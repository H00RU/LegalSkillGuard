"""Execute the new B6 source/G interventions once on the same18 TRAIN mothers.

This is a new-version component intervention, not a rerun of the old8-mother
study, a new model experiment, or an independent new-source generalization set.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_batch_initial as initial
from experiments import legal_skill_evolution_source_checkpoints as checkpoints
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def run():
    train = checkpoints.train
    old, new = (checkpoints.load(b, 'ConstraintAcquire') for b in (5,6))
    assert old['spec'] == new['spec'], 'Hold the same public native consumer/types'
    for key in ('operations','planner_program','scope','operation_scopes'):
        assert old.get(key) == new.get(key), 'Source/G intervention must not hide a reading-policy change'
    root = train.OUT / 'B6/component_interventions'
    task = train.read(train.OUT / 'B6/source_parser_correction/teacher_task.json')
    issue = train.read(train.OUT/'B5/checkpoint.json')['pending_source_semantics']
    result = {}
    for variant in ('full_new', 'new_phi_old_G', 'old_phi_new_G'):
        library = deepcopy(new)
        library.pop('fit', None)  # A full-library proof does not prove an intervention.
        if variant == 'new_phi_old_G':
            for key in ('language','renderers','selected_rule_ids'):
                library[key] = deepcopy(old[key])
        elif variant == 'old_phi_new_G':
            library['source_program'] = old['source_program']
            library['source_program_update'] = deepcopy(old['source_program_update'])
        immutable_json(root / variant / 'library.json', library)
        rows = [initial.evaluate(library, t['source_id'], variant, 6,
            root / variant / 'results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
        result[variant] = {'native_correct':sum(r['correct'] for r in rows), 'total':4*len(rows),
            'unresolved':sum(r['unresolved'] for r in rows), 'library_sha256':digest(library),
            'source_program_sha256':digest(library['source_program']),
            'selected_G_sha256':digest({k:library[k] for k in ('language','renderers','selected_rule_ids')}),
            'branch_authorization_preserved':not checkpoints.remaining(issue, {'ConstraintAcquire':rows}),
            'source_rows':[{k:r[k] for k in ('source','correct','unresolved')} for r in rows]}
    receipt = {'variants':result, 'current_B6_versions_not_old8_repetition':True,
        'fixed18_supplied_TRAIN_mothers_not_blind':True,'same_public_consumer_and_source_texts':True,
        'new_model_calls':0,'native_correctness_not_full_source_semantic_certificate':True,
        'not_a_strong_control_margin_or_two_contribution_certificate':True,'goal_complete':False}
    immutable_json(root/'result.json',receipt)
    print(json.dumps({k:{f:v[f] for f in ('native_correct','total','branch_authorization_preserved')}
        for k,v in result.items()}),flush=True)


if __name__ == '__main__':
    run()
