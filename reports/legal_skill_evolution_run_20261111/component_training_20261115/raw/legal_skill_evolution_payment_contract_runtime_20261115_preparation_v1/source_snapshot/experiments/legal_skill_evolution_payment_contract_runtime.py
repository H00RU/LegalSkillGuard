"""Frozen runtime for the acquired payment/service refinement and controls."""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_payment_contract_refinement as generation
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT = generation.ROOT
RUN = 'legal_skill_evolution_payment_contract_runtime_20261115'
OUT = ROOT / 'artifacts' / RUN
runtime = generation.runtime
read = generation.read


def prepare():
    old = read(generation.OUT / 'protocol.json')
    for path, sha in old['source_sha256'].items():
        assert hashlib.sha256((generation.OUT / 'source_snapshot' / path).read_bytes()).hexdigest() == sha
    assert all((generation.OUT / arm / 'teacher.json').exists() for arm in ('Method', 'FreeTeacher'))
    p = deepcopy(old)
    p.update(run_id=RUN, generation_run=generation.RUN,
        generation_protocol_sha256=digest(old),
        runtime_change='Apply the same strict nominal binder to payment contracts that also enumerate plan events')
    immutable_json(OUT / 'TRAIN_grading.json', read(generation.OUT / 'TRAIN_grading.json'))
    for channel in ('component_reads', 'relation_reads'):
        for file in (generation.OUT / channel).glob('*.json'):
            immutable_json(OUT / channel / file.name, read(file))
    files = [Path(__file__), Path(generation.__file__), Path(runtime.__file__),
             generation.OUT / 'common_library.json', OUT / 'TRAIN_grading.json']
    files += [generation.OUT / arm / 'teacher.json' for arm in ('Method', 'FreeTeacher')]
    files += sorted((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    p['source_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    immutable_json(OUT / 'protocol.json', p)
    for file in files:
        target = OUT / 'source_snapshot' / file.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(file.read_bytes())
    libraries = generation.candidates(p)
    for name, library in libraries.items():
        immutable_json(OUT / 'candidate_libraries' / (name + '.json'), library)
    immutable_json(OUT / 'offline_proposal_validation.json', {'candidates': sorted(libraries),
        'new_model_calls': 0, 'not_whole_case_or_semantic_success': True})
    print(json.dumps({'prepared': RUN, 'candidates': sorted(libraries)}), flush=True)


def protocol():
    p = read(OUT / 'protocol.json')
    for file, sha in p['source_sha256'].items():
        assert hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == sha, file
    return p


def fixed_generic(client, p, sid, source, kernel):
    target = OUT / 'fixed_generic' / (digest(sid) + '.json')
    if target.exists():
        return read(target)
    public = source['views'][0]['public']
    original = runtime.generic_schema(kernel, public)
    messages = runtime.render_messages(runtime.GENERIC_PROMPT + '\nShared native event meanings: ' + p['shared_native_event_encoding'],
        {'current_case': {k: public[k] for k in ('facts', 'question')},
         'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')}}, original)
    row = {'source': sid, 'condition': 'unchanged_fixed_generic_native_event_view', 'fallback': False}
    try:
        wire, _ = runtime.decoding_schema(original)
        assert client.tokenize(messages, thinking=False)['count'] + p['executor_profile']['max_tokens'] <= p['executor_profile']['context_tokens']
        response = client.generate(RUN + ':fixed_generic:' + digest(sid), source=sid,
            purpose='skill_actor', messages=messages, thinking=False, schema=wire)
        immutable_json(OUT / 'fixed_generic_raw' / (digest(sid) + '.json'), response)
        assert response['finish_reason'] == 'stop', 'Incomplete fixed generic observation'
        observation = json.loads(response['content'])
        jsonschema.validate(observation, original)
        grounded = runtime.generic_lower(observation, kernel, public)
        execution = runtime.execute_alternatives(kernel, grounded)
        reviewed = runtime.review(sid, grounded, complete_families=[n for n, a in kernel['fact_arities'].items() if a == 1])
        grading = read(OUT / 'TRAIN_grading.json')
        score = runtime.grade_view(source['dataset'], source['views'][0], grading[sid][source['views'][0]['id']], execution['answer'])
        row.update(observation=observation, grounded=grounded, execution=execution,
            source_review=reviewed, native_score=score,
            core_correct=execution['handled'] and score['correct'] and not reviewed['failures'],
            receipt={k: response.get(k) for k in ('usage', 'elapsed_seconds', 'finish_reason', 'cache_hit', 'reused_physical_call_id')})
    except Exception as error:
        row.update(error=type(error).__name__ + ': ' + str(error), core_correct=False)
    immutable_json(target, row)
    return row


def execute():
    p = protocol()
    public, kernels = runtime.previous.data()
    libraries = {n: read(OUT / 'candidate_libraries' / (n + '.json'))
                 for n in read(OUT / 'offline_proposal_validation.json')['candidates']}
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': p['sources'], 'dev': [], 'test': []}, binding=digest(p))
    client = FrozenExecutor(ledger, OUT, p['executor_profile'])
    client.exact_replay_roots = [runtime.OUT, generation.latest.OUT,
        ROOT / 'artifacts/legal_skill_evolution_generic_view_train_20261113']
    acquired, selected = [], {}
    for name, library in libraries.items():
        rows = [runtime.run_case(client, p, name, library, sid, public[sid]['views'][0]['public'], kernels[sid])
                for sid in p['acquisition_sources']]
        acquired.append({'candidate': name, 'rows': rows})
    for arm in ('Method', 'FreeTeacher'):
        best = min((v for v in acquired if v['candidate'].startswith(arm + '/')),
            key=lambda v: (-sum(r['core_correct'] for r in v['rows']),
                sum(r['source_failures'] for r in v['rows']),
                sum(x.get('elapsed_seconds') or 0 for r in v['rows'] for x in r['reads']), v['candidate']))
        selected[arm] = best['candidate']
    immutable_json(OUT / 'selected_before_reuse.json', {'selected': selected, 'acquisition_only': True})
    reuse = [runtime.run_case(client, p, name, libraries[name], sid, public[sid]['views'][0]['public'], kernels[sid])
             for name in selected.values() for sid in p['fixed_reuse_sources']]
    ordinary = [runtime.run_case(client, p, selected['Method'], libraries[selected['Method']], sid,
        public[sid]['views'][0]['public'], kernels[sid], policy='ordinary') for sid in p['fixed_reuse_sources']]
    generic = [fixed_generic(client, p, sid, public[sid], kernels[sid])
               for sid in p['acquisition_sources'] + p['fixed_reuse_sources']]
    immutable_json(OUT / 'result.json', {'acquisition': acquired, 'selected': selected,
        'fixed_reuse': reuse, 'same_contract_ordinary_reuse': ordinary, 'fixed_generic': generic,
        'goal_complete': False, 'DEV_TEST_loaded': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'execute'))
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        {'prepare': prepare, 'execute': execute}[args.phase]()
