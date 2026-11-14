"""Frozen current C/observation recipes on the original forty DEV parents.

No teacher, updates, new sources or TEST access. Shared predictions are executed
once and referenced by each recipe; core results remain separate from fallback.
Preparation refuses to read DEV until the actual B8 freeze exists.
"""
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path
import tarfile

import jsonschema

from experiments import legal_skill_evolution_mixed_freeze as frozen
from experiments import legal_skill_evolution_mixed_training_continue as current
from experiments import legal_skill_evolution_source_library_train as source_train
from experiments import legal_skill_evolution_five_train as parent
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives
from legal_skill_guard.skill_evolution.case_read_comparison import compare_reads, ordinary_action
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.skill_evolution.generic_event_observation import PROMPT, schema_for, lower
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import grade_view, record_schema, source_spans
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest, Library
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface, query_term
from legal_skill_guard.skill_evolution.scoped_grammar import material_public
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from legal_skill_guard.skill_evolution.span_compiler import execution_source_units, execute_json
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_execution
from legal_skill_guard.skill_evolution.statute_pure_calculation import certificate as calculation_certificate


ROOT = parent.ROOT
RUN = 'legal_skill_evolution_mixed_DEV_public_execution_20261115'
OUT = ROOT / 'artifacts' / RUN
PREPARED = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/dev'
read = parent.read


def prepare():
    freeze_path = frozen.OUT / 'frozen_manifest.json'
    manifest = read(freeze_path)  # Must precede every DEV input/result read.
    for name, sha in manifest['bound_files_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
    public = {s['key']: s for s in read(PREPARED / 'public.json')}
    assert len(public) == 40 and all(s['split'] == 'dev' for s in public.values())
    assert not set(public) & set(manifest['original_128_TRAIN_sources'])
    common_path = current.source_updates.train.ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/dev/FreeEvolution/B8.json'
    common = read(common_path)
    assert common['library_hash'] == Library.load(frozen.shared.COMMON / 'B8.json').hash
    common_rows = {r['source']: r for r in common['results']}
    assert set(common_rows) == set(public)
    inputs = [freeze_path, PREPARED / 'public.json', PREPARED / 'grading.json', common_path,
        parent.OUT / 'SARA_native_kernel_bank.json']
    protocol = {'run_id': RUN, 'same_goal': True, 'freeze_sha256': digest(manifest),
        'recipes': manifest['recipes'], 'train_sources': manifest['original_128_TRAIN_sources'],
        'dev_sources': list(public), 'test_sources': [], 'thinking': False,
        'data_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs},
        'driver_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'author_case_polarity_and_formal_facts_never_actor_input': True,
        'same_common_B8_fallback_only_when_current_execution_unhandled': True,
        'historical_DEV_exposure_disclosed_not_a_new_blind_test': True,
        'teacher_disabled': True, 'updates_disabled': True, 'TEST_opened': False}
    immutable_json(OUT / 'protocol.json', protocol)
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['train_sources'], 'dev': protocol['dev_sources'], 'test': []},
        binding=digest(protocol), freeze={'batch': 8, 'artifact_sha256': digest(manifest)})
    client = FrozenExecutor(ledger, OUT, manifest['executor_profile'])
    return manifest, public, common_rows, client


def sara_interfaces(public):
    """Restore only each fixed DEV task query, with its expected polarity removed."""
    from experiments.legal_skill_evolution_native_execution_reuse import parse_query
    grading = read(PREPARED / 'grading.json')
    template = read(parent.OUT / 'SARA_native_kernel_bank.json')[0]['kernel']
    kernels, actor_sources, receipts = {}, {}, []
    with tarfile.open('/tmp/lsg_sara_v2_native_archive_20261114.tar.gz') as archive:
        for sid, record in public.items():
            if record['dataset'] != 'SARA_v2_Binary':
                continue
            original = grading[sid]['native']['original_id']
            assert '/' not in original and '..' not in original
            body = archive.extractfile('sara_v2/cases/' + original + '.pl').read()
            query = parse_query(body.decode().split('% Test', 1)[1])
            kernel = deepcopy(template)
            kernel.update(name='+'.join(c['predicate'] for c in query),
                query_clause='+'.join(c['predicate'] for c in query), native_query=query)
            kernels[sid] = current_case_interface(kernel)
            actor_source = deepcopy(record)
            actor_source['views'][0]['public']['question'] += '\nNative query constraints from this same original task (truth value not supplied): ' + ', '.join(query_term(c) for c in query) + '.'
            actor_sources[sid] = actor_source
            receipts.append({'source': sid, 'original_member_sha256': hashlib.sha256(body).hexdigest(),
                'native_query_without_polarity': query, 'formal_case_facts_copied': False,
                'native_answer_copied': False})
    immutable_json(OUT / 'query_restoration_receipts.json', receipts)
    return kernels, actor_sources


