"""Index actual original TRAIN execution errors without asserting correct skills.

This reads saved predictions and the prepared TRAIN partition only. It issues
no model request, reruns no experiment, and never accesses DEV/TEST labels.
"""
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/Full'
PUBLIC = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json'
OUT = ROOT / 'reports/legal_skill_evolution_run_20261111/correct_skill_execution_20261114'


def read(path):
    return json.loads(path.read_text())


def run():
    public = {r['key']: r for r in read(PUBLIC)}
    counts = {}; candidates = []; exclusions = []; input_hashes = {}
    for batch in range(1, 9):
        path = STUDY / ('initial_B' + str(batch) + '.json')
        saved = read(path); input_hashes[str(path.relative_to(ROOT))] = digest(saved)
        for row in saved['results']:
            assert row['source'] in public and public[row['source']]['split'] == 'train'
            stats = counts.setdefault(row['dataset'], {'views': 0, 'actual_core': 0, 'nonexact_core_candidates': 0})
            for view_index, view in enumerate(row['views']):
                stats['views'] += 1
                execution = view['execution']; score = view['score']
                if not execution.get('core_executed') or execution.get('fallback'):
                    continue
                stats['actual_core'] += 1
                if not score or score.get('correct', score.get('grade') == 1):
                    continue
                stats['nonexact_core_candidates'] += 1
                applies = [(i, e) for i, e in enumerate(execution.get('events', [])) if e.get('kind') == 'APPLY']
                entry = {'source': row['source'], 'dataset': row['dataset'], 'view': view['view'],
                    'batch': batch, 'library_hash': row['library_hash'], 'terminal_skill': execution.get('terminal_skill'),
                    'score': score, 'saved_result': str(path.relative_to(ROOT)), 'saved_view_index': view_index,
                    'apply_refs': [{'event_index': i, 'skill_id': e['skill_id'], 'skill_hash': e.get('skill_hash'),
                        'version': e.get('version'), 'inputs_sha256': digest(e['inputs']),
                        'premises_sha256': digest(e['premises']), 'outputs_sha256': digest(e['outputs'])} for i, e in applies],
                    'skill_source_correctness': 'not_yet_verified',
                    'not_automatically_a_correct_skill_execution_failure': True}
                if row['dataset'] == 'SARA_v2_Binary':
                    question = public[row['source']]['views'][0]['public']['question']
                    if execution.get('terminal_skill') == 'section_3306_b_11_noncash_agricultural_wages_verdict' and 'Section 3306(c)' in question:
                        bank_path = STUDY / ('B' + str(batch - 1) + '.json')
                        skill = read(bank_path)['skills'][execution['terminal_skill']]
                        assert '3306(b)' in skill['intent']
                        entry['excluded_from_correct_relevant_skill_evidence'] = 'actual_skill_targets_3306_b_but_current_question_targets_3306_c'
                        exclusions.append({'source': row['source'], 'question': question,
                            'actual_skill_intent': skill['intent'], 'skill_path': str(bank_path.relative_to(ROOT)),
                            'not_a_fact_binding_failure': True,
                            'existing_public_claim_scope_checks_are_a_reusable_control_not_a_new_contribution': True})
                candidates.append(entry)
    summary = {'dataset_counts': counts, 'actual_core_views': sum(r['actual_core'] for r in counts.values()),
        'nonexact_core_views': len(candidates), 'nonexact_mother_sources': len({r['source'] for r in candidates}),
        'reviewed_query_scope_exclusions': len(exclusions),
        'verified_correct_relevant_skill_but_execution_wrong': 0,
        'zero_is_review_status_not_evidence_that_the_problem_is_absent': True,
        'new_model_requests': 0, 'no_DEV_TEST_or_experiment_reexecution': True, 'goal_complete': False}
    immutable_json(OUT / 'TRAIN_candidate_index.json', {'summary': summary, 'candidates': candidates,
        'reviewed_exclusions': exclusions, 'original_input_hashes': input_hashes})
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
