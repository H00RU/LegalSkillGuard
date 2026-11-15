"""One deterministic effect trace of the already TRAIN-selected G repair.

No acquisition, generation, further selection or new DEV benchmark run. The
candidate is bound before old DEV artifacts are opened; existing paid source
observations are replayed exactly, and all unchanged predictions stay fixed.
This cannot establish fresh model generation or independent generalization.
"""
from copy import deepcopy
import json

from experiments import legal_skill_evolution_source_selection_lineage as selected
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.open_acquisition import execute


ROOT = selected.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_selected_source_effect_replay_20261115'
DEV = ROOT / 'artifacts/legal_skill_evolution_mixed_component_DEV_profile_fix_20261115'


def run():
    read = selected.current.update.train.read
    selection = read(selected.OUT / 'selection.json')
    library = read(selected.OUT / 'training_selected_candidate.json')
    assert selection['selected_variant'] == '101'
    assert library['selected_rule_ids'] == selection['selected_rule_ids']
    before = selected.ledger_snapshot()
    immutable_json(OUT / 'pre_replay_lock.json', {
        'selection_sha256': digest(selection), 'candidate_sha256': digest(library),
        'selection_uses_only_original_TRAIN': True,
        'further_selection_or_acquisition_permitted': False,
        'new_model_calls': 0, 'ledger_before': before})
    original_library = read(selected.current.OUT / 'ConstraintAcquire/library.json')
    assert {k: v for k, v in library.items() if k != 'selected_rule_ids'} == {
        k: v for k, v in original_library.items() if k != 'selected_rule_ids'}
    previous = read(DEV / 'scored_results.json')
    prepared = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/dev'
    public = {r['key']: r for r in read(prepared / 'public.json')}
    grading = read(prepared / 'grading.json')
    assert all(r['split'] == 'dev' for r in public.values())
    new_core, changes = {}, []
    for sid, source in public.items():
        if source['dataset'] != 'ContractNLI':
            continue
        old = read(DEV / 'source' / (digest(sid) + '.json'))['rows']['ConstraintAcquire']
        observation = old['observation']
        original_execution = execute(original_library, observation)
        assert original_execution['source_output'] == old['source_execution']['source_output']
        execution = execute(library, observation)
        evaluator = selected.current.update.train.previous.old.previous.prior.prior.evaluate_source
        actual = evaluator(library, observation, source, None)
        assert actual['execution']['source_output'] == execution['source_output']
        old_views = {v['view']: v for v in old['views']}
        new_core[sid] = actual['feedback']['views']
        for view in actual['feedback']['views']:
            old_view = old_views[view['view']]
            if old_view['execution']['value'] != view['execution']['value']:
                changes.append({'source': sid, 'view': view['view'],
                    'old': old_view['execution']['value'], 'new': view['execution']['value']})
        immutable_json(OUT / 'source' / (digest(sid) + '.json'), {
            'source': sid, 'cached_observation_sha256': digest(observation),
            'original_execution_exact_parity': True,
            'source_output_changed': original_execution['source_output'] != execution['source_output'],
            'execution': execution, 'feedback': actual['feedback']})
    from legal_skill_guard.skill_evolution.native import grade_view
    common = read(ROOT / 'artifacts/legal_skill_evolution_20261111/formal_v5/dev/FreeEvolution/B8.json')
    inherited = {r['source']: {v['view']: v for v in r['views']} for r in common['results']}
    results = {}
    for name, recipe in previous['recipes'].items():
        rows = deepcopy(recipe['rows'])
        if recipe['recipe']['source'] == 'ConstraintAcquire':
            for row in rows:
                sid = row['source']
                if sid not in new_core:
                    continue
                updated = {v['view']: v for v in new_core[sid]}
                for view in row['views']:
                    value = updated[view['view']]
                    core = value['core_executed']
                    core_answer = value['execution']['value']['answer']
                    answer = core_answer if core else inherited[sid][view['view']]['execution']['answer']
                    public_view = next(v for v in public[sid]['views'] if v['id'] == view['view'])
                    view.update(answer=answer, fallback=not core,
                        score=grade_view('ContractNLI', public_view, grading[sid][view['view']], answer),
                        core_score=grade_view('ContractNLI', public_view, grading[sid][view['view']], core_answer))
                    view['core_execution'] = {'core_executed': core, 'answer': core_answer,
                        'current_learned_mechanism_executed': True}
        score = sum(sum(v['score']['grade'] for v in row['views'])/len(row['views']) for row in rows)/len(rows)
        results[name] = {'existing_score': recipe['native_parent_mean'],
            'cached_counterfactual_score': score, 'delta': score-recipe['native_parent_mean']}
    assert selected.ledger_snapshot() == before
    immutable_json(OUT / 'result.json', {'candidate_locked_before_old_DEV_loaded': True,
        'selection_sha256': digest(selection), 'candidate_sha256': digest(library),
        'old_paid_observations_reused_without_generation': True, 'changed_consumer_values': changes,
        'recipes': results, 'new_model_calls': 0, 'TEST_opened': False,
        'not_a_new_frozen_DEV_run_or_contribution_certificate': True,
        'old_results_unchanged': True, 'ledger_before': before,
        'ledger_after': selected.ledger_snapshot(), 'goal_complete': False})
    print(json.dumps({'changed_values': len(changes), 'recipes': results}), flush=True)


if __name__ == '__main__':
    run()
