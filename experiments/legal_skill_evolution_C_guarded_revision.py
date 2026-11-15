"""One offline guarded-update fit over the already exposed original TRAIN24.

The four/twenty experiment is preserved as a negative result. All 24 are now
explicitly training inputs for applicability learning, with no generalization
claim. This is one finite fit, not a parameter sweep or new model experiment.
"""
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_C_frame_revision as frames
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.source_frame_revision import FAMILIES, candidate_masks, merge
from legal_skill_guard.skill_evolution.source_revision_guards import vocabulary, fit, mask_for

ROOT = frames.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_C_guarded_revision_20261115'


def run():
    assert (frames.OUT / 'result.json').exists()
    stage = frames.stage; p = stage.protocol(); before = stage.ledger_counts()
    assert not any(status == 'reserved' for _, status, _ in before)
    bank = stage.read(stage.current.generation.OUT / 'raw_source_bank.json')
    texts = [bank[s]['source']['views'][0]['public']['source_text'] for s in p['sources']]
    files = [Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/source_frame_revision.py',
             ROOT / 'legal_skill_guard/skill_evolution/source_revision_guards.py', Path(frames.__file__)]
    immutable_json(OUT / 'protocol.json', {'sources': p['sources'], 'all24_are_original_exposed_TRAIN': True,
        'new_model_calls': 0, 'no_generalization_claim': True, 'fit_timeout_seconds': 120,
        'same_public_update_learner_for_both_arms': True,
        'source_sha256': {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
        'ledger_before': before, 'goal_complete': False})
    summaries = {}
    for arm in ('C', 'FreeTeacher'):
        library = stage.initial(arm); previous = stage.saved_rows(arm); updated, _ = stage.updated(arm)
        field = 'source_concept_program' if arm == 'C' else 'composition_program'
        features = vocabulary([library[field], updated[field]], texts)
        immutable_json(OUT / arm / 'feature_vocabulary.json', {'features': features,
            'from_actual_acquired_program_literals': True, 'minimum_parent_support': 2})
        table = []
        for sid in p['sources']:
            options = {}; new = frames.proposed(arm, sid)
            for mask in candidate_masks():
                # The inference ABI assigns bits by the three declared families.
                number = sum(2 ** sorted(FAMILIES).index(f) for f in mask)
                name = '+'.join(mask) or 'Before'
                target = OUT / arm / 'outcomes' / digest(sid) / (name + '.json')
                if target.exists():
                    row = stage.read(target)
                else:
                    output, receipt = merge(previous[sid]['source_output'], new['source_output'], mask)
                    row = frames.assess_output(library, output, sid); row['revision_receipt'] = receipt
                    immutable_json(target, row)
                options[number] = {'native_correct': row['native_correct'], 'source_valid': row['hard_source_pass']}
            table.append(options)
            print(json.dumps({'arm': arm, 'source': sid, 'cached_outcome_masks': len(options)}), flush=True)
        learned = fit(features, texts, table, timeout_seconds=120)
        immutable_json(OUT / arm / 'fit.json', learned)
        if learned['accepted']:
            policy = learned['policy']; rows = []
            for i, sid in enumerate(p['sources']):
                mask = mask_for(policy, texts[i]); output, receipt = merge(previous[sid]['source_output'],
                    frames.proposed(arm, sid)['source_output'], mask)
                row = frames.assess_output(library, output, sid); row['revision_receipt'] = receipt
                assert row['hard_source_pass']
                immutable_json(OUT / arm / 'selected_rows' / (digest(sid) + '.json'), row); rows.append(row)
            assert sum(r['native_correct'] for r in rows) == learned['native_correct']
        summaries[arm] = {k: learned[k] for k in ('accepted', 'native_correct', 'optimization_complete', 'policy', 'reason') if k in learned}
        print(json.dumps({'arm': arm, 'fit': summaries[arm]}), flush=True)
    assert stage.ledger_counts() == before
    immutable_json(OUT / 'result.json', {'arms': summaries, 'new_model_calls': 0,
        'TRAIN_fit_not_generalization': True, 'source_constraints_not_relaxed': True,
        'public_learner_shared_with_control': True, 'goal_complete': False})


if __name__ == '__main__':
    run()