def generate(client, sid, name, prompt, task, schema):
    messages = render_messages(prompt, task, schema)
    tokens = client.tokenize(messages, thinking=False)['count']
    assert tokens + client.config['max_tokens'] <= client.config['context_tokens']
    value = client.generate(RUN + ':' + name + ':' + sid, source=sid, purpose='skill_dev',
        thinking=False, messages=messages, schema=decoder_schema(schema)[0])
    if value['finish_reason'] != 'stop':
        raise ValueError('generation_truncated: ' + value['finish_reason'])
    decoded = json.loads(value['content'])
    jsonschema.validate(decoded, schema)
    return decoded, {k: value[k] for k in ('usage', 'elapsed_seconds', 'finish_reason')}


def observe_case(client, source, kernel, arm, library):
    target = OUT / 'initial' / arm / (digest(source['key']) + '.json')
    if target.exists():
        return read(target)
    sid, pub = source['key'], source['views'][0]['public']
    row = {'source': sid, 'arm': arm, 'reads': [], 'fallback': False}
    try:
        calc = calculation_certificate(kernel)
        if calc['certified_fact_independent']:
            grounded = {'bindings':[{'inputs':{'facts':[],'negative_givens':[],'extraction_status':'complete'},'witnesses':[]}], 'unresolved':[]}
            row.update(actual_component_ids=[],observation={},grounded=grounded,
                execution=execute_alternatives(kernel,grounded),shared_public_calculation=calc)
            immutable_json(target,row)
            return row
        if arm == 'GenericView':
            ids, schema = [], schema_for(kernel)
            prompt = PROMPT + '\nShared native event meanings: ' + FACTUAL_ENCODING
        else:
            components = {c['id']: c for c in library['components']}
            plan = execute_json(library['planner_program'], {'kernel': kernel, 'public_case': pub}, {}, allow_helpers=True)
            assert set(plan) == {'component_ids'}
            ids = plan['component_ids']
            assert len(ids) == len(set(ids)) and set(ids) <= set(components)
            schema = record_schema({cid: json.loads(components[cid]['schema_json']) for cid in ids})
            prompt = '\n\n'.join(components[cid]['prompt'] for cid in ids)
            row['library_sha256'] = digest(library)
        row['actual_component_ids'] = ids
        observation = {}
        if arm == 'GenericView' or ids:
            task = {'current_case': {k: pub[k] for k in ('facts', 'question')},
                'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')}}
            if arm != 'GenericView':
                task['component_meanings'] = {cid: components[cid]['meaning'] for cid in ids}
            observation, receipt = generate(client, sid, 'initial:' + arm, prompt, task, schema)
            row['reads'].append(receipt)
        row['observation'] = observation
        grounded = (lower(observation, kernel, pub) if arm == 'GenericView' else
            apply_adapter({'binding_program': library['binding_program']}, kernel, pub, observation,
                literal_context=literal_bindings({'public': pub})))
        row.update(grounded=grounded, execution=execute_alternatives(kernel, grounded))
        if arm != 'GenericView':
            row['contract'] = {'binding_program': library['binding_program'],
                'observation_schema_json': json.dumps(schema), 'observation_prompt': prompt,
                'requires_neural_read': bool(ids)}
    except GenerationHold:
        raise
    except (ValueError, KeyError, TypeError, AssertionError, jsonschema.ValidationError) as error:
        row.update(error=type(error).__name__ + ': ' + str(error), execution={'handled': False, 'answer': None})
    immutable_json(target, row)
    return row


