"""Continue all eight fixed mixed batches with revised observation learning.

Completed C acquisitions and unchanged boundary routes are inherited explicitly,
not regenerated or counted as new mechanism successes. Observation learning is
a warm continuation, with original B8 exposure and the failed finite probe fully
disclosed. Only original TRAIN enters updates; this driver never opens DEV/TEST.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import fcntl
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_observation_component_execute as actor
from experiments import legal_skill_evolution_mixed_shared_routes as shared
from experiments import legal_skill_evolution_generic_view_train as generic
from experiments import legal_skill_evolution_source_library_train as source_train
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.case_observation_contract import apply_adapter
from legal_skill_guard.skill_evolution.case_read_comparison import compare_reads
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.component_binding_program import binding_program
from legal_skill_guard.skill_evolution.decoder_constraints import decoding_schema
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.native_case_encoding import FACTUAL_ENCODING
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.observation_component_library import observation_schema, validate
from legal_skill_guard.skill_evolution.observation_source_review import review
from legal_skill_guard.skill_evolution.runtime import render_messages
from legal_skill_guard.skill_evolution.teacher_transport import pack_programs, INSTRUCTION, PROGRAM_INSTRUCTION


ROOT = actor.ROOT
RUN = 'legal_skill_evolution_mixed_component_training_20261115'
OUT = ROOT / 'artifacts' / RUN
read = actor.read
ARMS = actor.acquisition.ARMS


def setup():
    path = OUT / 'protocol.json'
    if path.exists():
        protocol = read(path)
    else:
        prior = read(actor.acquisition.previous.OUT / 'protocol.json')
        files = [Path(__file__), Path(actor.__file__)] + [ROOT / 'legal_skill_guard/skill_evolution' / name
            for name in ('observation_component_library.py', 'component_binding_program.py',
                'statute_input_dependencies.py', 'observation_source_review.py', 'decoder_constraints.py',
                'case_observation_contract.py', 'case_read_comparison.py', 'conversion_residual.py',
                'conversion_residual_worker.py', 'sara_statute_kernel.py', 'clients.py', 'ledger.py',
                'span_compiler.py', 'span_compiler_worker.py', 'runtime.py', 'teacher_transport.py')]
        inputs = [actor.acquisition.OUT / 'protocol.json', actor.acquisition.OUT / 'teacher_task.json']
        inputs += [actor.acquisition.OUT / arm / 'teacher.json' for arm in ARMS]
        inputs += [actor.acquisition.previous.parent.OUT / name for name in (
            'SARA_native_kernel_bank.json', 'SARA_corrected_TRAIN_views.json')]
        inputs += [actor.acquisition.previous.parent.PREPARED / 'public.json',
            actor.acquisition.previous.parent.PREPARED / 'grading.json',
            ROOT / 'artifacts/legal_skill_evolution_source_count_bias_repair_20261115/result.json',
            shared.OUT / 'result.json', actor.OUT / 'acquisition/scored_results.json']
        protocol = {'run_id': RUN, 'same_goal': True, 'sources': prior['sources'], 'batches': prior['batches'],
            'executor_profile': prior['executor_profile'], 'teacher_profile': prior['teacher_profile'],
            'thinking': False, 'shared_native_event_encoding': FACTUAL_ENCODING,
            'continuation_not_new_blind_training': True, 'original_B8_exposure_all128_disclosed': True,
            'eight_mixed_batches_16_mothers_each': True, 'new_sources_seeds_or_model_settings': False,
            'completed_C_updates_and_unchanged_boundary_routes_reused_not_retrained': True,
            'C_count_guard_is_common_repair_not_a_new_contribution': True,
            'M2_actual_initial_update_postupdate_and_same_contract_read_comparison': True,
            'ordinary_teacher_same_information_and_two_whole_proposals': True,
            'fixed_generic_predictions_preserved_no_unchanged_resampling': True,
            'selection': 'Shared partial source counterevidence failures, then native TRAIN correctness, then unresolved, then actual logical reads.',
            'candidate_retention_is_not_semantic_certification': True,
            'no_zero_fallback_or_all_branches_success_acceptance_threshold': True,
            'DEV_TEST_opened': False, 'goal_complete': False,
            'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in files + inputs}}
        immutable_json(path, protocol)
        for p in files:
            dest = OUT / 'source_snapshot' / p.relative_to(ROOT)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(p.read_bytes())
    for name, sha in protocol['source_sha256'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != sha:
            raise ValueError('Frozen mixed training binding changed: ' + name)
    ledger = EvolutionLedger(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3', run_id=RUN,
        sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol), teacher_concurrency=2)
    return protocol, ledger


def scored(row, public, grading):
    source = public[row['source']]
    return {**row, 'native_score': grade_view(source['dataset'], source['views'][0],
        grading[row['source']][source['views'][0]['id']], row['execution']['answer']),
        'partial_source_review': review(row['source'], row.get('grounded', {}))}


def inherited_routes(batch, keys):
    """Keep all five datasets visible without inventing new execution work."""
    path = OUT / f'B{batch}/inherited_routes.json'
    if path.exists():
        return
    correction = ROOT / 'artifacts/legal_skill_evolution_source_count_bias_repair_20261115'
    c_rows = {read(p)['source']: p for p in (correction / 'results').glob('*.json')}
    rows = []
    for sid in keys:
        dataset = sid.split(':', 1)[0]
        if dataset == 'SARA_v2_Binary':
            generic_path = generic.OUT / f'B{batch}/scored_results.json'
            value = read(generic_path)
            original = next(r for r in value['rows'] if r['source'] == sid)
            rows.append({'source': sid, 'dataset': dataset, 'route': 'actual_new_observation_learning',
                'fixed_generic_actual_result': original, 'fixed_generic_path': str(generic_path.relative_to(ROOT)),
                'generic_new_calls': 0, 'same_original_case_and_native_query': True})
        elif dataset == 'ContractNLI':
            free_path = source_train.OUT / 'B8/FreeUpdate/candidate_results' / source_train.previous.old.name_for(sid)
            rows.append({'source': sid, 'dataset': dataset, 'route': 'completed_C_and_Free_source_acquisition',
                'C_actual_result': read(c_rows[sid]), 'Free_actual_result_path': str(free_path.relative_to(ROOT)),
                'Free_actual_result_sha256': hashlib.sha256(free_path.read_bytes()).hexdigest(),
                'C_projection_is_common_repair_not_new_learning': True, 'new_model_calls': 0,
                'not_a_new_C_learning_curve': True})
        else:
            prior = shared.OUT / f'B{batch}/regraded_initial' / (digest(sid) + '.json')
            rows.append({'source': sid, 'dataset': dataset, 'route': 'exact_unchanged_shared_boundary',
                'actual_result_path': str(prior.relative_to(ROOT)), 'actual_result_sha256': hashlib.sha256(prior.read_bytes()).hexdigest(),
                'same_common_checkpoint_all_systems': True, 'new_model_calls': 0,
                'not_new_C_or_M2_learning_or_core_success': True})
    assert len(rows) == 16 and len({r['source'] for r in rows}) == 16
    immutable_json(path, {'batch': batch, 'rows': rows,
        'historical_exposure_and_acquisition_costs_inherited_by_all_arms': True})


def matched_read(client, protocol, batch, library, row, source, kernel):
    path = OUT / f'B{batch}/matched_reads' / (digest(row['source']) + '.json')
    if path.exists():
        return read(path)
    if not row.get('grounded') or not row.get('observation'):
        value = {'source': row['source'], 'eligible': False,
            'reason': 'No valid initial converted observation; not a residual opportunity', 'policies': {}}
    else:
        ids = row['plan']['component_ids']
        public = source['views'][0]['public']
        contract = {'binding_program': binding_program(library, ids),
            'observation_schema_json': json.dumps(observation_schema(library, ids)),
            'observation_prompt': '\n\n'.join(c['prompt'] for c in library['components'] if c['id'] in ids)
                + '\nShared native event meanings: ' + FACTUAL_ENCODING,
            'requires_neural_read': bool(ids)}
        parity = apply_adapter(contract, kernel, public, row['observation'], literal_context={})
        if parity != row['grounded']:
            raise ValueError('Compiled residual adapter changed actual conversion')

        def dispatch(policy, action):
            task = {'current_case': {k: public[k] for k in ('facts', 'question')},
                'current_legal_query': {k: kernel[k] for k in ('native_query', 'query_clause')},
                'current_observation': row['observation'],
                'existing_unresolved_messages': row['grounded']['unresolved']}
            messages = render_messages(action['prompt'], task, action['schema'])
            response = client.generate(RUN + f':B{batch}:matched:' + policy + ':' + row['source'],
                source=row['source'], purpose='skill_actor', thinking=False, messages=messages,
                schema=decoding_schema(action['schema'])[0])
            immutable_json(OUT / f'B{batch}/matched_raw' / policy / (digest(row['source']) + '.json'), response)
            if response['finish_reason'] != 'stop':
                raise ValueError('Matched read truncated: ' + response['finish_reason'])
            return json.loads(response['content']), {k: response.get(k) for k in ('usage', 'elapsed_seconds', 'finish_reason')}

        value = {'source': row['source'], **compare_reads(contract, kernel, public, row['observation'], dispatch)}
    immutable_json(path, value)
    return value


def acquire(protocol, ledger, batch, libraries, initial, public, kernels, grading):
    path = OUT / f'B{batch}/teacher_task.json'
    if not path.exists():
        common = read(actor.acquisition.OUT / 'teacher_task.json')
        keys = [sid for sid in protocol['batches'][batch - 1] if sid in kernels]
        task = {'same_goal': True, 'mixed_batch': batch,
            'current_libraries_both_available': libraries,
            'full_unchanged_author_statutes': common['full_unchanged_author_statutes'],
            'source_native_signatures': common['source_native_signatures'],
            'explicit_source_given_signatures': common['explicit_source_given_signatures'],
            'shared_native_event_encoding': FACTUAL_ENCODING,
            'acquisition_cases': [{'source': sid, 'public_case': public[sid]['views'][0]['public'],
                'kernel': kernels[sid], 'original_TRAIN_supervision': grading[sid]} for sid in keys],
            'current_actual_initial_results': initial,
            'shared_past_actual_probe_errors': read(actor.OUT / 'acquisition/scored_results.json'),
            'shared_past_source_reviews': [review(r['source'], r.get('grounded', {}))
                for r in read(actor.OUT / 'acquisition/scored_results.json')['rows']],
            'error_feedback_by_id': {f'B{batch}_actual_{i}': r for i, r in enumerate(initial)},
            'shared_factual_representation_not_a_new_method': True,
            'prior_B8_and_three_probe_sources_exposed_not_first_exposure': True,
            'new_DEV_TEST_information': False,
            'instruction': 'Repair the actual reusable observation schemas AND conversion code, including ordinary payment versus annual income, native event IDs/roles, exact statutory bases, and question/source separation. Do not assert parents, marriage facts, joint returns, exact151 negatives or payment episodes that the source does not state. A generic graph with correct arity but invented roles is not a successful repair. Both arms have all same source counterevidence and can adopt any equally expressive schema. Coverage contracts must describe actual whole-family ability, not merely list emitted symbols. Preserve known useful local components. Do not branch on source IDs or native answers.'}
        immutable_json(path, task)
    task = read(path)
    assert not strict_output_schema_issues(actor.acquisition.SCHEMA)

    def one(arm):
        target = OUT / f'B{batch}' / arm / 'teacher.json'
        if target.exists():
            return
        mode = ('Decompose revisions into paired schema/conversion versions. The host can recombine newly acquired components with existing local repairs using actual reads and the same source/native feedback.'
            if arm == ARMS[0] else 'Independently propose the two strongest ordinary teacher updates; the best complete candidate is selected. All same modular code, coverage reasoning and joint repairs are allowed. Do not weaken the control.')
        # Each arm updates its own current seed, while both have the identical
        # lawful evidence and access to the competing current seed.
        payload = {**task, 'seed_for_this_arm': libraries[arm]}
        system = actor.acquisition.SYSTEM.replace('Both arms have the same seed, full author program,',
            'Both arms share the original B8 seed and exposure, full author program,')
        response = FrozenTeacher(ledger, OUT, protocol['teacher_profile']).propose(
            RUN + f':B{batch}:' + arm + ':update', source_ids=[s for s in protocol['sources'] if s in kernels],
            system_prompt=system + '\n' + mode + '\n' + INSTRUCTION + '\n' + PROGRAM_INSTRUCTION,
            user_prompt=json.dumps(pack_programs(payload), ensure_ascii=False, separators=(',', ':')),
            output_schema=actor.acquisition.SCHEMA)
        immutable_json(target, response)
        print(json.dumps({'batch': batch, 'teacher_saved': arm}), flush=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = [pool.submit(one, arm) for arm in ARMS]
        for job in jobs:
            job.result()


def candidates(base, response, arm):
    result = {arm + '/retained': deepcopy(base)}
    for i, proposal in enumerate(response['value']['candidates']):
        try:
            result[arm + '/' + str(i)] = actor.candidate_library(base, proposal)
        except (ValueError, KeyError, TypeError) as error:
            result[arm + '/invalid_' + str(i)] = {'proposal_error': type(error).__name__ + ': ' + str(error)}
    if arm == ARMS[0] and arm + '/0' in result and arm + '/1' in result:
        left, right = result[arm + '/0'], result[arm + '/1']
        index = {c['id']: deepcopy(c) for c in left['components']}
        new = [c for c in right['components'] if c['id'] not in index]
        if new:
            index.update({c['id']: deepcopy(c) for c in new})
            result[arm + '/recombined'] = {**deepcopy(left), 'components': list(index.values())}
    return result


def run(stop):
    protocol, ledger = setup()
    client = FrozenExecutor(ledger, OUT, protocol['executor_profile'])
    client.exact_replay_roots = [OUT, actor.OUT, ROOT / 'artifacts/legal_skill_evolution_mixed_case_actor_givens6_20261114']
    public = {s['key']: s for s in read(actor.acquisition.previous.parent.OUT / 'SARA_corrected_TRAIN_views.json')}
    kernels = {r['source']: actor.acquisition.current_case_interface(r['kernel'])
        for r in read(actor.acquisition.previous.parent.OUT / 'SARA_native_kernel_bank.json')}
    grading = read(actor.acquisition.previous.parent.PREPARED / 'grading.json')
    seed = actor.libraries()
    libraries = {arm: seed[arm + '/0'] for arm in ARMS}
    immutable_json(OUT / 'warm_start_receipt.json', {
        'libraries': {a: digest(l) for a, l in libraries.items()},
        'broad_graph_native3of3_not_accepted_as_source_semantics': True,
        'known_local_errors_remain_explicit_TRAIN_feedback': True,
        'not_new_blind_TRAIN': True, 'not_goal_complete': True})
    for batch, keys in enumerate(protocol['batches'][:stop], 1):
        checkpoint = OUT / f'B{batch}/checkpoint.json'
        if checkpoint.exists():
            state = read(checkpoint)
            libraries = {a: read(ROOT / state['libraries'][a]['path']) for a in ARMS}
            continue
        current = [sid for sid in keys if sid in kernels]
        inherited_routes(batch, keys)
        initial = []
        for sid in current:
            for arm in ARMS:
                row = actor.execute_one(client, protocol, arm, libraries[arm], sid, kernels[sid], public[sid], f'B{batch}/initial')
                initial.append(scored(row, public, grading))
                if arm == ARMS[0]:
                    matched_read(client, protocol, batch, libraries[arm], row, public[sid], kernels[sid])
        immutable_json(OUT / f'B{batch}/initial_scored_results.json', {'rows': initial})
        acquire(protocol, ledger, batch, libraries, initial, public, kernels, grading)
        selected = {}
        for arm in ARMS:
            bank = candidates(libraries[arm], read(OUT / f'B{batch}' / arm / 'teacher.json'), arm)
            choices = []
            for name, library in bank.items():
                if library.get('proposal_error'):
                    immutable_json(OUT / f'B{batch}/invalid_proposals' / (name + '.json'), library)
                    continue
                try:
                    validate(library, kernels[current[0]])
                except (ValueError, KeyError, TypeError) as error:
                    immutable_json(OUT / f'B{batch}/invalid_proposals' / (name + '.json'), {'error': str(error)})
                    continue
                immutable_json(OUT / f'B{batch}/candidate_libraries' / (name + '.json'), library)
                rows = [scored(actor.execute_one(client, protocol, name, library, sid,
                    kernels[sid], public[sid], f'B{batch}/post'), public, grading) for sid in current]
                metrics = {'partial_source_failures': sum(r['partial_source_review']['failures'] for r in rows),
                    'native_correct': sum(r['native_score']['correct'] for r in rows),
                    'unresolved': sum(not r['execution']['handled'] for r in rows),
                    'logical_component_reads': sum(len(r['reads']) for r in rows)}
                immutable_json(OUT / f'B{batch}/candidate_scores' / (name + '.json'), {'metrics': metrics, 'rows': rows})
                choices.append((metrics['partial_source_failures'], -metrics['native_correct'],
                    metrics['unresolved'], metrics['logical_component_reads'], name, library))
            if not choices:
                raise ValueError('No executable retained or proposed library for ' + arm)
            chosen = min(choices, key=lambda row: row[:-1])
            libraries[arm] = chosen[-1]
            path = OUT / f'B{batch}' / arm / 'library.json'
            immutable_json(path, libraries[arm])
            selected[arm] = {'path': str(path.relative_to(ROOT)), 'sha256': digest(libraries[arm]),
                'candidate': chosen[-2], 'known_partial_source_failures': chosen[0],
                'native_correct': -chosen[1], 'unresolved': chosen[2],
                'not_full_semantic_or_novelty_certification': True}
        immutable_json(checkpoint, {'batch': batch, 'libraries': selected,
            'same_original_mixed_sources': keys, 'learning_branches': current,
            'completed_C_history_and_boundary_cache_references': {
                'C': 'artifacts/legal_skill_evolution_source_count_bias_repair_20261115/result.json',
                'unchanged_boundary': str((shared.OUT / f'B{batch}/checkpoint.json').relative_to(ROOT))},
            'all_16_mothers_in_queue_but_only_SARA_observation_update_here': True,
            'goal_complete': False})
        print(json.dumps({'mixed_batch_complete': batch, 'selected': selected}), flush=True)
    immutable_json(OUT / f'completed_through_B{stop}.json', {'last_batch': stop,
        'original_mixed_mothers': sum(len(b) for b in protocol['batches'][:stop]),
        'new_observation_learning_datasets': ['SARA_v2_Binary'],
        'C_completed_history_reused': True, 'boundary_cached_not_new_mechanism_success': True,
        'not_a_two_contribution_acceptance': True, 'DEV_TEST_opened': False, 'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stop', type=int, choices=range(1, 9), default=8)
    args = parser.parse_args()
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        run(args.stop)
