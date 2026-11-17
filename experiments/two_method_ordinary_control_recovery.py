"""Recover the fixed ordinary candidate pool after token-accounting failure.

No teacher calls, candidate additions or source changes. Re-evaluate the same
three preserved programs on original D0, freeze, then evaluate the remaining
fixed roles. Preserve every older prediction and failed physical request.
"""
import argparse
import json
from pathlib import Path

from experiments import two_method_ordinary_control as ordinary
from legal_skill_guard.paired_interfaces.control_accounting import TokenBudgetExecutor, settled_token_usage
from legal_skill_guard.paired_interfaces.control_learning import program_from_proposal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest

ROOT, BASE = ordinary.ROOT, ordinary.BASE
RUN_ID = 'two_method_ordinary_control_v1_20261117'


def prepare():
    original, prepared, lock, sources, train = ordinary.prepare()
    original_protocol = ordinary.read(original / 'protocol.json')
    if original_protocol['resolved_executor_budget'] != ordinary.primary_budget(lock):
        raise ValueError('The original primary comparison cap changed')
    for dataset, expected in prepared['dataset_tasks_sha256'].items():
        if digest(ordinary.read(original / 'teacher_inputs' / (dataset + '.json'))) != expected:
            raise ValueError('The original shared teacher evidence changed')
    paths = [str(Path(__file__).relative_to(ROOT)),
             'legal_skill_guard/paired_interfaces/control_accounting.py']
    bindings = {**prepared['source_sha256'], **{name: ordinary.sha(ROOT / name) for name in paths}}
    protocol = {'experiment': 'fixed_ordinary_pool_accounting_recovery_v2',
        'source_sha256': bindings, 'original_artifact_root': str(original.relative_to(ROOT)),
        'original_protocol_sha256': ordinary.sha(original / 'protocol.json'),
        'original_ledger_run_id_and_physical_cache_retained': RUN_ID,
        'executor': prepared['executor'], 'teacher': prepared['teacher'],
        'resolved_executor_budget': original_protocol['resolved_executor_budget'],
        'teacher_request_ceiling_total_including_original_acquisition': 20,
        'new_teacher_requests': 0, 'new_candidates': 0,
        'candidate_pool': 'the same three preserved teacher programs per dataset',
        'selection': 'original D0 mother-macro,stable earlier-candidate ties,before later-role evaluation',
        'old_failed_predictions_not_overwritten': True,
        'old_failed_physical_request_identities_never_redispatched': True,
        'unknown_usage_accounting': 'charge the original full serving-context token bound per unmetered failure',
        'earlier_repair_feedback_was_partly_affected_by_accounting_failure': True}
    out = BASE / 'ordinary_control_accounting_recovery_v2' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name in paths:
        target = out / 'source_snapshot' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        raw = (ROOT / name).read_bytes()
        if target.exists() and target.read_bytes() != raw:
            raise ValueError('A recovery source snapshot changed')
        if not target.exists():
            target.write_bytes(raw)
    frozen = {}
    for dataset in sorted(prepared['dataset_tasks_sha256']):
        candidates = []
        for index in range(3):
            path = original / 'teacher_outputs' / dataset / ('program_' + str(index) + '.json')
            response = ordinary.read(path)
            failure = None
            try:
                program = program_from_proposal(response['value'], sources['sources']['train'])
            except Exception as error:
                failure = type(error).__name__ + ': ' + str(error)
                program = {'predicates': [], 'extractors': [],
                           'composition': 'def compose(inputs, predict, extractors):\n    return None\n'}
            candidates.append({'index': index, 'program': program, 'original_validation_failure': failure,
                'teacher_proposal_path': str(path.relative_to(ROOT)),
                'teacher_proposal_sha256': ordinary.sha(path),
                'original_teacher_physical_call_id': response['physical_call_id']})
        frozen[dataset] = candidates
    immutable_json(out / 'frozen_candidate_pool.json', frozen)
    return original, out, protocol, prepared, lock, sources, train, frozen


