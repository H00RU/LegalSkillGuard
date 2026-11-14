"""Recover the existing Free composition absence guard after its producer update.

The paid proposal already emits witnessed disclosure permissions. Its retained
older lexical audit nevertheless adds 'no disclosure permission'. Restore the
positive-root guard already implemented by the SAME supplied library's prior
composer. No permission, legal exception, source fact or native label is added.
"""
import ast
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_batch_initial as initial
from experiments import legal_skill_evolution_source_library_train as train
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure


def run():
    batch, arm = 5, 'FreeUpdate'
    parent = train.OUT / 'B5' / arm
    folder = parent / 'provided_absence_guard_recovery'
    old = train.read(parent / 'compiled_candidate.json')
    library = deepcopy(old)
    code = library['composition_program']
    guard = 'if not free_internal_permission_present(spans) and not elliptical:'
    assert code.count(guard) == 1
    tree = ast.parse(code)
    helper = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'pb_has_root')
    prior = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'previous_compose')
    assert "not pb_has_root(out, 'permission')" in ast.get_source_segment(code, prior)
    changed = code.replace(guard,
        "if not free_internal_permission_present(spans) and not elliptical and not pb_has_root(statements, 'permission'):")
    validate_procedure(changed, allow_helpers=True)
    library['composition_program'] = changed
    assert library['source_program'] == old['source_program']
    immutable_json(folder / 'library.json', library)
    immutable_json(folder / 'recovery_receipt.json', {
        'original_library_sha256': digest(old), 'recovered_library_sha256': digest(library),
        'existing_helper_code': ast.get_source_segment(code, helper),
        'guard_already_in_same_supplied_previous_composer': True,
        'source_program_and_all_positive_legal_norms_unchanged': True,
        'no_model_response_rewritten': True, 'no_missing_rule_or_source_semantics_invented': True,
        'new_model_calls': 0, 'same_source_absence_consistency_check_both_arms': True})
    task = train.read(train.OUT / 'B5/teacher_task.json')
    public = {s['key']: s for s in train.read(train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = train.read(train.parent.PREPARED / 'grading.json')
    rows, evidence_changes = [], []
    for entry in task['tasks']:
        sid = entry['source_id']
        row = initial.evaluate(library, sid, arm, batch, folder / 'results' / train.previous.old.name_for(sid))
        before = train.read(parent / 'candidate_results' / train.previous.old.name_for(sid))
        def retained(value):
            return [r for r in value['actual']['execution']['source_output']['statements']
                if r['term'][0] != 'complete_source_no_disclosure_permission']
        assert retained(before) == retained(row), 'No positive source claim may be modified by this recovery'
        for b, a in zip(before['actual']['feedback']['views'], row['actual']['feedback']['views']):
            assert b['core_executed'] == a['core_executed']
            for key in ('grade', 'correct', 'valid'):
                assert (b['score'] or {}).get(key) == (a['score'] or {}).get(key)
            if b['score'] != a['score']:
                evidence_changes.append({'source': sid, 'view': b['view'],
                    'before': b['score'], 'after': a['score'],
                    'reason': 'Removed false full-source absence support from the proof'})
        check = with_disposal_review(train.previous.old.previous.prior.prior.checker(library, public[sid], grading[sid]),
            sid, task['shared_reviewed_source_scope_checks'], library['spec']['decision_program'])
        checked = check(row['actual']['execution']['source_output'])
        assert checked.get('source_review_passed', True), checked
        rows.append(row)
    source_id = next(s for s in task['current_sources'] if '4607c94' in s)
    c_row = train.read(train.OUT / 'B5/ConstraintAcquire/candidate_results' / train.previous.old.name_for(source_id))
    f_row = next(r for r in rows if r['source'] == source_id)
    result = {'arm': arm, 'batch': batch,
        'all_supplied_correct': sum(r['correct'] for r in rows), 'all_supplied_total': len(rows) * 4,
        'current_correct': sum(r['correct'] for r in rows if r['source'] in task['current_sources']),
        'current_total': len(task['current_sources']) * 4, 'unresolved': sum(r['unresolved'] for r in rows),
        'all_primary_native_scores_unchanged': True, 'evidence_score_changes': evidence_changes,
        'shared_source_checks_now_pass_all': True,
        'original_model_absence_contradiction_retained': True,
        'recovered_candidate_path': str(folder.relative_to(train.ROOT)), 'new_model_calls': 0,
        'past_actual_source_semantic_feedback_for_next_batch': {
            'source': source_id, 'source_quote': next(u['text'] for u in task['tasks']
                if u['source_id'] == source_id for u in u['source_units'] if 'where expressly authorised in writing' in u['text']),
            'actual_C_disposal_norms': [r['term'] for r in c_row['actual']['execution']['source_output']['statements'] if r['term'][0] == 'disposal_obligation'],
            'actual_Free_disposal_norms': [r['term'] for r in f_row['actual']['execution']['source_output']['statements'] if r['term'][0] == 'disposal_obligation'],
            'finding': 'C keeps a plain return-or-destroy alternative and no_acquired_exception despite source-specific written authorization on destruction. Free has now learned the existing authorized_action_alternative. Native NDA20 does not test the legality of choosing destruction, and the shared consumer currently recognizes ordinary alternatives but not this authorized variant. Do not call C native correctness proof of its dropped branch qualifier, or Free lower native score proof of a wrong acquired rule. Preserve per-action authorization scope; add no source facts or gold-answer rules.'},
        'goal_complete': False}
    immutable_json(folder / 'result.json', result)
    immutable_json(parent / 'library.json', library)
    immutable_json(parent / 'update_result.json', result)
    print(json.dumps({k: result[k] for k in ('arm', 'batch', 'all_supplied_correct', 'all_supplied_total',
        'current_correct', 'current_total', 'unresolved', 'new_model_calls')}), flush=True)


if __name__ == '__main__':
    run()
