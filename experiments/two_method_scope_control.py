"""One fixed, budget-matched SCOPE adaptation on the original pilot mothers.

Four teacher requests per library: joint seed rationales/trace analysis/program,
one local plus one systemic adversary, a separate blind labeler, then one final
trace-driven revision. There is no resampling, threshold search or extra round.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import time

from experiments import two_method_ordinary_control as ordinary
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import (
    direct_program, pack_teacher_payload, program_from_proposal)
from legal_skill_guard.paired_interfaces.control_accounting import TokenBudgetExecutor, settled_token_usage
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.control_tools import legal_tools
from legal_skill_guard.paired_interfaces.scope_learning import (
    admit_variants, adversary_schema, blind_verifier_payload, make_variant,
    revision_schema, verification_schema)
from legal_skill_guard.paired_interfaces.scope_replay import attribute
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT, BASE, LEDGER = ordinary.ROOT, ordinary.BASE, ordinary.LEDGER
SYSTEM = ordinary.SYSTEM + '''
This arm is the budget-matched SCOPE adaptation. Start from the single native
predicate seed, then use actual weak predicate inputs, labels and full native
TRAIN feedback to attribute errors. Counterfactual replay changes finite label
leaves in pure composition, never invents unobserved weak responses; numeric or
span errors and unseen branches may be unsupported. Treat it as diagnostic
attribution, not a semantic oracle. Contrast correctly classified seed cases.
Ground each revision in an explicit policy clause, definition or exception.
The program may change predicate wording, number, extractors and composition.
Use self-contained fixed-label predicates (enum/boolean), deterministic
extractors for arithmetic/spans, and the shared frozen law tools. Do not ask
the weak model for reasoning. Native mode remains available for a whole task.
The original D0 mother-macro selects the best program across rounds; never
select by accuracy on the growing synthetic pool. If a round does not improve,
backtrack to the best candidate and propose a substantively different revision.
Supply a source-grounded rationale for every fixed development mother in each
revision response. There are exactly two learned candidates after the seed.
'''
BLIND_SYSTEM = '''Independently label edited TRAIN examples using only their
complete public legal policy, facts, questions and answer contract. Judge every
native task. Do not assume that a well-written example is supported. If facts
or policy are inconsistent or insufficient, say so in the support flag. The
native answer dict must use the exact current view IDs and answer types.
You do not receive the generator's intended answers, rationale, program or weak
predictions. Return the exact requested structured output. Repeated strings
may use a lossless text_table: resolve each {$shared_text:id} at the listed
referenced_string_paths to the full text_table[id] before reading the task.'''


def read(path):
    return ordinary.read(Path(path))


def prepare():
    shared_out, shared, lock, sources, train = ordinary.prepare()
    for schema in (revision_schema(), adversary_schema(), verification_schema()):
        if strict_output_schema_issues(schema):
            raise ValueError('SCOPE teacher output contract is not transport-ready')
    registry = BASE / 'scope_control_v1/active_protocol.json'
    if registry.exists():
        out = ROOT / read(registry)['artifact_root']
        protocol = read(out / 'prepared_protocol.json')
        for path, expected in protocol['source_sha256'].items():
            if ordinary.sha(ROOT / path) != expected:
                raise ValueError('An active SCOPE source binding changed: ' + path)
        return out, protocol, lock, sources, train
    binding = dict(shared['source_sha256'])
    for path in ('experiments/two_method_scope_control.py',
                 'legal_skill_guard/paired_interfaces/scope_replay.py',
                 'legal_skill_guard/paired_interfaces/control_accounting.py',
                 'legal_skill_guard/paired_interfaces/scope_learning.py'):
        binding[path] = ordinary.sha(ROOT / path)
    parents = {d: sorted(r['key'] for r in lock['rows']
                        if r['dataset'] == d and r['role'] == 'development')[0]
               for d in shared['dataset_tasks_sha256']}
    protocol = {'experiment': 'budget_matched_SCOPE_adaptation_pilot_v1',
        'source_sha256': binding, 'teacher': shared['teacher'], 'executor': shared['executor'],
        'ordinary_shared_artifact_root': str(shared_out.relative_to(ROOT)),
        'shared_information_sha256': shared['dataset_tasks_sha256'],
        'pilot_lock_sha256': ordinary.sha(BASE / 'pilot_lock.json'),
        'source_lock_sha256': ordinary.sha(BASE / 'prepared/source_lock.json'),
        'fixed_mother_roles': shared['fixed_mother_roles'], 'adversary_parents': parents,
        'adversary_slots_per_dataset': ['local', 'systemic'], 'maximum_synthetic_variants': 10,
        'synthetic_variants_are_not_new_independent_mothers_or_calibration_truth': True,
        'teacher_stages': ['seed_analysis_decomposition', 'local_and_systemic_adversaries',
                           'separate_blind_verification', 'second_analysis_decomposition'],
        'teacher_requests_per_dataset': 4, 'teacher_request_ceiling': 20,
        'candidates': ['fixed_monolithic_seed', 'first_decomposition', 'second_decomposition'],
        'candidate_selection': 'original D0 mother-macro, stable earlier-candidate ties',
        'counterfactual_design': {'max_label_edits': 2, 'max_replays_per_execution': 128,
            'unobserved_predicate_input': 'unsupported; never invent a weak response',
            'unbounded_numbers_and_spans': 'not enumerated',
            'exhaustive_global_attribution_claimed': False},
        'executor_budget_rule': shared['executor_budget_rule'],
        'unmetered_failure_accounting': 'charge original serving-context token bound;preserve missing actual usage',
        'adaptation_differences_from_paper': [
            'Two fixed revisions and ten preallocated source-derived variants within the ordinary arm 20-teacher budget, rather than eight optimizer rounds with adaptive counts',
            'Seed rationales and first analysis/decomposition combined in one teacher turn after seed execution',
            'Same authorized Codex teacher identity in separate stateless calls; no claim of independent human or different-model gold',
            'Bounded one/two finite-label-leaf replay; explicit unsupported numeric/span/novel-branch cases',
            'Native legal task bundle scoring and shared frozen legal RPC instead of original policy-enforcement datasets'],
        'all_generations_in_original_ledger': True, 'model_weights_updated': False,
        'no_M1_generated_candidate_pool': True,
        'calibration_structure_DEV_TEST_feedback_for_repairs': False}
    out = BASE / 'scope_control_v1' / digest(protocol)
    immutable_json(out / 'prepared_protocol.json', protocol)
    for path, expected in binding.items():
        raw = (ROOT / path).read_bytes()
        target = out / 'source_snapshot' / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('A prepared SCOPE snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    for dataset in shared['dataset_tasks_sha256']:
        task = read(shared_out / 'teacher_inputs' / (dataset + '.json'))
        if digest(task) != shared['dataset_tasks_sha256'][dataset]:
            raise ValueError('Shared original development evidence changed')
        immutable_json(out / 'teacher_inputs' / (dataset + '.json'), task)
    return out, protocol, lock, sources, train


def teacher_call(teacher, out, dataset, stage, payload, schema, source_ids, *, blind=False):
    target = out / 'teacher_outputs' / dataset / (stage + '.json')
    if target.exists():
        return read(target)
    system = BLIND_SYSTEM if blind else SYSTEM
    encoded = pack_teacher_payload(payload)
    identity = teacher.ledger.run_id + ':teacher:' + digest([dataset, stage, system, encoded, schema])
    immutable_json(target.with_name(stage + '_input.json'), encoded)
    result = teacher.propose(identity, source_ids=source_ids, system_prompt=system,
        user_prompt=json.dumps(encoded, ensure_ascii=False, sort_keys=True), output_schema=schema)
    record = {'physical_call_id': identity, 'stage': stage, 'value': result['value'],
              'blind_to_intended_labels_and_generator_rationales': blind}
    immutable_json(target, record)
    return record


def candidate(response, source_ids, development_ids, out, stage):
    try:
        rationales = response['value']['seed_rationales']
        if (len(rationales) != len(development_ids)
                or {r['source'] for r in rationales} != set(development_ids)):
            raise ValueError('Seed rationales must cover exactly the fixed development mothers')
        return program_from_proposal(response['value'], source_ids), None
    except Exception as error:
        failure = {'physical_teacher_call_id': response['physical_call_id'],
                   'error': type(error).__name__ + ': ' + str(error)}
        immutable_json(out / 'invalid_programs' / (stage + '.json'), failure)
        return {'predicates': [], 'extractors': [],
                'composition': 'def compose(inputs, predict, extractors):\n    return None\n'}, failure


def attribution_feedback(result):
    """Reference repeated offline callbacks to full actual traces in feedback.

    This never removes an actual weak trace: the complete executions remain in
    search_history/evaluation. The full offline replays also remain on disk.
    """
    reports = []
    for report in result['source_reports']:
        compact = {k: v for k, v in report.items() if k not in ('baseline', 'interventions')}
        compact['interventions'] = [{
            **{k: v for k, v in intervention.items() if k not in ('events', 'worker_stderr')},
            'recorded_callback_references': [{
                'type': e['type'], 'recorded_trace_index': e.get('recorded_trace_index'),
                'physical_call_id': e.get('physical_call_id'),
                'input_sha256': digest(e['input']), 'value': e['value'],
                **({'tool_id': e['tool_id'], 'input': e['input'],
                    'binding_sha256': e['binding_sha256']} if e['type'] == 'legal_tool' else {})}
                for e in intervention['events']]}
            for intervention in report['interventions']]
        reports.append(compact)
    return {**result, 'source_reports': reports,
            'offline_repeated_predicate_inputs_reference_complete_actual_traces': True}


def attribution(program, evaluation, train, executor, out, stage, targets=None):
    path = out / 'attribution' / (stage + '.json')
    if path.exists():
        return attribution_feedback(read(path))
    targets = targets if targets is not None else {
        source: {view: row['answer'] for view, row in grading.items()}
        for source, grading in read(ordinary.GRADING).items()}
    reports = []
    for prediction in evaluation['predictions']:
        source = train[prediction['source']]
        bundle = source_bundle(source)
        tools, assets = legal_tools(source, bundle)
        runtime = ControlProgramRuntime(executor, out, max_calls=executor.token_cap,
                                        shared_assets=assets, legal_tools=tools)
        message_path = runtime.execution_path(program, source, bundle).with_name('input.json')
        execution = prediction.get('execution')
        if not execution or not message_path.exists():
            report = {'baseline_reproduced': False, 'reason': 'No complete actual execution input',
                      'interventions': [], 'new_model_requests': 0}
        else:
            report = attribute(read(message_path), execution, legal_tools=tools)
        for result in report['interventions']:
            result['matches_recorded_target_exactly'] = bool(result['supported'] and
                digest(result['answer']) == digest(targets[source['key']]))
        reports.append({'source': source['key'], 'target_answer': targets[source['key']], **report})
    result = {'stage': stage, 'source_reports': reports,
              'recorded_target_match_is_sufficient_not_necessary_for_native_score': True,
              'counterfactuals_are_not_actual_weak_observations': True, 'new_model_requests': 0}
    immutable_json(path, result)
    return attribution_feedback(result)


def evaluate_variant(program, variant, executor, out, dataset):
    path = out / 'variant_predictions' / dataset / (variant['slot'] + '.json')
    source = variant['source']
    bundle = source_bundle(source)
    tools, assets = legal_tools(source, bundle)
    runtime = ControlProgramRuntime(executor, out, max_calls=executor.token_cap,
                                    shared_assets=assets, legal_tools=tools)
    if path.exists():
        record = read(path)
    else:
        try:
            execution = runtime.run(program, source, bundle)
            error = execution['error']
        except Exception as exc:
            error = type(exc).__name__ + ': ' + str(exc)
            execution_path = runtime.execution_path(program, source, bundle)
            execution = read(execution_path) if execution_path.exists() else None
        record = {'source': source['key'], 'slot': variant['slot'], 'execution': execution,
                  'answer': execution['answer'] if execution else None, 'error': error,
                  'target_is_teacher_verified_training_variant': True}
        immutable_json(path, record)
    synthetic_train = {source['key']: source}
    report = attribution(program, {'predictions': [record]}, synthetic_train, executor, out,
        dataset + '_synthetic_' + variant['slot'], {source['key']: variant['independent_answer']})
    return {'prediction': record, 'attribution': report,
            'verified_target': variant['independent_answer'],
            'verification_rationale': variant['independent_verification']['rationale']}


def freeze_best(history):
    return max(history, key=lambda h: (h['evaluation']['mother_macro'], -h['index']))


def run():
    out, prepared, lock, sources, train = prepare()
    shared_out = ROOT / prepared['ordinary_shared_artifact_root']
    if not (shared_out / 'terminal.json').exists():
        raise RuntimeError('Wait for the fixed ordinary arm to settle before SCOPE dispatch')
    if read(shared_out / 'terminal.json')['status'] != 'fixed_ordinary_control_evaluated':
        raise ValueError('Ordinary predecessor has not completed its fixed evaluation')
    budget = ordinary.primary_budget(lock)
    protocol = {**prepared, 'resolved_executor_budget': budget}
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(BASE / 'scope_control_v1/active_protocol.json', {
        'artifact_root': str(out.relative_to(ROOT)), 'protocol_sha256': ordinary.sha(out / 'protocol.json')})
    for path, expected in prepared['source_sha256'].items():
        if ordinary.sha(ROOT / path) != expected:
            raise ValueError('SCOPE implementation binding changed before dispatch: ' + path)
    ledger = EvolutionLedger(LEDGER, run_id='two_method_scope_control_v1_20261117',
        sources=sources['sources'], binding={'protocol_sha256': ordinary.sha(out / 'protocol.json')})
    teacher = FrozenTeacher(ledger, out, prepared['teacher'])
    executor = TokenBudgetExecutor(FrozenExecutor(ledger, out, prepared['executor']), budget['input_plus_output_token_cap'])
    selections, shared_variants = {}, []
    for dataset in sorted(prepared['shared_information_sha256']):
        task = read(out / 'teacher_inputs' / (dataset + '.json'))
        ids = [example['source'] for example in task['fixed_development_examples']]
        rows = [r for r in lock['rows'] if r['dataset'] == dataset and r['role'] == 'development']
        seed = direct_program()
        initial = ordinary.evaluate(seed, rows, train, executor, out, dataset + '_seed', 'development')
        history = [{'index': 0, 'program': seed, 'evaluation': initial, 'fixed_monolithic_seed': True,
                    'attribution': attribution(seed, initial, train, executor, out, dataset + '_seed')}]
        first = teacher_call(teacher, out, dataset, 'seed_analysis_decomposition',
            {**task, 'instruction': 'Write seed rationales, analyze actual errors and correct contrasts, then produce a clause-grounded first decomposition. This fixed budget combines rationale/analyzer/decomposer roles in one turn.',
             'search_history': history}, revision_schema(), ids)
        program, failure = candidate(first, sources['sources']['train'], ids, out, dataset + '_first')
        evaluation = ordinary.evaluate(program, rows, train, executor, out, dataset + '_first', 'development')
        history.append({'index': 1, 'program': program, 'evaluation': evaluation, 'proposal': first,
            'validation_failure': failure,
            'attribution': attribution(program, evaluation, train, executor, out, dataset + '_first')})
        current = freeze_best(history)
        parent = train[prepared['adversary_parents'][dataset]]
        adversary = teacher_call(teacher, out, dataset, 'local_and_systemic_adversaries',
            {**task, 'instruction': 'Generate exactly one local and one systemic variant of this fixed parent, with no resampling. Local: target a declared predicate using its actual input traces and a policy-clause mismatch. Systemic: target omitted/misrouted policy interactions in the full composition. Give literal before/after substitutions and an intended native answer dict for every current task. Only edit facts for SARA/Airline, the Facts section for OpenExempt, or contract source_text for CNI/MAUD. Never edit supplied laws, solved givens, questions, answer schemas or IDs. CNI edits must not cross sentence boundaries. Each before literal is substituted in all editable public occurrences of this parent. Do not include an answer or rationale in edited facts.',
             'fixed_parent_source': parent['key'], 'parent_input': source_bundle(parent),
             'current_best_program': current['program'], 'actual_seed_pool_and_weak_traces': current['evaluation'],
             'previous_programs_and_scores': history}, adversary_schema(), ids)
        proposed, invalid = [], []
        specifications = adversary['value']['variants']
        if {s['slot'] for s in specifications} != {'local', 'systemic'}:
            invalid.append({'reason': 'Adversary did not supply both unique fixed slots'})
        else:
            for spec in specifications:
                try:
                    if spec['slot'] == 'local' and spec['target_predicate'] not in {
                            p['id'] for p in current['program']['predicates']}:
                        raise ValueError('Local adversary must target an actual named predicate')
                    proposed.append(make_variant(parent, spec, spec['slot']))
                except Exception as error:
                    invalid.append({'slot': spec['slot'], 'error': type(error).__name__ + ': ' + str(error),
                                    'specification': spec})
        immutable_json(out / 'variants' / dataset / 'proposed.json', {'variants': proposed, 'invalid': invalid,
                       'extra_generation_or_resampling': False})
        verification = teacher_call(teacher, out, dataset, 'separate_blind_verification',
            blind_verifier_payload(proposed, task['shared_legal_assets']), verification_schema(),
            [parent['key']], blind=True)
        try:
            checked = admit_variants(proposed, verification['value'])
        except Exception as error:
            checked = [{**variant, 'admitted': False,
                        'verification_error': type(error).__name__ + ': ' + str(error)} for variant in proposed]
        immutable_json(out / 'variants' / dataset / 'verified.json', {'variants': checked,
            'blind_verification_physical_call_id': verification['physical_call_id']})
        admitted = [v for v in checked if v['admitted']]
        shared_variants.extend(admitted)
        variant_feedback = [evaluate_variant(current['program'], v, executor, out, dataset) for v in admitted]
        second = teacher_call(teacher, out, dataset, 'second_analysis_decomposition',
            {**task, 'instruction': 'Analyze complete seed and admitted adversarial weak traces and counterfactual replay. Contrast correct seeds. Backtrack to the best original-D0 program if the last revision did not improve, and propose a substantively different policy-grounded revision. Synthetic teacher targets guide training but never replace D0 for selection. No more variants or rounds are available.',
             'search_history': history, 'current_best_program': current['program'],
             'admitted_variants_and_verification': admitted, 'actual_adversarial_feedback': variant_feedback,
             'rejected_variants_and_errors': [v for v in checked if not v['admitted']] + invalid}, revision_schema(), ids)
        program, failure = candidate(second, sources['sources']['train'], ids, out, dataset + '_second')
        evaluation = ordinary.evaluate(program, rows, train, executor, out, dataset + '_second', 'development')
        history.append({'index': 2, 'program': program, 'evaluation': evaluation, 'proposal': second,
                        'validation_failure': failure})
        winner = freeze_best(history)
        selections[dataset] = {'program': winner['program'], 'candidate_index': winner['index'],
            'fixed_development_mother_macro': winner['evaluation']['mother_macro'],
            'admitted_synthetic_variants': len(admitted), 'new_independent_mothers': 0}
        immutable_json(out / 'search_history' / (dataset + '.json'), history)
        immutable_json(out / 'frozen_libraries' / (dataset + '.json'), selections[dataset])
    immutable_json(out / 'frozen_libraries.json', {'datasets': selections,
        'selection_uses_only_original_D0': True, 'growing_pool_scores_not_compared': True,
        'calibration_or_structure_evaluation_feedback_used': False})
    immutable_json(out / 'shared_training_variants.json', {'variants': shared_variants,
        'available_to_all_later_formal_arms': True, 'not_retroactively_used_by_ordinary_pilot': True,
        'not_independent_mothers_or_reference_graphs_or_calibration': True})
    for role in ('calibration', 'structure_evaluation'):
        for dataset, selection in selections.items():
            rows = [r for r in lock['rows'] if r['role'] == role and r['dataset'] == dataset]
            if rows:
                ordinary.evaluate(selection['program'], rows, train, executor, out, dataset + '_' + role, role)
    with ledger.transaction() as db:
        counts = db.execute('SELECT status,count(*) FROM calls WHERE role=? AND id LIKE ? GROUP BY status',
                            ('teacher', ledger.run_id + ':%')).fetchall()
    if counts != [('completed', 20)]:
        raise ValueError('Fixed SCOPE teacher schedule/accounting is incomplete')
    immutable_json(out / 'terminal.json', {'status': 'fixed_SCOPE_adaptation_evaluated',
        'executor_usage': settled_token_usage(ledger, ledger.run_id,
            context_tokens=prepared['executor']['context_tokens']), 'teacher_request_counts': counts,
        'admitted_variants': len(shared_variants), 'complete_two_method_goal': False})
    print(json.dumps({'scope_control_complete': True, 'artifact_root': str(out)}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--wait-for-ordinary-pid', type=int)
    args = parser.parse_args()
    if args.prepare:
        out, protocol, *_ = prepare()
        print(json.dumps({'prepared': str(out), 'new_model_requests': 0,
                          'teacher_request_ceiling': protocol['teacher_request_ceiling']}, ensure_ascii=False))
        return
    if args.wait_for_ordinary_pid is not None:
        proc = Path('/proc') / str(args.wait_for_ordinary_pid)
        if proc.exists():
            commands = (proc / 'cmdline').read_bytes().split(b'\x00')
            if not any(command in commands for command in (
                    b'experiments.two_method_ordinary_control',
                    b'experiments.two_method_ordinary_control_recovery')):
                raise ValueError('Proposed predecessor is not the actual ordinary control')
            start = (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19]
        else:
            start = None
        print(json.dumps({'event': 'waiting_for_actual_ordinary_exit', 'host_pid': args.wait_for_ordinary_pid,
                          'observed_start_ticks': start, 'new_model_requests': 0}), flush=True)
        while start is not None:
            try:
                if (proc / 'stat').read_text().rsplit(')', 1)[1].split()[19] != start:
                    break
            except FileNotFoundError:
                break
            time.sleep(2)
        os.execv(sys.executable, [sys.executable, '-m', 'experiments.two_method_scope_control'])
    run()


if __name__ == '__main__':
    main()
