"""Fit whole-frame update masks on the same four original TRAIN parents.

This offline follow-up develops update granularity from the failed proposal;
the twenty-parent replay is NOT a new blind validation. Both arms receive the
same eight masks and the same native/source checks. No model clients exist here.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_C_diagnostic_refinement as stage
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_frame_revision import candidate_masks, merge
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review

ROOT = stage.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_C_frame_revision_20261115'


def assess_output(library, output, sid):
    current = stage.current
    bank = stage.read(current.generation.OUT / 'raw_source_bank.json')
    grading = stage.read(current.generation.OUT / 'TRAIN_grading.json')
    reviews = stage.read(current.prior.g.previous.base.history.OUT / 'teacher_task.json')['shared_partial_reviews']
    feedback = with_disposal_review(current.generation.core.checker(library, bank[sid]['source'], grading[sid]), sid,
        reviews.get('shared_reviewed_source_scope_checks') or [], library['spec']['decision_program'],
        authorization_review=reviews.get('shared_branch_authorization_review'))(output)
    frame = current.prior.g.previous.base.history.frame_review(sid, output)
    return {'source': sid, 'source_output': output, 'feedback': feedback, 'frame_review': frame,
        'hard_source_pass': feedback.get('source_review_passed', True) and not frame['failures'],
        'native_correct': sum(bool(v['score'] and v['score']['correct']) for v in feedback['views']),
        'native_total': len(feedback['views']), 'unresolved': sum(not v['core_executed'] for v in feedback['views'])}


def proposed(arm, sid):
    """Execute the actual updated skills, including C's actual φ and G."""
    current = stage.current
    target = OUT / arm / 'executed_proposal' / (digest(sid) + '.json')
    if target.exists():
        return stage.read(target)
    library, _ = stage.updated(arm)
    if arm == 'C':
        # The previous-G candidate already passed all four acquisition source
        # checks. This fixes the proposal used by the mask fit before replay.
        library['selected_rule_ids'] = stage.read(stage.OUT / 'C/candidates/UpdatedPreviousG.json')['selected_rule_ids']
    raw = stage.read(current.OUT / arm / 'raw_observations' / (digest(sid) + '.json'))
    value = current.assess(library, current.convert(library, raw), sid)
    immutable_json(target, value)
    return value


def run():
    assert (stage.OUT / 'result.json').exists()
    p = stage.protocol(); before = stage.ledger_counts()
    assert not any(status == 'reserved' for _, status, _ in before)
    summaries = {}
    for arm in ('C', 'FreeTeacher'):
        library = stage.initial(arm); previous = stage.saved_rows(arm); scores = []; rows_by_mask = {}
        for mask in candidate_masks():
            name = '+'.join(mask) or 'Before'; rows = []
            for sid in p['acquisition_sources']:
                new = proposed(arm, sid)
                output, receipt = merge(previous[sid]['source_output'], new['source_output'], mask)
                row = assess_output(library, output, sid)
                if not mask:
                    assert row['feedback'] == previous[sid]['feedback']
                row['revision_receipt'] = receipt
                immutable_json(OUT / arm / 'acquisition' / name / (digest(sid) + '.json'), row)
                rows.append(row)
            rows_by_mask[name] = rows
            scores.append({'name': name, 'mask': mask, 'source_valid': all(r['hard_source_pass'] for r in rows),
                'native_correct': sum(r['native_correct'] for r in rows), 'native_total': 16,
                'unresolved': sum(r['unresolved'] for r in rows)})
        chosen = min(scores, key=lambda r: (not r['source_valid'], -r['native_correct'], len(r['mask']), r['name']))
        immutable_json(OUT / arm / 'selected_before_replay.json', {'selected': chosen, 'scores': scores,
            'only_four_acquisition_sources_used': True, 'both_arms_share_mask_algorithm': True,
            'not_a_new_blind_split_after_the_first_negative_continuation': True})
        print(json.dumps({'arm': arm, 'selected': chosen, 'acquisition_scores': scores}), flush=True)
        rows = []
        for sid in p['fixed_reuse_sources']:
            new = proposed(arm, sid)
            output, receipt = merge(previous[sid]['source_output'], new['source_output'], chosen['mask'])
            row = assess_output(library, output, sid); row['revision_receipt'] = receipt
            old_views = {v['view']: v for v in previous[sid]['feedback']['views']}
            corrected, regressed = [], []
            for v in row['feedback']['views']:
                old_ok = bool(old_views[v['view']]['score'] and old_views[v['view']]['score']['correct'])
                new_ok = bool(v['score'] and v['score']['correct'])
                if old_ok and not new_ok: regressed.append(v['view'])
                if new_ok and not old_ok: corrected.append(v['view'])
            row['corrected_views'] = corrected; row['regressed_views'] = regressed
            immutable_json(OUT / arm / 'replay' / (digest(sid) + '.json'), row); rows.append(row)
        summaries[arm] = {'selected': chosen, 'replay_native_correct': sum(r['native_correct'] for r in rows),
            'replay_native_total': 80, 'replay_source_failures': [r['source'] for r in rows if not r['hard_source_pass']],
            'corrected': sum(len(r['corrected_views']) for r in rows), 'regressed': sum(len(r['regressed_views']) for r in rows),
            'not_a_new_blind_generalization_claim': True}
        print(json.dumps({'arm': arm, **summaries[arm]}), flush=True)
    assert stage.ledger_counts() == before
    immutable_json(OUT / 'result.json', {'arms': summaries, 'new_model_calls': 0,
        'public_operator_also_given_to_strong_control': True, 'original_TRAIN_only': True,
        'no_answer_or_source_ID_gating': True, 'goal_complete': False})


if __name__ == '__main__':
    run()