def followup(client, source, kernel, initial, arm):
    target = OUT / 'followup' / arm / (digest(source['key']) + '.json')
    if target.exists():
        return read(target)
    if ('contract' not in initial or initial['execution']['handled'] or
            not initial['contract']['requires_neural_read']):
        result = {'eligible': False, 'reason': 'Already handled, invalid initial conversion, or no declared neural channel', 'policies': {}}
    else:
        sid, pub = source['key'], source['views'][0]['public']
        contract, observation = initial['contract'], initial['observation']

        def dispatch(policy, action):
            return generate(client, sid, arm + ':' + policy, action['prompt'],
                {'current_case': {k: pub[k] for k in ('facts', 'question')},
                 'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')},
                 'current_observation': observation,
                 'existing_unresolved_messages': initial['grounded']['unresolved']}, action['schema'])

        if arm == 'ProgramGuided':
            result = compare_reads(contract, kernel, pub, deepcopy(observation), dispatch)
        else:
            action = ordinary_action(contract, initial['execution'], observation)
            try:
                value, receipt = dispatch('ordinary_reread', action)
                updated = {**deepcopy(observation), **value}
                jsonschema.validate(updated, json.loads(contract['observation_schema_json']))
                grounded = apply_adapter(contract, kernel, pub, updated,
                    literal_context=literal_bindings({'public': pub}))
                outcome = {'execution': execute_alternatives(kernel, grounded),
                    'action': action, 'observation_after': updated, 'read_receipt': receipt}
            except GenerationHold:
                raise
            except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
                outcome = {'execution': {'handled': False, 'answer': None}, 'error': type(error).__name__ + ': ' + str(error)}
            result = {'eligible': True, 'policies': {'ordinary_reread': outcome}}
    immutable_json(target, {'source': source['key'], 'initial_row_sha256': digest(initial), **result})
    return read(target)


class SourceDEVReader:
    """The existing source observer declares TRAIN replay; enforce DEV instead."""
    def __init__(self, client):
        self.client = client
        self.config = client.config

    def tokenize(self, *args, **kwargs):
        return self.client.tokenize(*args, **kwargs)

    def generate(self, call_id, **kwargs):
        assert kwargs.pop('purpose') == 'skill_replay'
        return self.client.generate(call_id, purpose='skill_dev', **kwargs)


def source_case(client, source, libraries):
    """Execute the identical source path with DEV material; no scores supplied."""
    sid, pub = source['key'], source['views'][0]['public']
    target = OUT / 'source' / (digest(sid) + '.json')
    if target.exists():
        return read(target)
    base_dir = source_train.previous.old.previous.PARENT
    base, grammar = read(base_dir / 'base.json'), read(base_dir / 'grammar.json')
    upstream, event = run_source(base['source_program'], base['grammar'], grammar, source)
    output = upstream['source_program_output']
    units, _ = execution_source_units(pub['source_text'], source_spans(material_public(pub)))
    rows = {'common_upstream_without_phi_G': contract_execution(libraries['ConstraintAcquire']['spec'], source)(output)}
    for arm, library in libraries.items():
        def save_event(event):
            immutable_json(OUT / 'source_events' / arm / digest(sid) / (digest(event['call_id']) + '.json'), event)
        try:
            observed = source_train.previous.old.observe(SourceDEVReader(client), RUN + ':' + arm + ':' + sid,
                sid, library, source_text=pub['source_text'], units=units, source_output=output, save_event=save_event)
            actual = source_train.previous.old.previous.prior.prior.evaluate_source(library, observed, source, None)
            rows[arm] = {**actual['feedback'], 'source_execution': actual['execution'], 'observation': observed}
        except GenerationHold:
            raise
        except (ValueError, KeyError, TypeError, jsonschema.ValidationError) as error:
            rows[arm] = {'error': type(error).__name__ + ': ' + str(error), 'views': []}
    immutable_json(target, {'source': sid, 'rows': rows, 'native_labels_used': False, 'upstream_event': event})
    return read(target)


