"""Connect an existing guarded action type to the shared disposal consumer.

The authorization stays in the source action; only the common consequence
(all stated material disposed of by either lawful branch) is projected here.
Keep original B5 libraries and paid proposals immutable.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_library_train as train
from experiments import legal_skill_evolution_source_batch_initial as initial
from experiments import legal_skill_evolution_source_checkpoints as checkpoints
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.span_compiler import validate_procedure
from legal_skill_guard.skill_evolution.objects import digest


OUT = train.OUT / 'B5/post_shared_authorized_consumer'


def repair(code):
    old = "action[0] in ('action_alternative','acquired_action_alternative_v3')"
    new = "action[0] in ('action_alternative','acquired_action_alternative_v3','authorized_action_alternative')"
    assert code.count(old) == 1
    result = code.replace(old, new)
    validate_procedure(result, allow_helpers=True)
    return result


def run():
    for batch in range(5):
        checkpoints.record(batch, {a: train.OUT / f'B{batch}' / a / 'library.json'
            for a in train.ARMS}, pending=[])
    task = train.read(train.OUT / 'B5/teacher_task.json')
    old = {a: train.read(train.OUT / 'B5' / a / 'library.json') for a in train.ARMS}
    assert len({digest(v['spec']['decision_program']) for v in old.values()}) == 1
    code = repair(old[train.ARMS[0]]['spec']['decision_program'])
    paths, summaries = {}, {}
    for arm in train.ARMS:
        library = deepcopy(old[arm])
        library['spec']['decision_program'] = code
        preserved = deepcopy(library)
        preserved['spec']['decision_program'] = old[arm]['spec']['decision_program']
        assert preserved == old[arm]
        path = OUT / arm / 'library.json'
        immutable_json(path, library)
        paths[arm] = path
        rows = [initial.evaluate(library, t['source_id'], arm, 5,
            OUT / arm / 'results' / train.previous.old.name_for(t['source_id'])) for t in task['tasks']]
        assert all('actual' in r for r in rows)
        summaries[arm] = {'seen_correct': sum(r['correct'] for r in rows), 'seen_total': 4*len(rows),
            'current_correct': sum(r['correct'] for r in rows if r['source'] in task['current_sources']),
            'current_total': 4*len(task['current_sources']), 'unresolved': sum(r['unresolved'] for r in rows)}
    sid = next(t['source_id'] for t in task['tasks'] if any(u['id'] == 32 and
        'where expressly authorised in writing by the OSCE' in u['text'] for u in t['source_units']))
    issue = {'id': 'C5_destroy_written_authorization', 'arm': 'ConstraintAcquire', 'source': sid,
        'source_unit_ids': [32], 'reason': 'Actual acquired plain return/destroy alternative omits written authorization required only for destruction. Native disposal label does not test this distinction.',
        'status': 'unresolved', 'source_based_not_added_native_label': True}
    checkpoints.record(5, paths, pending=[issue])
    result = {'batch': 5, 'same_shared_consumer_both_arms': True, 'new_model_calls': 0,
        'source_phi_G_and_positive_policies_unchanged': True, 'original_libraries_and_results_preserved': True,
        'new_C_or_M2_learning_credit': False, 'results': summaries,
        'pending_source_semantics': [issue], 'goal_complete': False}
    immutable_json(OUT / 'receipt.json', result)
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    run()
