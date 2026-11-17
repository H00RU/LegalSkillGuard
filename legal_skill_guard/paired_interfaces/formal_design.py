"""Fixed source/role/time boundaries for the one five-library formal study.

The source-only reference pool lets M2 evaluate typed rewrites on natural TRAIN
worlds without already observing their weak reads. Complete replay retains all
available paired traces as its empirical proxy. Native labels/weak outcomes do
not assign roles. The full corpus remains128 original mothers/eight batches.
"""
from collections import Counter, defaultdict

from legal_skill_guard.skill_evolution.objects import digest


ARMS = ('empty', 'ordinary_teacher_skills', 'budget_matched_SCOPE_adaptation',
        'M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2')
CURVES = (0, 1, 4, 8)
ROLE_SEED = 'two-method-formal-reference-worlds-before-any-new-formal-reads-20261117'
REFERENCE_COUNTS = {'OpenExempt': 8, 'SARA_v2_Binary': 4, 'ContractNLI': 4,
                    'RuleArena_Airline': 4, 'MAUD': 4}


def source_roles(source_lock, pilot_lock):
    batches = source_lock['training_batches']
    order = [source for batch in batches for source in batch]
    if (len(batches) != 8 or any(len(batch) != 16 for batch in batches)
            or len(order) != 128 or len(set(order)) != 128
            or set(order) != set(source_lock['sources']['train'])):
        raise ValueError('Preserve the complete original128-mother/eight-batch corpus')
    roles = {row['key']: row['role'] for row in pilot_lock['rows']}
    if (len(roles) != 32 or Counter(roles.values()) !=
            Counter(development=8, calibration=16, structure_evaluation=8)
            or not set(roles) <= set(order)):
        raise ValueError('The original pilot source roles must remain intact')
    new = defaultdict(list)
    for source in order:
        if source not in roles:
            new[source.split(':', 1)[0]].append(source)
    if set(new) != set(REFERENCE_COUNTS):
        raise ValueError('The original five source datasets changed')
    for dataset, sources in new.items():
        ranked = sorted(sources, key=lambda source: (digest([ROLE_SEED, source]), source))
        count = REFERENCE_COUNTS[dataset]
        if len(ranked) <= count or (len(ranked) - count) % 2:
            raise ValueError('Fixed reference/development/calibration counts cannot be formed')
        for source in ranked[:count]:
            roles[source] = 'reference_only'
        for index, source in enumerate(ranked[count:]):
            roles[source] = 'development' if index % 2 == 0 else 'calibration'
    rows = [{'source': source, 'dataset': source.split(':', 1)[0], 'batch': batch,
             'role': roles[source], 'original_pilot_role_preserved': source in {row['key'] for row in pilot_lock['rows']}}
            for batch, sources in enumerate(batches, 1) for source in sources]
    if Counter(row['role'] for row in rows) != Counter(development=44, calibration=52, reference_only=24, structure_evaluation=8):
        raise ValueError('A formal source role was lost or counted twice')
    return rows


def prefix(rows, batch):
    if type(batch) is not int or not 0 <= batch <= 8:
        raise ValueError('Use a fixed formal batch0..8')
    return [row for row in rows if row['batch'] <= batch]


def assert_pair_access(rows, sources, batch):
    permitted = {row['source'] for row in prefix(rows, batch)
                 if row['role'] in ('development', 'calibration')}
    if not set(sources) <= permitted:
        raise ValueError('A future,reference-only or structural-evaluation read entered primary fitting')


