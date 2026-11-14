"""Current factual-reader continuation under a shared, minimal actor interface.

Keep statutes and native graph schemas with the teacher/compiler, rather than
send competing downstream formats to a factual reader. Both learned arms and
the fixed generic control receive the same facts/question/query context. All
old requests/results and the existing physical ledger remain unchanged.
"""
import argparse
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

import jsonschema

from experiments import legal_skill_evolution_observation_library_train as learned
from experiments import legal_skill_evolution_generic_view_train as generic
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter, execute_alternatives
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.skill_evolution.generic_event_observation import PROMPT, schema_for, lower
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.literal_facts import literal_bindings
from legal_skill_guard.skill_evolution.native import record_schema, grade_view
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import decoder_schema, render_messages
from legal_skill_guard.skill_evolution.span_compiler import execute_json
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING


ROOT = learned.ROOT
RUN = 'legal_skill_evolution_mixed_case_actor_givens6_20261114'
OUT = ROOT / 'artifacts' / RUN
ARMS = (*learned.ARMS, 'GenericView')
read = learned.read


def prepare():
    if (OUT / 'protocol.json').exists():
        return read(OUT / 'protocol.json')
    prior = read(learned.OUT / 'protocol.json')
    paths = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/runtime.py',
        ROOT / 'legal_skill_guard/skill_evolution/generic_event_observation.py',
        ROOT / 'legal_skill_guard/skill_evolution/native_case_encoding.py',
        ROOT / 'legal_skill_guard/skill_evolution/case_observation_contract.py',
        ROOT / 'legal_skill_guard/skill_evolution/sara_statute_kernel.py']
    protocol = {'run_id': RUN, 'same_goal': True, 'continuation_of': [learned.RUN, generic.RUN],
        'sources': prior['sources'], 'batches': prior['batches'], 'executor_profile': prior['executor_profile'],
        'thinking': False, 'same_factual_context_fields_all_arms': ['facts', 'question'],
        'actor_program_interface_fields': ['native_query', 'query_clause'],
        'teacher_retains_complete_source_law_and_exact_author_programs': True,
        'no_competing_native_input_graph_schema_in_actor_prompt': True,
        'generic_one_unary_kind_per_record_no_ontology_copying_array': True,
        'explicit_same_event_ID_keeps_multiple_kinds_without_inventing_events': True,
        'raw_old_truncations_and_costs_retained': True,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        'TEST_opened': False, 'new_sources_seeds_or_model_settings': False, 'goal_complete': False}
    immutable_json(OUT / 'protocol.json', protocol)
    for path in paths:
        target = OUT / 'source_snapshot' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    return protocol


