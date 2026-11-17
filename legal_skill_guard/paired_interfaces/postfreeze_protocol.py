"""Pre-evaluation seals for fixed ablations and TRAIN transfer diagnostics.

No native grader or model transport is accepted. The measured MOAR-style
comparator is selected later from actual fixed-pool TRAIN scores after the
complete probe predictions have been sealed. Those labels never enter these
primary,full-replay or independent-field choices.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path

from legal_skill_guard.paired_interfaces.formal_design import ARMS, assert_pair_access
from legal_skill_guard.paired_interfaces.formal_evaluation import check_library, sealed, verify
from legal_skill_guard.paired_interfaces.formal_learning import restore_pair, select, world_weights
from legal_skill_guard.paired_interfaces import independent_field_noise, rich_graph_pairs
from legal_skill_guard.paired_interfaces.native_channel_selection import choose_risks
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


ABLATIONS = ('same_legal_candidate_pool_exhaustive_search', 'refinement_only', 'compression_only')
TRANSFER_SYSTEMS = ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2',
                    'independent_field_noise', 'MOAR_style_measured_fixed_pool')
MODULES = ('OpenExempt', 'RuleArena_Airline')


def diagnostic_design(roles, source_lock):
    if Counter(r['role'] for r in roles) != Counter(development=44, calibration=52, reference_only=24, structure_evaluation=8):
        raise ValueError('Preserve the full original formal source roles')
    transfer = [r['source'] for r in roles if r['role'] == 'reference_only'
                and r['dataset'] in ('SARA_v2_Binary', 'ContractNLI', 'MAUD')]
    internal = [r['source'] for r in roles if r['role'] == 'structure_evaluation']
    tests = [source for source in source_lock['sources']['test'] if source.split(':', 1)[0] in MODULES]
    if (Counter(s.split(':', 1)[0] for s in transfer) != Counter(SARA_v2_Binary=4, ContractNLI=4, MAUD=4)
            or Counter(s.split(':', 1)[0] for s in tests) != Counter(OpenExempt=32, RuleArena_Airline=32)):
        raise ValueError('Do not resample or expand the predeclared diagnostic cohorts')
    return {'protocol': 'fixed-post-B8-independent-contribution-diagnostics-v1',
        'M1_ablation_modules': list(MODULES), 'M1_ablation_variants': list(ABLATIONS),
        'M1_ablation_checkpoint': 8, 'M1_ablation_fixed_TEST_sources': tests,
        'M1_ablation_candidates_sealed_before_any_DEV_TEST_grading': True,
        'M1_ablation_TEST_cells': 6, 'M1_ablation_TEST_is_the_same_original_frozen_subset_not_a_new_blind_dataset': True,
        'M1_same_pool_search_is_the_same_exhaustive_empirical_selector': True,
        'transfer_TRAIN_sources': transfer, 'transfer_mothers': 12, 'transfer_systems': list(TRANSFER_SYSTEMS),
        'internal_structural_TRAIN_sources': internal, 'internal_systems': list(ARMS),
        'internal_structural_mothers': 8,
        'actual_target_weak_reads_and_native_TRAIN_labels_only_after_choice_seal': True,
        'MOAR_style_search': 'all three original candidates once;best actual native TRAIN mother-view macro;original candidate-order ties',
        'MOAR_is_an_adaptation_with_current_TRAIN_feedback_not_a_blind_deployment_method': True,
        'independent_field_model': 'all available paired TRAIN sources;conditional independent empirical predicate-family rewrites;whole-read abstention mass retained;no coverage guarantee',
        'independent_field_or_M2_unknown_mass_not_imputed_as_zero': True,
        'natural_structure_novelty_requires_separate_source_coverage_audit': True,
        'no_primary_repair_or_candidate_selection_from_diagnostic_labels': True,
        'cached_logical_information_and_new_physical_cost_reported_separately': True}


def _ablation_libraries(m1, asset_manifest, asset_manifest_sha256):
    if (asset_manifest['endpoint_plan'] != {'refinement_only': 'local_records', 'compression_only': 'local_records'}
            or not asset_manifest['same_endpoint_not_evidence_one_operator_is_better']):
        raise ValueError('Ablation endpoints must follow the frozen source-free operator evidence')
    result = {}
    for variant in ABLATIONS:
        library = {k: deepcopy(v) for k, v in m1.items() if k != 'snapshot_sha256'}
        library['fixed_postfreeze_ablation'] = variant
        library['operator_asset_manifest_sha256'] = asset_manifest_sha256
        if variant != ABLATIONS[0]:
            library['M1_choices'] = {dataset: value for dataset, value in library['M1_choices'].items()}
            for dataset in MODULES:
                if 'local_records' not in library['raw_candidate_orders'][dataset]:
                    raise ValueError('Operator endpoint is outside the original candidate pool')
                library['M1_choices'][dataset] = {'plan': 'local_records', 'supported': True,
                    'choice_basis': 'source-free legal operator endpoint;not DEV/TEST or diagnostic grades'}
        result[variant] = sealed(library, 'snapshot_sha256')
    return result


def seal(root, *, roles, source_lock, libraries, training_seal, public_train,
         interface_actor, paired_records, ablation_asset_manifest, ablation_asset_manifest_sha256):
    root = Path(root)
    design = diagnostic_design(roles, source_lock)
    verify(training_seal, 'training_seal_sha256')
    if set(libraries) != set(ARMS) or training_seal['batch'] != 8:
        raise ValueError('All seven actual B8 libraries must precede diagnostic choices')
    for arm in ARMS: check_library(libraries[arm], arm, 8)
    bindings = {arm: libraries[arm]['snapshot_sha256'] for arm in ARMS}
    if training_seal['libraries'] != bindings or not training_seal['all_seven_libraries_frozen']:
        raise ValueError('The diagnostic inputs differ from the original B8 training freeze')
    path = root / 'postfreeze_choice_seal.json'
    if path.exists():
        value = json.loads(path.read_text()); verify(value, 'diagnostic_seal_sha256')
        if (value['training_seal_sha256'] != training_seal['training_seal_sha256'] or value['main_B8_libraries'] != bindings
                or value['design'] != design or value['ablation_asset_manifest_sha256'] != ablation_asset_manifest_sha256
                or value['paired_TRAIN_records_sha256'] != digest(paired_records)):
            raise ValueError('A saved diagnostic seal changed its pre-evaluation inputs')
        return value
    if any((root / 'label_access' / split).exists() for split in ('dev', 'test', 'diagnostics')):
        raise ValueError('Missing pre-evaluation diagnostic seal cannot be reconstructed after target labels opened')
    assert_pair_access(roles, [r['source'] for r in paired_records], 8)
    groups = defaultdict(list)
    for row in paired_records:
        pair = restore_pair(row['pair'])
        if pair.source_id != row['source']:
            raise ValueError('A diagnostic fitting trace lost its TRAIN mother binding')
        if row['dataset'] in ('SARA_v2_Binary', 'ContractNLI', 'MAUD'):
            groups[row['dataset'], pair.reference.schema, pair.reference.context, row['plan']].append(pair)
    models = {key: independent_field_noise.fit(pairs) for key, pairs in groups.items()}
    model_ids = {key: model['model_sha256'] for key, model in models.items()}
    for key, model in models.items():
        immutable_json(root / 'independent_field_models' / (model['model_sha256'] + '.json'), model)
    reference_groups = libraries['M1_M2']['reference_world_groups']
    decisions = []
    for source_id in design['transfer_TRAIN_sources']:
        source = public_train[source_id]
        for view in interface_actor.views(source):
            if view['pre_generation_domain_refusal']:
                raise ValueError('The fixed three-dataset transfer pool cannot invent a new law-domain refusal')
            schema, context = view['scope']['schema'], view['scope']['context']
            consume = lambda world: rich_graph_pairs.consumer_signature(world, source['dataset'], view['native_public'])
            choices = {arm: select(libraries[arm], dataset=source['dataset'], schema=schema,
                                  context=context, arm=arm, consume=consume)
                       for arm in ('M1_only', 'M2_fixed_interfaces', 'M1_full_trace_replay', 'M1_M2')}
            refs = [g for g in reference_groups if (g['dataset'], g['schema'], g['context']) ==
                    (source['dataset'], schema, context)]
            predictions = {}
            for plan in view['plans']:
                key = source['dataset'], schema, context, plan['name']
                if key not in models or not refs:
                    predictions[plan['name']] = {'supported': False, 'reason': 'no compatible actual TRAIN marginal model/reference pool'}
                else:
                    predictions[plan['name']] = independent_field_noise.risk(models[key], consume,
                        world_weights(refs[0]['records']), version=interface_actor.channel_version(plan),
                        allow_stationary_transfer=True)
            orders = [p['name'] for p in view['plans']]
            choices['independent_field_noise'] = choose_risks(predictions, baseline=orders[0], costs={p: 0. for p in orders})
            decisions.append({'source': source_id, 'dataset': source['dataset'], 'view': view['view'],
                'public_source_sha256': digest(source), 'native_tasks': view['native_tasks'], 'fixed_candidate_order': orders,
                'frozen_choices': choices, 'actual_target_weak_read_or_native_grade_used': False,
                'natural_source_absence_or_transfer_advantage_certified': False})
    ablations = _ablation_libraries(libraries['M1_only'], ablation_asset_manifest, ablation_asset_manifest_sha256)
    value = sealed({'design': design, 'training_seal_sha256': training_seal['training_seal_sha256'],
        'paired_TRAIN_records_sha256': digest(paired_records),
        'main_B8_libraries': bindings, 'ablation_libraries': ablations,
        'ablation_asset_manifest_sha256': ablation_asset_manifest_sha256,
        'transfer_decisions': decisions,
        'independent_field_models': [{'dataset': key[0], 'schema': key[1], 'context': key[2],
            'plan': key[3], 'model_sha256': model_ids[key]} for key in sorted(model_ids)],
        'prepared_before_DEV_TEST_or_auxiliary_target_grading': True,
        'no_target_read_or_native_label_in_primary_or_noise_choices': True,
        'MOAR_choice_requires_later_actual_fixed_pool_scores': True,
        'primary_candidates_and_libraries_not_modified': True, 'complete_goal_claimed': False}, 'diagnostic_seal_sha256')
    immutable_json(path, value)
    return value


def measured_MOAR_choices(scores, decisions, prediction_seal):
    """Current TRAIN-label search only AFTER complete probe predictions."""
    verify(prediction_seal, 'probe_prediction_seal_sha256')
    expected = {(d['source'], d['view'], plan, task) for d in decisions
                for plan in d['fixed_candidate_order'] for task in d['native_tasks']}
    if (prediction_seal['native_candidate_slots'] != len(expected)
            or prediction_seal['native_slot_keys_sha256'] != digest(sorted(expected))
            or prediction_seal['diagnostic_decisions_sha256'] != digest(decisions)):
        raise ValueError('The complete fixed-pool predictions must precede measured MOAR scoring')
    identities = [(r['source'], r['opaque_view'], r['plan'], r['view']) for r in scores]
    if set(identities) != expected or len(identities) != len(expected):
        raise ValueError('Every fixed candidate/native task,including failures,must remain in MOAR search')
    if any(type(r['grade']) not in (int, float) or not math.isfinite(r['grade']) or not 0 <= r['grade'] <= 1
           or not r['handled'] and r['grade'] != 0 for r in scores):
        raise ValueError('Native diagnostic scores must preserve valid values and zero for unresolved outputs')
    lookup = {(r['source'], r['opaque_view'], r['plan'], r['view']): r['grade'] for r in scores}
    results = []
    for decision in decisions:
        order = decision['fixed_candidate_order']
        metrics = {plan: sum(lookup[decision['source'], decision['view'], plan, task]
                             for task in decision['native_tasks']) / len(decision['native_tasks']) for plan in order}
        plan = max(order, key=lambda p: (metrics[p], -order.index(p)))
        results.append({'source': decision['source'], 'view': decision['view'], 'plan': plan,
            'actual_current_TRAIN_native_feedback_used': True, 'candidate_native_scores': metrics,
            'not_a_blind_primary_method': True, 'primary_choices_not_modified': True})
    return results
