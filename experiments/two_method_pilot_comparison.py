"""Compare already frozen pilot arms on the identical complete native cohort.

No generation, grading, reselection, teacher-reference repair or new trials.
The ordinary accounting fault and pilot information differences stay explicit.
"""
import json
import math
from pathlib import Path

from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces.pilot_metrics import summarize
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


MAIN = BASE / 'pilot_evaluation_v1/3a847ef33221884de63f234bc6e2ce78f1e19f2265cefc58fa4463e079f8a650'
CONTROLS = {
    'ordinary_teacher': BASE / 'ordinary_control_accounting_recovery_v2/cc60703fc6b75b26d167c4005af59c0664ea7177ee448c7dc2faf9e210cf5e81',
    'budget_matched_SCOPE': BASE / 'scope_control_v1/7a1f8dd8ba69375b5b1310fbcc6551650e92af5b8ceca41554596d21f7c5883f',
}


def control_rows(evaluation, dataset, role, sources):
    if evaluation['role'] != role or not evaluation['all_fixed_sources_in_denominator']:
        raise ValueError('A control evaluation lost its fixed role/denominator')
    if {row['source'] for row in evaluation['scores']} != set(sources):
        raise ValueError('A control score cohort differs from the locked main cohort')
    if len(evaluation['scores']) != len(sources):
        raise ValueError('A control mother was counted twice')
    rows = []
    for mother in evaluation['scores']:
        expected = {view['id'] for view in sources[mother['source']]['views']}
        if set(mother['native']) != expected:
            raise ValueError('A native task is missing from a control denominator')
        actual_mean = math.fsum(value['grade'] for value in mother['native'].values()) / len(expected)
        if not math.isclose(actual_mean, mother['mother_score'], abs_tol=1e-12):
            raise ValueError('A saved control mother score cannot be reproduced')
        for view, value in mother['native'].items():
            rows.append({'dataset': dataset, 'role': role, 'source': mother['source'],
                         'view': view, 'grade': value['grade'],
                         'handled': not value.get('unresolved_or_failed', False)})
    return rows


def run():
    lock_path = BASE / 'pilot_lock.json'
    public_path = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
    lock = read(lock_path)
    train = {source['key']: source for source in read(public_path)}
    seal_path = MAIN / 'selection_freeze.json'
    seal = read(seal_path)
    if seal['calibration_or_structure_evaluation_grades_used_for_main_selection']:
        raise ValueError('Main choices must precede held-out evaluation')
    main_scores = MAIN / 'all_candidate_native_scores.json'
    selected = [row for row in read(main_scores)
                if row['plan'] == seal['M1_dataset_choices'][row['dataset']]['plan']]
    bindings = {str(p.relative_to(ROOT)): sha(p)
                for p in (lock_path, public_path, seal_path, main_scores, Path(__file__))}
    control_libraries = {}
    for arm, root in CONTROLS.items():
        terminal_path = root / 'terminal.json'
        terminal = read(terminal_path)
        if terminal['executor_usage']['pending_requests']:
            raise ValueError('A pilot control has unsettled requests')
        library_path = root / 'frozen_libraries.json'
        library = read(library_path)
        if library.get('calibration_or_structure_evaluation_feedback_used', False):
            raise ValueError('A control selected using held-out feedback')
        control_libraries[arm] = library['datasets']
        bindings.update({str(p.relative_to(ROOT)): sha(p) for p in (terminal_path, library_path)})
    summaries = []
    for dataset, role in sorted({(row['dataset'], row['role']) for row in lock['rows']}):
        sources = {row['key']: train[row['key']] for row in lock['rows']
                   if (row['dataset'], row['role']) == (dataset, role)}
        expected = {(source, view['id']) for source, item in sources.items() for view in item['views']}
        main = [row for row in selected if (row['dataset'], row['role']) == (dataset, role)]
        summaries.append({'arm': 'M1_only', 'dataset': dataset, 'role': role, **summarize(main, expected)})
        for arm, root in CONTROLS.items():
            choice = control_libraries[arm][dataset]
            if role == 'development':
                index = choice['candidate_index']
                stage = (f'{dataset}_candidate_{index}' if arm == 'ordinary_teacher'
                         else dataset + '_' + ('seed', 'first', 'second')[index])
            else:
                stage = dataset + '_' + role
            path = root / 'scores' / (stage + '.json')
            bindings[str(path.relative_to(ROOT))] = sha(path)
            evaluation = read(path)
            rows = control_rows(evaluation, dataset, role, sources)
            summary = summarize(rows, expected)
            if not math.isclose(summary['mother_macro'], evaluation['mother_macro'], abs_tol=1e-12):
                raise ValueError('A saved control macro score cannot be reproduced')
            summaries.append({'arm': arm, 'dataset': dataset, 'role': role, **summary})
    protocol = {'experiment': 'frozen_fixed_pilot_three_arm_comparison_v1', 'sha256': bindings,
                'new_model_requests': 0, 'new_independent_trials': 0,
                'native_metrics': {'OpenExempt': 'official EC/EV F1', 'others': 'native exact match'},
                'unit': 'all native tasks averaged within each original mother,then mother macro',
                'no_cross_dataset_scalar_or_significance_claim': True,
                'ordinary_feedback_partly_affected_by_original_accounting_failure': True,
                'strict_information_parity_not_established': True,
                'information_boundary': 'Controls learned on original8 D0 mothers;M2 additionally used16 calibration source-only references.All arms had shared legal tools and original token ceilings.',
                'M2_selection_remains_tied_and_not_an_independent_nontrivial_arm': True,
                'formal_training_DEV_TEST_or_goal_completion': False}
    out = BASE / 'pilot_comparison_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(out / 'report.json', {'metrics': summaries, 'protocol_sha256': digest(protocol),
                                      'new_model_requests': 0, 'complete_two_method_goal': False})
    print(json.dumps({'artifact_root': str(out), 'dataset_role_arm_rows': len(summaries),
                      'structure_evaluation': [{key: row[key] for key in
                          ('arm', 'dataset', 'mothers', 'native_tasks', 'mother_macro')}
                          for row in summaries if row['role'] == 'structure_evaluation']}, ensure_ascii=False))


if __name__ == '__main__':
    run()
