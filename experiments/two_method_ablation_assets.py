"""Freeze the predeclared OE/Airline operator ablations without model calls."""
import itertools
import json
from pathlib import Path

from experiments.two_method_asset_module import execute
from experiments.two_method_airline_module import array_factorization_certificate
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from legal_skill_guard.paired_interfaces.ablation_paths import finite_operator_paths, projection_operator_paths
from legal_skill_guard.paired_interfaces.asset_interfaces import frozen_skill, regimes
from legal_skill_guard.paired_interfaces.control_tools import module_assets
from legal_skill_guard.paired_interfaces.residual import FiniteModule, canonical
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def airline_module():
    # Reconstruct the complete original finite table from its already
    # certified decoder,not from any source's native answer or weak read.
    original = read(BASE / 'offline_airline_module/generated_interfaces.json')
    asset = original['candidates']['candidates'][0]
    feature = next(f for f in asset['features'] if f['operation'] == 'residual_bucket')
    field = feature['field']; groups = feature['groups']
    values = sorted(value for group in groups for value in group['members'])
    if values != list(range(101)):
        raise ValueError('Preserve the full original integer0..100 domain')
    contexts = [json.loads(key) for key in next(iter(asset['decoder'].values()))]
    def consumer(local, context):
        code = next(g['code'] for g in groups if local[field] in g['members'])
        return asset['decoder'][canonical({feature['name']: code})][canonical(context)]['outputs']
    module = FiniteModule.build(asset['module'], {field: values}, contexts, consumer,
        consumer_sha256=asset['fixed_consumer_sha256'], source_scope=asset['source_scope'],
        protected_status_fields=asset['certificate']['protected_status_fields'])
    if module.binding != asset['module_binding'] or sha(ROOT / original['frozen_library_path']) != original['frozen_library_sha256']:
        raise ValueError('The reconstructed table lost its original immutable consumer binding')
    return module, original


def prepare():
    module, old_airline = airline_module()
    airline = finite_operator_paths(module)
    locked = read(BASE / 'pilot_lock.json')
    primary_codec = next(p for p in locked['plans']['RuleArena_Airline'] if p['name'] == 'local_records')['weight_codec']
    original_groups = primary_codec['groups']
    if module.binding != primary_codec['module_binding']:
        raise ValueError('The ablation table differs from the original production module binding')
    if airline['assets']['compression_only']['features'][0]['groups'] != original_groups:
        raise ValueError('Ablations must retain the original production codec alphabet')
    airline['production_array_factorization_certificate'] = array_factorization_certificate(
        module_assets('RuleArena_Airline')['skill']['procedure'], original_groups)
    airline['original_production_module_binding'] = primary_codec['module_binding']
    skill = frozen_skill(); premises = {name: p['value'] for name, p in skill['premises'].items()}
    boolean_fields = sorted(k for k in skill['inputs'] if k.startswith('asset_is_'))
    reports = []
    for regime in regimes(skill):
        calls = []
        for flags, debtors, family in itertools.product(itertools.product([False, True], repeat=len(boolean_fields)),
                                                       (1, 2), ('EC', 'EV')):
            inputs = {'asset_descriptions': ['zero-valued fixture asset', 'fractional-valued fixture asset'],
                'asset_values': [0, 23717.5], 'governing_regime': regime, 'number_of_debtors': debtors,
                'output_family': family, **{name: [value, not value] for name, value in zip(boolean_fields, flags)}}
            calls.append({'inputs': inputs})
        outputs = execute(skill['procedure'], premises, calls)
        reports.append(projection_operator_paths(skill, regime, [{**row, 'output': value} for row, value in zip(calls, outputs)]))
    paths = [Path(__file__).relative_to(ROOT), 'experiments/two_method_asset_module.py',
        'experiments/two_method_airline_module.py',
        'legal_skill_guard/paired_interfaces/ablation_paths.py', 'legal_skill_guard/paired_interfaces/residual.py',
        'legal_skill_guard/paired_interfaces/program_residual.py', 'legal_skill_guard/paired_interfaces/asset_interfaces.py',
        'legal_skill_guard/paired_interfaces/consumer_worker.py']
    protocol = {'experiment': 'fixed_OE_Airline_operator_ablation_assets_v1',
        'source_sha256': {str(p): sha(ROOT / p) for p in paths}, 'pilot_lock_sha256': sha(BASE / 'pilot_lock.json'),
        'frozen_airline_consumer_sha256': old_airline['consumer_sha256'], 'frozen_OE_skill_sha256': digest(skill),
        'original_airline_finite_asset_sha256': sha(BASE / 'offline_airline_module/generated_interfaces.json'),
        'original_production_Airline_module_binding': primary_codec['module_binding'],
        'primary_candidate_pool_changed': False, 'primary_candidate_or_source_expansion': False,
        'variants': ['same_legal_candidate_pool_exhaustive_search', 'refinement_only', 'compression_only'],
        'evaluation': 'B8 TRAIN choices sealed before any DEV/TEST grading;fixed OE/Airline TEST subset;no repair',
        'same_pool_search_is_the_primary_empirical_selector_not_an_additional_search_algorithm': True,
        'identical_endpoints_reuse_the_same_actual_read_and_are_not_independent_trials': True,
        'all_frozen_F_outputs_and_unknown_production_states_preserved': True,
        'teacher_or_weak_requests_or_native_grading': 0}
    out = BASE / 'formal_ablation_assets_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    immutable_json(out / 'Airline_operator_paths.json', airline)
    immutable_json(out / 'OE_operator_paths.json', reports)
    manifest = {'algorithm_variants': protocol['variants'], 'modules': ['OpenExempt', 'RuleArena_Airline'],
        'endpoint_plan': {'refinement_only': 'local_records', 'compression_only': 'local_records'},
        'same_pool_search_plan': 'M1 B8 per-dataset empirical TRAIN winner',
        'same_endpoint_not_evidence_one_operator_is_better': True,
        'same_wire_not_an_extra_independent_measurement': True, 'new_model_requests': 0,
        'Airline_compression_merges': len(airline['compression_merges']),
        'Airline_refinement_splits': len(airline['refinement_splits']), 'Airline_endpoint_classes': airline['end_classes'],
        'OE_refinement_witnesses': sum(len(r['refinement_witnesses']) for r in reports),
        'real_ablation_NATIVE_TEST_scores_computed': False, 'complete_goal_claimed': False}
    immutable_json(out / 'manifest.json', manifest)
    for path in paths:
        target = out / 'source_snapshot' / path; target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != (ROOT / path).read_bytes():
            raise ValueError('An immutable ablation source snapshot changed')
        if not target.exists(): target.write_bytes((ROOT / path).read_bytes())
    return out, protocol, manifest


if __name__ == '__main__':
    out, protocol, manifest = prepare()
    print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), **manifest}, ensure_ascii=False))
