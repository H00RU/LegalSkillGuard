"""Reconcile B1–B8 teacher decisions with the saved TRAIN libraries."""

import json
from collections import Counter

from experiments.convergence_formal_b1_fit import POINTER as B1_CONTROLS
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_b1_primary import POINTER as B1_PRIMARY
from experiments.convergence_formal_bootstrap import POINTER as BOOTSTRAP
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, M2, ORDINARY, pointer
from experiments.convergence_pilot_b0 import HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def finished(link, status):
    path = ROOT / read(link)['artifact_root']
    binding, terminal = (read(path / f) for f in ('binding.json', 'terminal.json'))
    if digest(binding) != path.name or terminal['status'] != status or terminal['TEST_opened']:
        raise ValueError('Use the exact finished TRAIN stage for the audit')
    return path, binding, terminal


def control_counts(rows, changed, first_batch):
    totals = Counter()
    for dataset, row in rows.items():
        totals['proposed'] += 1
        if row['status'] == 'invalid_teacher_candidate':
            totals['invalid'] += 1
            continue
        gain = (row['candidate_native_utility'] - row['original_native_utility']
                if first_batch else row['native_utility_delta'])
        totals['current_TRAIN_positive' if gain > 0 else 'current_TRAIN_negative' if gain < 0
               else 'current_TRAIN_tie'] += 1
        if row['selected'] == 'candidate':
            if gain <= 0 or dataset not in changed:
                raise ValueError('An accepted teacher change must match the positive fitted candidate')
            totals['accepted'] += 1
        elif row['selected'] == 'incumbent' and dataset not in changed:
            if gain > 0:
                prior = row.get('earlier_TRAIN_regression')
                if not prior or prior['passed']:
                    raise ValueError('A retained native-positive control needs its prior-TRAIN regression record')
                totals['positive_rejected_by_prior_TRAIN_guard'] += 1
        else:
            raise ValueError('The control decision disagrees with the journal')
    return dict(totals)


def run():
    root = ROOT / read(BOOTSTRAP)['artifact_root']
    study = read(root / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    first, _, first_end = finished(B1_CONTROLS, 'completed_two_B1_control_updates')
    primary, primary_binding, primary_end = finished(B1_PRIMARY, 'completed_all_five_B1_updates')
    if (primary_binding['stages']['controls']['root'] != str(first.relative_to(ROOT))
            or primary_binding['stages']['controls']['terminal_sha256'] != sha(first / 'terminal.json')
            or any(row['completed_batch_sha256'] != primary_end['arm_receipts'][arm]
                   for arm, row in first_end['arms'].items())):
        raise ValueError('Reconcile B1 with the measured control bank that its update used')
    audits, totals = {}, {arm: Counter() for arm in (ORDINARY, EXTERNAL_ARM, M2)}
    for batch in range(1, 9):
        if batch == 1:
            fit = primary
            end = primary_end
            teacher = {arm: {p.parent.name: read(p) for p in (first / 'candidates' / arm).glob('*/decision.json')}
                       for arm in (ORDINARY, EXTERNAL_ARM)}
            relation = {'OpenExempt': {'relation_in_scope': bool(primary_end['M2_relation_scope']),
                                       'status': primary_end['M2_selection_status']}}
        else:
            fit, _, end = finished(pointer(batch), 'completed_all_five_TRAIN_updates')
            matched = read(fit / 'matched_decisions.json')
            if digest(matched) != end['matched_decisions_sha256']:
                raise ValueError('The B2–B8 paper audit needs the original paired decisions')
            teacher, relation = matched['teacher'], matched['relation']
        changes = {}
        for arm in (ORDINARY, EXTERNAL_ARM, M2):
            key = 'schema_proposals' if arm == EXTERNAL_ARM else 'programs'
            before, current = (journal.library(arm, step).get(key, {}) for step in (batch - 1, batch))
            saved = journal._completed_batch(arm, batch)['completed_batch_sha256']
            if saved != end['arm_receipts'][arm]:
                raise ValueError('An audited batch needs its actual completed library seal')
            changes[arm] = sorted(d for d in set(before) | set(current) if before.get(d) != current.get(d))
        reports = {arm: control_counts(rows, changes[arm], batch == 1) for arm, rows in teacher.items()}
        in_scope = {dataset: row['status'] for dataset, row in relation.items() if row['relation_in_scope']}
        isolated = sum(bool(row.get('isolated_shared_rejection_applied')) for row in relation.values())
        reports[M2] = {'accepted': len(changes[M2]), 'in_scope_dataset_batches': len(in_scope),
                       'isolated_shared_rejections': isolated}
        for arm, stats in reports.items():
            totals[arm].update(stats)
        audits[f'B{batch}'] = {'training_terminal_sha256': sha(fit / 'terminal.json'),
                             'changed_datasets': changes, 'teacher_decisions': reports,
                             'M2_status_for_in_scope_datasets': in_scope}
    evidence = {'batches': audits, 'totals': {key: dict(value) for key, value in totals.items()},
                'new_model_calls': 0, 'TEST_artifacts_read_by_this_audit': False}
    publication = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables/TRAIN_UPDATE_ACCOUNTING.json'
    immutable_json(publication, evidence)
    result = {'paper_artifact': str(publication.relative_to(ROOT)), 'evidence_sha256': sha(publication),
              'totals': evidence['totals']}
    immutable_json(HANDOFF / 'B8_training_update_decision_accounting_20261119.json', result)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    run()
