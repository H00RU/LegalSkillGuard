"""Execute paid observation revisions before continuing the fixed mixed queue.

Component reads are independent real requests, so exact reuse across candidate
combinations does not pretend a jointly generated observation was independent.
TRAIN scoring follows saved execution; it never enters a reader prompt.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_observation_component_acquire as acquisition
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import (
    convert, observation_schema, plan, replace_components, validate)
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages


ROOT = acquisition.ROOT
RUN = 'legal_skill_evolution_observation_component_execution_20261115'
OUT = ROOT / 'artifacts' / RUN
read = acquisition.read


def candidate_library(base, proposal):
    library = replace_components(base, proposal['component_edits'])
    by_id = {c['id']: c for c in library['components']}
    updates = proposal['coverage_updates']
    if len(updates) != len(by_id) or {c['id'] for c in updates} != set(by_id):
        raise ValueError('Exactly one coverage contract per resulting component')
    for update in updates:
        by_id[update['id']].update(deepcopy(update))
    return library


def prepare():
    path = OUT / 'protocol.json'
    if path.exists():
        protocol = read(path)
    else:
        old = read(acquisition.OUT / 'protocol.json')
        files = [Path(__file__)] + [ROOT / 'legal_skill_guard/skill_evolution' / name for name in (
            'observation_component_library.py', 'statute_input_dependencies.py',
            'case_observation_contract.py', 'sara_statute_kernel.py', 'clients.py', 'ledger.py',
            'span_compiler.py', 'span_compiler_worker.py', 'runtime.py')]
        inputs = [acquisition.OUT / 'protocol.json', acquisition.OUT / 'seed_library.json']
        inputs += [acquisition.OUT / arm / 'teacher.json' for arm in acquisition.ARMS]
        inputs += [acquisition.previous.parent.OUT / name for name in (
            'SARA_native_kernel_bank.json', 'SARA_corrected_TRAIN_views.json')]
        protocol = {'run_id': RUN, 'same_goal': True,
            'sources': old['all_inherited_TRAIN_exposure'],
            'acquisition_sources': old['acquisition_sources'], 'reuse_sources': old['reuse_sources'],
            'executor_profile': old['executor_profile'], 'thinking': False,
            'teacher_calls': 0, 'DEV_TEST_loaded': False,
            'prior_B8_exposure_disclosed_not_a_blind_split': True,
            'independent_component_reads_common_to_all_arms': True,
            'shared_missing_coverage_is_unresolved_not_false': True,
            'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files + inputs}, 'goal_complete': False}
        immutable_json(path, protocol)
        for p in files:
            target = OUT / 'source_snapshot' / p.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(p.read_bytes())
    for name, sha in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Frozen execution binding changed: ' + name)
    return protocol


def libraries():
    base = read(acquisition.OUT / 'seed_library.json')
    result = {}
    for arm in acquisition.ARMS:
        proposals = read(acquisition.OUT / arm / 'teacher.json')['value']['candidates']
        pair = [candidate_library(base, p) for p in proposals]
        for index, library in enumerate(pair):
            result[arm + '/' + str(index)] = library
        if arm == 'CoverageRecombine':
            # A genuine version recombination: retain candidate0's local repairs
            # and add candidate1's newly acquired source-native component. No
            # facts, rules, schema fields or code are supplied by the host.
            left = {c['id']: deepcopy(c) for c in pair[0]['components']}
            new = [c for c in pair[1]['components'] if c['id'] not in left]
            if new:
                left.update({c['id']: deepcopy(c) for c in new})
                result[arm + '/recombined'] = {**deepcopy(pair[0]), 'components': list(left.values())}
    return result


def read_component(client, protocol, sid, component, kernel, public):
    schema = observation_schema({'components': [component]}, [component['id']])
    task = {'current_case': {k: public[k] for k in ('facts', 'question')},
        'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')},
        'component_meanings': {component['id']: component['meaning']}}
    messages = render_messages(component['prompt'], task, schema)
    # Identity excludes lineage/coverage/converter: those never enter the wire.
    key = digest({'source': sid, 'messages': messages, 'schema': schema})
    path = OUT / 'component_reads' / (key + '.json')
    if path.exists():
        result = read(path)
        if result['error']:
            raise ValueError('Saved physical read failure: ' + result['error'])
        return result['value'], result['receipt']
    result = {'source': sid, 'component_id': component['id'], 'wire_input_sha256': key,
        'value': None, 'error': None}
    try:
        count = client.tokenize(messages, thinking=False)['count']
        if count + protocol['executor_profile']['max_tokens'] > protocol['executor_profile']['context_tokens']:
            raise ValueError('Full component request exceeds the frozen context')
        response = client.generate(RUN + ':read:' + key, source=sid, purpose='skill_actor',
            thinking=False, messages=messages, schema=decoder_schema(schema)[0])
        # Raw provider content is saved before decode/schema/execution checks.
        immutable_json(OUT / 'raw_responses' / (key + '.json'), response)
        result['receipt'] = {k: response.get(k) for k in (
            'usage', 'elapsed_seconds', 'finish_reason', 'cache_hit', 'reused_physical_call_id')}
        if response['finish_reason'] != 'stop':
            raise ValueError('generation_truncated: ' + response['finish_reason'])
        value = json.loads(response['content'])
        result['value'] = value
        jsonschema.validate(value, schema)
    except GenerationHold:
        raise
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    immutable_json(path, result)
    if result['error']:
        raise ValueError(result['error'])
    return result['value'], result['receipt']


def execute_one(client, protocol, name, library, sid, kernel, source, phase):
    target = OUT / phase / name / (digest(sid) + '.json')
    if target.exists():
        return read(target)
    public = source['views'][0]['public']
    row = {'source': sid, 'candidate': name, 'phase': phase, 'library_sha256': digest(library),
        'reads': [], 'fallback': False, 'not_a_semantic_certificate': True}
    try:
        validate(library, kernel)
        selection = plan(library, kernel)
        row['plan'] = selection
        # This proposal explicitly leaves event families unrepresented. Do not
        # spend reads and later mislabel their unobserved absence as complete.
        # This is a proposal deficit, not an all-branches success criterion.
        if selection['unrepresented_native_families']:
            row.update(execution={'handled': False, 'answer': None},
                unresolved_proposal='Incomplete declared observation coverage; no physical reads dispatched')
        else:
            by_id = {c['id']: c for c in library['components']}
            observation = {}
            for cid in selection['component_ids']:
                value, receipt = read_component(client, protocol, sid, by_id[cid], kernel, public)
                observation.update(value)
                row['reads'].append({'component_id': cid, **receipt})
            row['observation'] = observation
            row['grounded'] = convert(library, selection['component_ids'], kernel, public, observation)
            row['execution'] = execute_alternatives(kernel, row['grounded'])
    except GenerationHold:
        raise
    except Exception as error:
        row.update(error=type(error).__name__ + ': ' + str(error),
            execution={'handled': False, 'answer': None})
    immutable_json(target, row)
    print(json.dumps({'phase': phase, 'candidate': name, 'source': sid,
        'handled': row['execution']['handled'], 'error': row.get('error'),
        'reads': len(row['reads'])}), flush=True)
    return row


def run(phase):
    protocol = prepare()
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3',
        run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    client.exact_replay_roots = [OUT, ROOT / 'artifacts/legal_skill_evolution_mixed_case_actor_givens6_20261114']
    public = {s['key']: s for s in read(acquisition.previous.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: acquisition.current_case_interface(r['kernel'])
        for r in read(acquisition.previous.parent.OUT / 'SARA_native_kernel_bank.json')}
    bank = libraries()
    for name, library in bank.items():
        immutable_json(OUT / 'libraries' / (name + '.json'), library)
    if phase == 'reuse':
        frozen = read(OUT / 'selected_after_acquisition.json')
        bank = {name: bank[name] for name in frozen['selected_candidates']}
    sources = protocol['acquisition_sources'] if phase == 'acquisition' else protocol['reuse_sources']
    rows = [execute_one(client, protocol, name, library, sid, kernels[sid], public[sid], phase)
        for sid in sources for name, library in bank.items()]
    grading = read(acquisition.previous.parent.PREPARED / 'grading.json')
    scored = [{**row, 'native_score': grade_view(public[row['source']]['dataset'],
        public[row['source']]['views'][0], grading[row['source']][public[row['source']]['views'][0]['id']],
        row['execution']['answer'])} for row in rows]
    immutable_json(OUT / phase / 'scored_results.json', {'rows': scored,
        'no_DEV_TEST': True, 'native_correctness_not_source_semantics': True, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('acquisition', 'reuse'))
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.phase)
