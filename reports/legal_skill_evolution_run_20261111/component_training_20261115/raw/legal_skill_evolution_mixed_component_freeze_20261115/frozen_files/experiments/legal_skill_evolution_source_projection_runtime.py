"""Verify the guarded C library through normal observe->execute, TRAIN only.

The same deterministic feature is made available to the ordinary composition.
All original source reads are reused by identity; any new read is an explicit
offline failure, never a hidden executor request. No library is refitted here.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

from experiments import legal_skill_evolution_source_batch_update as update
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import observe
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review


ROOT = update.train.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_source_projection_runtime_20261115'
COUNTED = ROOT / 'artifacts/legal_skill_evolution_source_count_bias_repair_20261115'


class NoDispatch:
    def generate(self, *args, **kwargs):
        raise ValueError('Offline replay requested an unsupplied physical model read')

    def tokenize(self, *args, **kwargs):
        raise ValueError('Offline replay needs no new operation/window')


def run():
    read = update.train.read
    c_library = read(COUNTED / 'candidate_library.json')
    free_library = deepcopy(read(update.train.OUT / 'B8/FreeUpdate/library.json'))
    free_library['input_projection_definitions'] = deepcopy(c_library['input_projection_definitions'])
    libraries = {'ConstraintAcquire': c_library, 'FreeUpdate': free_library}
    public = {s['key']: s for s in read(update.train.parent.PREPARED / 'public.json') if s['dataset'] == 'ContractNLI'}
    grading = read(update.train.parent.PREPARED / 'grading.json')
    task = read(update.train.OUT / 'B8/teacher_task.json')
    evaluator = update.train.previous.old.previous.prior.prior.evaluate_source
    summaries = {}
    for arm, library in libraries.items():
        immutable_json(OUT / arm / 'library.json', library)
        rows = []
        for entry in task['tasks']:
            sid = entry['source_id']
            filename = update.train.previous.old.name_for(sid)
            previous = read(update.train.OUT / 'B8' / arm / 'candidate_results' / filename)['observation']
            upstream = read(update.train.parent.OUT / 'source_pass/upstream' / filename)['source_output']
            observation = observe(NoDispatch(), 'offline_normal_projection:' + arm + ':' + sid, sid,
                library, source_text=public[sid]['views'][0]['public']['source_text'],
                units=previous['visible_inputs']['units'], source_output=upstream,
                previous_observation=previous)
            assert observation['visible_inputs'] == previous['visible_inputs']
            assert observation['execution']['new_physical_requests'] == 0
            actual = evaluator(library, observation, public[sid], None)
            check = with_disposal_review(update.train.previous.old.previous.prior.prior.checker(
                library, public[sid], grading[sid]), sid, task.get('shared_reviewed_source_scope_checks', []),
                library['spec']['decision_program'], authorization_review=task.get('shared_branch_authorization_review'))
            feedback = check(actual['execution']['source_output'])
            row = {'source': sid, 'arm': arm, 'normal_observe_path': True,
                'observation': observation, 'source_output': actual['execution']['source_output'], 'feedback': feedback,
                'correct': sum(bool(v['score'] and v['score']['correct']) for v in feedback['views']),
                'unresolved': sum(not v['core_executed'] for v in feedback['views']),
                'source_review_passed': feedback.get('source_review_passed', True),
                'new_model_calls': 0, 'not_new_acquisition_or_novelty': True}
            immutable_json(OUT / arm / 'results' / filename, row)
            rows.append(row)
        summaries[arm] = {'native_correct': sum(r['correct'] for r in rows), 'views': 4 * len(rows),
            'unresolved': sum(r['unresolved'] for r in rows),
            'all_existing_source_checks_pass': all(r['source_review_passed'] for r in rows),
            'new_model_calls': 0}
    receipt = {'normal_observe_execute_used_both_arms': True, 'results': summaries,
        'same_public_feature_available_to_Free': True, 'new_model_calls': 0,
        'no_previous_library_or_result_overwritten': True, 'DEV_TEST_not_loaded': True,
        'source_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (Path(__file__), ROOT / 'legal_skill_guard/skill_evolution/open_acquisition.py',
                ROOT / 'legal_skill_guard/skill_evolution/source_projection_counts.py')},
        'not_a_new_C_contribution_or_two_contribution_acceptance': True, 'goal_complete': False}
    immutable_json(OUT / 'result.json', receipt)
    print(json.dumps(summaries), flush=True)


if __name__ == '__main__':
    run()