def design(source_lock, pilot_lock):
    rows = source_roles(source_lock, pilot_lock)
    if set(source_lock['sources']) != {'train', 'dev', 'test'}:
        raise ValueError('Explicit original source partitions are required')
    dev, test = source_lock['sources']['dev'], source_lock['sources']['test']
    if (len(dev) != 72 or len(test) != 136 or len(set(dev + test)) != 208
            or set(dev + test) & {row['source'] for row in rows}):
        raise ValueError('The fixed fresh source manifests changed or overlap')
    curves = [{'partition': 'dev', 'arm': arm, 'batch': batch, 'mothers': len(dev)}
              for batch in CURVES for arm in ARMS]
    final = [{'partition': 'test', 'arm': arm, 'freeze_batch': 8, 'mothers': len(test)} for arm in ARMS]
    transfer = [row['source'] for row in rows if row['role'] == 'reference_only'
                and row['dataset'] in ('SARA_v2_Binary', 'ContractNLI', 'MAUD')]
    return {'protocol': 'one-original128-five-library-formal-dataflow-v1',
        'roles': rows, 'role_seed': ROLE_SEED, 'source_mothers': 128, 'batches': 8,
        'role_counts': dict(Counter(row['role'] for row in rows)),
        'primary_paired_mothers': 96, 'source_only_reference_mothers': 24,
        'internal_structural_evaluation_mothers': 8,
        'all128_are_study_corpus_not128_independent_calibration_pairs': True,
        'primary_reader_calls_for_reference_only_sources': False,
        'reference_only_pool_may_contain_other_version_historical_exposure': True,
        'reference_only_is_not_a_new_blind_dataset': True,
        'original_pilot_roles_and_exposure_not_reset': True,
        'primary_M2_risk_worlds': 'same-context source-only reference TRAIN pool;equal mothers then distinct canonical worlds',
        'M2_stationary_transfer': 'explicit conditional mixture assumption for reference worlds outside actual calibration support',
        'reference_only_native_labels_weak_reads_and_outcomes_not_primary_training_inputs': True,
        'full_trace_replay': 'all available development+calibration joint pairs;native risk on its complete cached TRAIN world distribution as an empirical transfer proxy',
        'full_trace_replay_not_artificially_denied_development_traces': True,
        'all_arms_receive_same_prefix_raw_sources_source_references_and_formal_common_tools': True,
        'per_arm_learned_artifacts_isolated': True,
        'main_candidate_families': ['columns', 'records', 'local_records'],
        'M2_fixed_interface_families': ['columns', 'records'],
        'M1_selection': 'all actually measured development/calibration TRAIN mothers;native mother macro;fixed candidate-order tie',
        'M2_primary_unknown_mode': 'unrestricted', 'M2_secondary_conditional_mode': 'detectable_residual',
        'M2_primary_risk_costs': 'zero;actual token costs reported separately',
        'curve_matrix': curves, 'final_test_matrix': final,
        'DEV_label_feedback_to_candidate_or_channel_repair': False,
        'TEST_requires_B8_freeze_and_original_unexposed_source_manifest': True,
        'final_checkpoint_choice': 'learned arms:within each dataset choose best DEV mother macro from B1/B4/B8;ties later checkpoint;empty arm stays direct;seal once after B8',
        'B0_is_a_curve_initialization_not_a_learned_arm_final_fallback': True,
        'B0': 'no new formal updates;prior common legal F and historical exposure remain disclosed',
        'internal_structure_evaluation': 'once after B8 library/selection freeze;original8 exposed TRAIN mothers,not new blind TEST',
        'transfer_controls': {'source_pool': transfer,
            'mothers': len(transfer), 'systems': ['MOAR_style_measured_fixed_pool', 'independent_field_noise'],
            'actual_weak_reads_and_native_TRAIN_grading_only_after_primary_B8_selection_seals': True,
            'never_native_DEV_TEST_labels_for_plan_search': True,
            'no_primary_library_repair_from_control_results': True,
            'cached_logical_access_cost_and_actual_physical_cost_reported_separately': True},
        'M1_ablation_modules': ['OpenExempt', 'RuleArena_Airline'],
        'M1_ablation_contracts': ['same_legal_candidate_pool_exhaustive_search', 'refinement_only', 'compression_only'],
        'ablation_variants_not_used_to_enlarge_or_reselect_primary_pool': True,
        'raw_native_metrics': 'official EC/EV F1 within OE;native EM within each other dataset;no mixed-unit headline average',
        'one_fixed_matrix_no_gain_driven_expansion': True,
        'resource_or_teacher_generation_permission_not_granted_by_this_design': True,
        'complete_goal_claimed': False}