def execute(protocol, batch, arm, *, initial=False):
    if initial and arm == 'GenericView':
        raise ValueError('GenericView has one fixed observation per source, not a learned pre/post library')
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    client.exact_replay_roots = [OUT]
    public = {s['key']: s for s in read(learned.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: current_case_interface(r['kernel']) for r in read(learned.parent.OUT / 'SARA_native_kernel_bank.json')}
    stage = 'initial_results' if initial else 'results'
    target_root = (generic.OUT if arm == 'GenericView' else learned.OUT) / f'B{batch}'
    if arm != 'GenericView':
        library = read(learned.OUT / f'B{batch-1 if initial else batch}' / arm / 'library.json')
    for sid in [s for s in protocol['batches'][batch-1] if s in public]:
        target = target_root / (stage if arm == 'GenericView' else arm + '/' + stage) / (digest(sid) + '.json')
        if target.exists():
            continue
        source = deepcopy(public[sid])
        original_hash = source['runtime_actor_views_sha256']
        source['runtime_actor_views_sha256'] = digest(source['views'])
        pub, kernel = source['views'][0]['public'], kernels[sid]
        row = {'source': sid, 'arm': arm, 'batch': batch,
            'stage': 'pre_update_TRAIN' if initial else 'post_update_TRAIN', 'fallback': False, 'reads': [],
            'actor_interface_revision': RUN, 'original_prepared_view_hash_retained_as_provenance': original_hash,
            'corrected_runtime_actor_view_hash': source['runtime_actor_views_sha256']}
        try:
            if arm == 'GenericView':
                schema = schema_for(kernel)
                prompt = PROMPT + '\nShared native event meanings: ' + FACTUAL_ENCODING
            else:
                components = {c['id']: c for c in library['components']}
                plan = execute_json(library['planner_program'], {'kernel': kernel, 'public_case': pub}, {}, allow_helpers=True)
                assert set(plan) == {'component_ids'}
                ids = plan['component_ids']
                assert len(ids) == len(set(ids)) and set(ids) <= set(components)
                row.update(library_sha256=digest(library), actual_component_ids=ids)
                schema = record_schema({cid: json.loads(components[cid]['schema_json']) for cid in ids})
                prompt = '\n\n'.join(components[cid]['prompt'] for cid in ids)
            observation = {}
            if arm == 'GenericView' or ids:
                task = {'current_case': {k: pub[k] for k in protocol['same_factual_context_fields_all_arms']},
                    'current_legal_query': {k: kernel[k] for k in protocol['actor_program_interface_fields']}}
                if arm != 'GenericView':
                    task['component_meanings'] = {cid: components[cid]['meaning'] for cid in ids}
                messages = render_messages(prompt, task, schema)
                count = client.tokenize(messages, thinking=False)['count']
                assert count + protocol['executor_profile']['max_tokens'] <= protocol['executor_profile']['context_tokens']
                row['input_tokens'] = count
                response = client.generate(RUN + ':B' + str(batch) + ':' + stage + ':' + arm + ':' + sid,
                    source=sid, purpose='skill_actor', thinking=False, messages=messages, schema=decoder_schema(schema)[0])
                row['reads'].append({k: response[k] for k in ('usage', 'elapsed_seconds', 'finish_reason')})
                if response['finish_reason'] != 'stop':
                    raise ValueError('generation_truncated: ' + response['finish_reason'])
                value = json.loads(response['content'])
                row['raw_decoded_observation'] = value
                observation = value
                jsonschema.validate(observation, schema)
            row['observation'] = observation
            grounded = (lower(observation, kernel, pub) if arm == 'GenericView' else
                apply_adapter({'binding_program': library['binding_program']}, kernel, pub, observation,
                    literal_context=literal_bindings({'public': pub})))
            row.update(grounded=grounded, execution=execute_alternatives(kernel, grounded))
            row['learning_evidence_requires_actual_case_observation'] = bool(row.get('reads'))
        except GenerationHold:
            raise
        except Exception as error:
            with ledger.transaction() as db:
                assert not db.execute("select 1 from calls where status='reserved'").fetchone(), 'Reconcile actual pending call'
            row.update(error=type(error).__name__ + ': ' + str(error), execution={'handled': False, 'answer': None})
        immutable_json(target, row)
        print(json.dumps({'batch': batch, 'arm': arm, 'source': sid, 'handled': row['execution']['handled'],
            'error': row.get('error'), 'input_tokens': row.get('input_tokens')}), flush=True)
        if arm == 'GenericView' and row.get('error', '').startswith('ValueError: generation_truncated'):
            # Actual continuing systematic format failure is a route issue.
            # Keep unsent sources unsent; other learning branches continue.
            immutable_json(OUT / f'B{batch}/generic_format_route_unresolved.json', {
                'source': sid, 'reason': row['error'], 'unsent_sources_not_failed_or_retried': True,
                'same_goal_active': True})
            return


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['prepare', 'execute'])
    parser.add_argument('--arm', choices=ARMS)
    parser.add_argument('--batch', type=int, choices=range(3, 9), default=3)
    parser.add_argument('--initial', action='store_true')
    args = parser.parse_args()
    protocol = prepare()
    for name, expected in protocol['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected
    if args.phase == 'execute':
        assert args.arm
        with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            execute(protocol, args.batch, args.arm, initial=args.initial)
