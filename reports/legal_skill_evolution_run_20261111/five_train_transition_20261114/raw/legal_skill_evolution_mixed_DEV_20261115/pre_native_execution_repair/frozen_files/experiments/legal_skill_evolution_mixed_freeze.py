"""Freeze actual final TRAIN libraries and the controlled seven-system recipes.

This reads TRAIN checkpoints only. A freeze preserves errors as well as learned
programs; it never establishes either contribution or starts DEV/TEST.
"""
import hashlib
import json
from pathlib import Path
import fcntl

from experiments import legal_skill_evolution_observation_library_train as observation
from experiments import legal_skill_evolution_source_checkpoints as source
from experiments import legal_skill_evolution_generic_view_train as generic
from experiments import legal_skill_evolution_mixed_shared_routes as shared
from experiments import legal_skill_evolution_mixed_training_continue as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest, Library


ROOT = observation.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_mixed_freeze_20261114'
RECIPES = {
    'C_PG_residual': {'source': 'ConstraintAcquire', 'observation': 'ProgramGuided', 'followup': 'residual_guided'},
    'NoC_PG_residual': {'source': 'common_upstream_without_phi_G', 'observation': 'ProgramGuided', 'followup': 'residual_guided'},
    'C_Generic': {'source': 'ConstraintAcquire', 'observation': 'fixed_generic', 'followup': 'none'},
    'FreeSource_FreeObs': {'source': 'FreeUpdate', 'observation': 'FreeHistory', 'followup': 'ordinary_reread'},
    'BaseSource_Generic': {'source': 'common_upstream_without_phi_G', 'observation': 'fixed_generic', 'followup': 'none'},
    'C_FreeObs': {'source': 'ConstraintAcquire', 'observation': 'FreeHistory', 'followup': 'ordinary_reread'},
    'C_PG_ordinary': {'source': 'ConstraintAcquire', 'observation': 'ProgramGuided', 'followup': 'ordinary_reread'},
}


def freeze():
    protocol = observation.read(current.OUT / 'protocol.json')
    assert source.exists(8), 'Finish source TRAIN before freeze'
    for batch in range(1, 9):
        assert (observation.OUT / f'B{batch}/scored_results.json').exists(), 'Unsettled observation TRAIN batch'
    libraries, bound_files = {}, {}
    for arm in source.train.ARMS:
        library = source.load(8, arm)
        path = ROOT / source.state(8)['libraries'][arm]['path']
        libraries['source/' + arm] = {'path': str(path.relative_to(ROOT)), 'value_sha256': digest(library)}
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert source.load(8, 'ConstraintAcquire')['spec']['decision_program'] == source.load(8, 'FreeUpdate')['spec']['decision_program']
    for arm in observation.ARMS:
        path = observation.OUT / 'B8' / arm / 'library.json'
        library = observation.read(path)
        libraries['observation/' + arm] = {'path': str(path.relative_to(ROOT)), 'value_sha256': digest(library)}
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    common = shared.COMMON / 'B8.json'
    libraries['common_boundary_foundation'] = {'path': str(common.relative_to(ROOT)), 'library_hash': Library.load(common).hash}
    bound_files[str(common.relative_to(ROOT))] = hashlib.sha256(common.read_bytes()).hexdigest()
    for module in (observation, generic, current, source, shared):
        path = Path(module.__file__).resolve()
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('legal_skill_evolution_mixed_freeze.py', 'legal_skill_evolution_mixed_dev.py'):
        path = ROOT / 'experiments' / name
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = ROOT / 'legal_skill_guard/skill_evolution/statute_pure_calculation.py'
    bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    all_bindings = {**protocol['source_sha256'], **protocol['data_sha256']}
    for sub_protocol in (current.actor.prepare(), current.residual_reads.prepare()):
        all_bindings.update(sub_protocol['source_sha256'])
    for name, sha in all_bindings.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
        bound_files[name] = sha
    result = {'same_goal': True, 'stage': 'B8_frozen_before_DEV', 'recipes': RECIPES,
        'libraries': libraries, 'bound_files_sha256': bound_files,
        'original_128_TRAIN_sources': protocol['sources'], 'original_8_mixed_batches': protocol['batches'],
        'source_pending_semantic_issues': source.state(8)['pending_source_semantics'],
        'executor_profile': protocol['executor_profile'], 'teacher_profile': protocol['teacher_profile'],
        'same_common_three_dataset_foundation_all_recipes': True,
        'same_public_direct_pure_calculation_precheck_all_observation_arms':True,
        'public_calculation_not_learned_mechanism_success':True,
        'fallback': 'Same inherited B8 answer only when current core is unhandled; always separate from core evidence.',
        'native_scores_not_semantic_or_novelty_certificates': True,
        'comparison1': ['C_PG_ordinary', 'C_Generic', 'C_FreeObs'],
        'comparison2_same_PG_contract': ['C_PG_residual', 'C_PG_ordinary'],
        'C_ablation': ['C_PG_residual', 'NoC_PG_residual'],
        'same_information_independent_updates_with_shared_history': ['C_PG_residual', 'FreeSource_FreeObs'],
        'not_cold_start_independent_acquisition_trajectories':True,
        'eligibility_without_labels_max_one_followup_opportunity': True,
        'known_failures_preserved_not_zero_fallback_gate': True,
        'not_seven_independent_retrainings_or_seven_new_algorithms': True,
        'new_model_calls': 0, 'DEV_opened_by_this_script': False, 'TEST_opened': False,
        'two_contributions_established': False, 'goal_complete': False}
    immutable_json(OUT / 'frozen_manifest.json', result)
    print(json.dumps({'stage': result['stage'], 'recipes': list(RECIPES),
        'pending_source_semantics': len(result['source_pending_semantic_issues']), 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze()
