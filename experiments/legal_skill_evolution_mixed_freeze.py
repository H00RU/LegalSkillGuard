"""Freeze actual final TRAIN libraries and the controlled seven-system recipes.

This reads TRAIN checkpoints only. A freeze preserves errors as well as learned
programs; it never establishes either contribution or starts DEV/TEST.
"""
import hashlib
import json
from pathlib import Path
import fcntl

from experiments import legal_skill_evolution_source_checkpoints as source
from experiments import legal_skill_evolution_generic_view_train as generic
from experiments import legal_skill_evolution_mixed_shared_routes as shared
from experiments import legal_skill_evolution_mixed_component_training as current
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest, Library


ROOT = current.ROOT
OUT = ROOT / 'artifacts/legal_skill_evolution_mixed_component_freeze_profile_fix_20261115'
RECIPES = {
    'C_PG_residual': {'source': 'ConstraintAcquire', 'observation': 'CoverageRecombine', 'followup': 'residual_guided'},
    'NoC_PG_residual': {'source': 'common_upstream_without_phi_G', 'observation': 'CoverageRecombine', 'followup': 'residual_guided'},
    'C_Generic': {'source': 'ConstraintAcquire', 'observation': 'fixed_generic', 'followup': 'none'},
    'FreeSource_FreeObs': {'source': 'FreeUpdate', 'observation': 'FreeGlobalUpdate', 'followup': 'ordinary_reread'},
    'BaseSource_Generic': {'source': 'common_upstream_without_phi_G', 'observation': 'fixed_generic', 'followup': 'none'},
    'C_FreeObs': {'source': 'ConstraintAcquire', 'observation': 'FreeGlobalUpdate', 'followup': 'ordinary_reread'},
    'C_PG_ordinary': {'source': 'ConstraintAcquire', 'observation': 'CoverageRecombine', 'followup': 'ordinary_reread'},
}


def freeze():
    protocol = current.setup()[0]
    assert (current.OUT / 'completed_through_B8.json').exists(), 'Finish current component TRAIN before freeze'
    assert source.exists(8), 'Finish source TRAIN before freeze'
    for batch in range(1, 9):
        assert (current.OUT / f'B{batch}/checkpoint.json').exists(), 'Unsettled component TRAIN batch'
    libraries, bound_files = {}, {}
    projection = ROOT / 'artifacts/legal_skill_evolution_source_projection_runtime_20261115'
    projection_result = current.read(projection / 'result.json')
    assert projection_result['normal_observe_execute_used_both_arms']
    assert projection_result['same_public_feature_available_to_Free']
    for arm in source.train.ARMS:
        path = projection / arm / 'library.json'
        library = current.read(path)
        libraries['source/' + arm] = {'path': str(path.relative_to(ROOT)), 'value_sha256': digest(library)}
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    assert current.read(projection / 'ConstraintAcquire/library.json')['spec']['decision_program'] == current.read(projection / 'FreeUpdate/library.json')['spec']['decision_program']
    for name, sha in projection_result['source_sha256'].items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
        bound_files[name] = sha
    checkpoint = current.read(current.OUT / 'B8/checkpoint.json')
    for arm in current.ARMS:
        path = ROOT / checkpoint['libraries'][arm]['path']
        library = current.read(path)
        assert digest(library) == checkpoint['libraries'][arm]['sha256']
        libraries['observation/' + arm] = {'path': str(path.relative_to(ROOT)), 'value_sha256': digest(library)}
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    common = shared.COMMON / 'B8.json'
    libraries['common_boundary_foundation'] = {'path': str(common.relative_to(ROOT)), 'library_hash': Library.load(common).hash}
    bound_files[str(common.relative_to(ROOT))] = hashlib.sha256(common.read_bytes()).hexdigest()
    for module in (current.actor, generic, current, source, shared):
        path = Path(module.__file__).resolve()
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('legal_skill_evolution_mixed_freeze.py', 'legal_skill_evolution_mixed_dev.py'):
        path = ROOT / 'experiments' / name
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    path = ROOT / 'legal_skill_guard/skill_evolution/statute_pure_calculation.py'
    bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    all_bindings = dict(protocol['source_sha256'])
    for name, sha in all_bindings.items():
        assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == sha, name
        bound_files[name] = sha
    # Freeze the actual common execution runtime as well as the learned units.
    # No package source may drift while the fixed DEV comparison is running.
    execution_files = list((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py'))
    execution_files += [ROOT / 'legal_skill_guard/rr' / name for name in ('client.py', 'ledger.py')]
    source_assets = current.source_train.previous.old.previous.PARENT
    execution_files += [source_assets / name for name in ('base.json', 'grammar.json')]
    kernel = current.read(current.actor.acquisition.previous.parent.OUT / 'SARA_native_kernel_bank.json')[0]['kernel']
    for name, sha in kernel['statute_sha256'].items():
        path = ROOT / kernel['statute_directory'] / name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha, name
        execution_files.append(path)
    for path in execution_files:
        bound_files[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    result = {'same_goal': True, 'stage': 'B8_frozen_before_DEV', 'recipes': RECIPES,
        'libraries': libraries, 'bound_files_sha256': bound_files,
        'original_128_TRAIN_sources': protocol['sources'], 'original_8_mixed_batches': protocol['batches'],
        'source_original_B8_pending_semantic_issues': source.state(8)['pending_source_semantics'],
        'source_public_repair_normal_execution': projection_result['results'],
        'observation_training_protocol': str((current.OUT / 'protocol.json').relative_to(ROOT)),
        'actual_current_component_B8_checkpoint': str((current.OUT / 'B8/checkpoint.json').relative_to(ROOT)),
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
        'actual_component_training': protocol['run_id'], 'new_model_calls': 0}), flush=True)


if __name__ == '__main__':
    with (ROOT / 'artifacts/rr_v2_preflight/current_open_acquisition_client.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        freeze()