def run():
    original, out, protocol, prepared, lock, sources, train, frozen = prepare()
    ledger = EvolutionLedger(ordinary.LEDGER, run_id=RUN_ID, sources=sources['sources'],
        binding={'protocol_sha256': ordinary.sha(original / 'protocol.json')})
    with ledger.transaction() as db:
        teachers = db.execute('SELECT status,count(*) FROM calls WHERE role=? AND id LIKE ? GROUP BY status',
                              ('teacher', RUN_ID + ':%')).fetchall()
    if teachers != [('completed', 20)]:
        raise ValueError('Recover only the complete fixed original20-teacher candidate pool')
    executor = TokenBudgetExecutor(FrozenExecutor(ledger, out, prepared['executor']),
        protocol['resolved_executor_budget']['input_plus_output_token_cap'])
    selected = {}
    for dataset, candidates in frozen.items():
        history = []
        rows = [row for row in lock['rows'] if row['dataset'] == dataset and row['role'] == 'development']
        for candidate in candidates:
            stage = dataset + '_candidate_' + str(candidate['index'])
            evaluation = ordinary.evaluate(candidate['program'], rows, train, executor, out, stage, 'development')
            history.append({**candidate, 'evaluation': evaluation})
        winner = max(history, key=lambda value: (value['evaluation']['mother_macro'], -value['index']))
        selected[dataset] = {'program': winner['program'], 'candidate_index': winner['index'],
            'fixed_development_mother_macro': winner['evaluation']['mother_macro'],
            'fixed_original_candidate_pool_only': True}
        immutable_json(out / 'frozen_libraries' / (dataset + '.json'), selected[dataset])
    immutable_json(out / 'frozen_libraries.json', {'datasets': selected,
        'calibration_or_structure_evaluation_feedback_used_for_selection': False,
        'new_teacher_requests': 0, 'new_candidates': 0})
    for role in ('calibration', 'structure_evaluation'):
        for dataset, selection in selected.items():
            rows = [row for row in lock['rows'] if row['role'] == role and row['dataset'] == dataset]
            if rows:
                ordinary.evaluate(selection['program'], rows, train, executor, out, dataset + '_' + role, role)
    for path, expected in protocol['source_sha256'].items():
        if ordinary.sha(ROOT / path) != expected:
            raise ValueError('A frozen recovery binding changed: ' + path)
    usage = settled_token_usage(ledger, RUN_ID, context_tokens=prepared['executor']['context_tokens'])
    if usage['pending_requests'] or usage['conservatively_charged_input_plus_output_tokens'] > executor.token_cap:
        raise ValueError('The repaired fixed evaluation is not safely within its original token cap')
    terminal = {'status': 'fixed_ordinary_control_evaluated',
        'accounting_recovery_artifact_root': str(out.relative_to(ROOT)),
        'authoritative_final_frozen_libraries': str((out / 'frozen_libraries.json').relative_to(ROOT)),
        'original_failed_controller_session_exit_code': 1,
        'executor_usage': usage, 'teacher_request_counts': teachers,
        'new_teacher_requests': 0, 'new_candidate_count': 0,
        'original_predictions_and_frozen_libraries_preserved': True,
        'earlier_teacher_repairs_partly_affected_by_accounting_failure': True,
        'complete_two_method_goal': False, 'SCOPE_control_completed': False}
    immutable_json(out / 'terminal.json', terminal)
    immutable_json(original / 'terminal.json', terminal)
    print(json.dumps({'ordinary_control_accounting_recovery_complete': True,
        'artifact_root': str(out.relative_to(ROOT)), 'new_teacher_requests': 0}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        _, out, protocol, *_ = prepare()
        print(json.dumps({'prepared': str(out.relative_to(ROOT)),
            'new_teacher_requests': 0, 'new_model_requests': 0}, ensure_ascii=False))
    else:
        run()


if __name__ == '__main__':
    main()
