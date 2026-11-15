"""Isolate the three actual G changes in the completed TRAIN guard repair.

This finite attribution reuses the exact 24 paid source observations. It does
not search new rules, load DEV/TEST, or deploy a checkpoint. The original fitted
selection, raw proposal and later common-feature candidate are all preserved.
"""
from copy import deepcopy
from itertools import product
import hashlib
import json
import sqlite3

from experiments import legal_skill_evolution_source_projection_runtime as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review


ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_source_selection_lineage_20261115'
FACTORS = ('compose_atomic_return_v3', 'compose_permission_controlled_employee_v3',
    'compose_complete_no_disclosure_without_parsed_permission_v1')


def ledger_snapshot():
    path = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as connection:
        rows = list(connection.execute('SELECT * FROM calls ORDER BY rowid'))
    return {'rows': len(rows), 'sha256': digest(rows)}


def run():
    read = current.update.train.read
    before = ledger_snapshot()
    fitted_path = current.update.train.OUT / 'B8/ConstraintAcquire/library.json'
    proposed_path = fitted_path.with_name('compiled_candidate.json')
    current_path = current.OUT / 'ConstraintAcquire/library.json'
    fitted, proposed, guarded = [read(p) for p in (fitted_path, proposed_path, current_path)]
    assert fitted['source_program'] == proposed['source_program'] == guarded['source_program']
    assert fitted['spec'] == proposed['spec'] == guarded['spec']
    base = set(fitted['selected_rule_ids'])
    assert base < set(proposed['selected_rule_ids'])
    assert set(guarded['selected_rule_ids']) == base | set(FACTORS)
    assert set(proposed['selected_rule_ids']) - base == {
        FACTORS[0], FACTORS[1], 'compose_complete_no_disclosure_query_v1'}
    public = {s['key']: s for s in read(current.update.train.parent.PREPARED / 'public.json')
        if s['dataset'] == 'ContractNLI'}
    grading = read(current.update.train.parent.PREPARED / 'grading.json')
    task = read(current.update.train.OUT / 'B8/teacher_task.json')
    selected_ids = [r['source_id'] for r in task['tasks']]
    assert len(selected_ids) == len(set(selected_ids)) == 24
    assert all(public[sid]['split'] == 'train' for sid in selected_ids)
    cached = {sid: read(current.OUT / 'ConstraintAcquire/results' /
        current.update.train.previous.old.name_for(sid)) for sid in selected_ids}
    results = []
    for bits in product((False, True), repeat=len(FACTORS)):
        key = ''.join(str(int(b)) for b in bits)
        library = deepcopy(guarded)
        library['selected_rule_ids'] = sorted(base | {r for r, b in zip(FACTORS, bits) if b})
        path = OUT / 'variants' / (key + '.json')
        if path.exists():
            value = read(path)
            assert value['library_sha256'] == digest(library)
        else:
            rows = []
            for sid in selected_ids:
                original = cached[sid]
                execution = execute(library, original['observation'])
                checker = with_disposal_review(
                    current.update.train.previous.old.previous.prior.prior.checker(library, public[sid], grading[sid]),
                    sid, task.get('shared_reviewed_source_scope_checks', []),
                    library['spec']['decision_program'],
                    authorization_review=task.get('shared_branch_authorization_review'))
                feedback = checker(execution['source_output'])
                if all(bits):
                    assert execution['source_output'] == original['source_output']
                    assert feedback == original['feedback']
                rows.append({'source': sid, 'observation_sha256': digest(original['observation']),
                    'source_output': execution['source_output'], 'feedback': feedback,
                    'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in feedback['views']),
                    'unresolved': sum(not v['core_executed'] for v in feedback['views']),
                    'hard_source_valid': feedback.get('source_review_passed', True)})
            value = {'variant': key, 'enabled_changes': [r for r, b in zip(FACTORS, bits) if b],
                'library_sha256': digest(library), 'selected_rule_ids': library['selected_rule_ids'],
                'native_correct': sum(r['native_correct'] for r in rows), 'native_total': 96,
                'all_hard_source_checks_pass': all(r['hard_source_valid'] for r in rows),
                'unresolved': sum(r['unresolved'] for r in rows), 'rows': rows,
                'new_model_calls': 0, 'current_result_exact_parity': all(bits)}
            immutable_json(path, value)
        print(json.dumps({k: value[k] for k in ('variant', 'native_correct',
            'all_hard_source_checks_pass', 'unresolved')}), flush=True)
        results.append(value)
    effects = []
    for index, factor in enumerate(FACTORS):
        off, on = results[0], next(v for v in results if v['variant'] == ''.join(
            '1' if i == index else '0' for i in range(len(FACTORS))))
        changes = []
        for a, b in zip(off['rows'], on['rows']):
            assert a['source'] == b['source']
            for av, bv in zip(a['feedback']['views'], b['feedback']['views']):
                assert av['view'] == bv['view']
                ac, bc = bool(av['score'] and av['score']['correct']), bool(bv['score'] and bv['score']['correct'])
                if ac != bc or av['core_executed'] != bv['core_executed']:
                    changes.append({'source': a['source'], 'view': av['view'],
                        'native_correct_before': ac, 'native_correct_after': bc,
                        'core_before': av['core_executed'], 'core_after': bv['core_executed']})
        effects.append({'factor': factor, 'single_change_native_delta': on['native_correct'] - off['native_correct'],
            'changed_views': changes})
    after = ledger_snapshot()
    assert before == after
    receipt = {'question': 'Which actual selected-rule changes caused the completed TRAIN repair gain?',
        'factor_order': list(FACTORS), 'variants': [{k: v[k] for k in ('variant', 'enabled_changes',
            'native_correct', 'native_total', 'all_hard_source_checks_pass', 'unresolved')} for v in results],
        'single_factor_effects': effects, 'parent_sha256': {str(p.relative_to(ROOT)):
            hashlib.sha256(p.read_bytes()).hexdigest() for p in (fitted_path, proposed_path, current_path)},
        'ledger_before': before, 'ledger_after': after, 'new_model_calls': 0,
        'DEV_TEST_loaded': False, 'checkpoint_changed_or_selected': False,
        'not_a_new_C_contribution_or_DEV_result': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', receipt)


def select_repaired_update():
    """Resume selection against the accepted B8 parent, not its raw proposal.

    All candidates are the already evaluated three-change patch family. This
    is a bounded update, with no claim of optimization over every acquired G.
    """
    read = current.update.train.read
    evidence = read(OUT / 'result.json')
    base_path = current.update.train.OUT / 'B8/ConstraintAcquire/library.json'
    base = read(base_path)
    feature_library = read(current.OUT / 'ConstraintAcquire/library.json')
    parent = set(base['selected_rule_ids'])
    rules = {r['id']: r for r in feature_library['language']['rules']}
    evaluated = []
    for variant in evidence['variants']:
        row = read(OUT / 'variants' / (variant['variant'] + '.json'))
        assert row['all_hard_source_checks_pass']
        selected = set(row['selected_rule_ids'])
        objective = (row['native_total'] - row['native_correct'], len(parent ^ selected),
            sum(rules[r]['cost'] for r in selected))
        evaluated.append((objective, row['variant'], row))
    objective, variant, selected = min(evaluated, key=lambda v: (v[0], v[1]))
    library = deepcopy(feature_library)
    library['selected_rule_ids'] = selected['selected_rule_ids']
    assert digest(library) == selected['library_sha256']
    selection = {'accepted_parent_path': str(base_path.relative_to(ROOT)),
        'accepted_parent_sha256': digest(base), 'finite_patch_evidence_sha256': digest(evidence),
        'objective_order': ['native_loss', 'selection_edits', 'complexity'],
        'evaluated_objectives': {key: list(obj) for obj, key, _ in evaluated},
        'selected_variant': variant, 'selected_rule_ids': library['selected_rule_ids'],
        'objective': list(objective), 'native_correct': selected['native_correct'], 'native_total': 96,
        'all_existing_source_checks_pass': True, 'optimization_complete_within_actual_patch_family': True,
        'selection_is_global_optimum': False, 'new_model_calls': 0, 'DEV_TEST_loaded': False,
        'candidate_not_promoted_to_previous_frozen_runs': True,
        'source_program_changed': False, 'consumer_program_changed': False,
        'removed_from_previous_guard_candidate': sorted(set(feature_library['selected_rule_ids']) -
            set(library['selected_rule_ids'])), 'goal_complete': False}
    immutable_json(OUT / 'training_selected_candidate.json', library)
    immutable_json(OUT / 'selection.json', selection)
    assert ledger_snapshot() == evidence['ledger_before']
    print(json.dumps(selection), flush=True)


if __name__ == '__main__':
    run()
    select_repaired_update()