def score_view(source, view, actual, inherited, grading):
    fallback = not actual['core_executed']
    answer = inherited['execution']['answer'] if fallback else actual['answer']
    return {'view': view['id'], 'core_execution': actual, 'fallback': fallback,
        'shared_public_calculation':actual.get('shared_public_calculation',False),
        'current_learned_mechanism_executed':actual.get('current_learned_mechanism_executed',False),
        'fallback_reason': ('unchanged_common_boundary_route' if source['dataset'] in frozen.shared.DATASETS else 'current_core_unhandled') if fallback else None,
        'answer': answer, 'score': grade_view(source['dataset'], view, grading, answer),
        'core_score': grade_view(source['dataset'], view, grading, actual['answer'])}


def run():
    manifest, public, common, client = prepare()
    libraries = {a: frozen.source.load(8, a) for a in source_train.ARMS}
    observation_libraries = {a: read(ROOT / manifest['libraries']['observation/' + a]['path']) for a in current.learned.ARMS}
    kernels, actor_sources = sara_interfaces(public)
    # Execute and save all primary records before loading the scoring file here.
    for sid, source in public.items():
        if source['dataset'] == 'SARA_v2_Binary':
            for arm in ('GenericView', *current.learned.ARMS):
                row = observe_case(client, actor_sources[sid], kernels[sid], arm, observation_libraries.get(arm))
                if arm != 'GenericView':
                    followup(client, actor_sources[sid], kernels[sid], row, arm)
        elif source['dataset'] == 'ContractNLI':
            source_case(client, source, libraries)
        print(json.dumps({'DEV_primary_saved': sid, 'updates': False}), flush=True)
    grading = read(PREPARED / 'grading.json')
    recipes = {}
    for name, recipe in manifest['recipes'].items():
        rows = []
        for sid, source in public.items():
            inherited = {v['view']: v for v in common[sid]['views']}
            if source['dataset'] == 'SARA_v2_Binary':
                arm = 'GenericView' if recipe['observation'] == 'fixed_generic' else recipe['observation']
                initial = read(OUT / 'initial' / arm / (digest(sid) + '.json'))
                execution = initial['execution']
                if arm != 'GenericView' and recipe['followup'] != 'none':
                    result = read(OUT / 'followup' / arm / (digest(sid) + '.json'))
                    execution = result['policies'].get(recipe['followup'], {}).get('execution', execution)
                core = {source['views'][0]['id']: {'core_executed': execution['handled'], 'answer': execution['answer'],
                    'shared_public_calculation':bool(initial.get('shared_public_calculation')),
                    'current_learned_mechanism_executed':arm!='GenericView' and
                        bool(initial.get('actual_component_ids')) and bool(initial.get('observation')) and
                        not initial.get('shared_public_calculation')}}
            elif source['dataset'] == 'ContractNLI':
                record = read(OUT / 'source' / (digest(sid) + '.json'))['rows'][recipe['source']]
                core = {v['view']: {'core_executed': v['core_executed'],
                    'answer': v['execution']['value']['answer'],
                    'current_learned_mechanism_executed':recipe['source']!='common_upstream_without_phi_G'} for v in record['views']}
            else:
                core = {}  # Explicit common boundary route, no C/M2 claim.
            views = []
            for view in source['views']:
                actual = core.get(view['id'], {'core_executed': False, 'answer': None})
                views.append(score_view(source, view, actual, inherited[view['id']], grading[sid][view['id']]))
            rows.append({'source': sid, 'dataset': source['dataset'], 'views': views})
        recipes[name] = {'recipe': recipe, 'rows': rows, 'native_parent_mean': sum(
            sum(v['score']['grade'] for v in r['views'])/len(r['views']) for r in rows)/len(rows),
            'fallback_views': sum(v['fallback'] for r in rows for v in r['views']),
            'native_backend_correct_views': sum(v['core_execution']['core_executed'] and v['core_score']['correct'] for r in rows for v in r['views']),
            'learned_mechanism_correct_views': sum(v['core_execution']['core_executed'] and v['core_score']['correct'] and v['current_learned_mechanism_executed'] for r in rows for v in r['views'])}
    immutable_json(OUT / 'scored_results.json', {'recipes': recipes, 'frozen_B8_not_best_DEV': True,
        'teacher_or_updates': False, 'fallback_not_core_success': True,
        'native_correctness_not_source_semantic_or_novelty_certification': True, 'goal_complete': False})


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run()
