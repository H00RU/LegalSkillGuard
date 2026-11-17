"""One fixed full formal matrix;--prepare is source-only and makes no calls.

This entry never acquires teacher reference annotations. Missing source reviews
stop before creating any model clients,so it cannot dispatch or bypass the
previously rejected96-call reference batch. Optimizer calls belong to the
separately bound fixed ordinary/SCOPE study after the full data prerequisites.
"""
import argparse
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from experiments.two_method_annotate import inputs
from experiments.two_method_ablation_assets import prepare as prepare_ablation_assets
from experiments.two_method_formal_reference_registry import PREFLIGHT, prepare as prepare_registry
from experiments.two_method_graph_corpus import BASE, ROOT, read, sha
from experiments.two_method_heldout_exposure_gate import assert_unexposed_cohorts, inspect_exposure
from legal_skill_guard.paired_interfaces.formal_actors import (
    InterfaceActor, ProgramActor, INTERFACE_ARMS, restore_airline_wire_order)
from legal_skill_guard.paired_interfaces.formal_budget import PrefixBudgetExecutor
from legal_skill_guard.paired_interfaces.formal_controls import ControlBatchTrainer, ORDINARY, SCOPE, protocol as control_protocol
from legal_skill_guard.paired_interfaces.formal_design import design, prefix
from legal_skill_guard.paired_interfaces.formal_evaluation import FormalEvaluation, verify
from legal_skill_guard.paired_interfaces.formal_study import FormalStudy
from legal_skill_guard.paired_interfaces.formal_training import InterfaceBatchTrainer, MissingSourceReviews, ReferenceRegistry
from legal_skill_guard.paired_interfaces.postfreeze_protocol import ABLATIONS, diagnostic_design
from legal_skill_guard.paired_interfaces.postfreeze_execution import PostfreezeExecution
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


LEDGER = ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
TRAIN_ROOT = ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train'
PARTITIONS = {'train': TRAIN_ROOT, 'dev': BASE / 'prepared/dev', 'test': BASE / 'prepared/sealed_test'}


def wire_reuse_audit(assets, executor_profile):
    """Validate literal old wires,not only order-insensitive JSON equality."""
    from types import SimpleNamespace
    actor = InterfaceActor(SimpleNamespace(config=executor_profile), BASE / 'unused_wire_metadata_actor',
        plan_assets=assets, source_inputs=inputs, pipeline_binding={'metadata_only_wire_reuse_audit': True})
    public = {s['key']: s for s in read(TRAIN_ROOT / 'public.json')}
    rows = []
    for row in read(PREFLIGHT / 'requests.json'):
        identity = row['existing_paid_pilot_physical_call_id']
        if not identity: continue
        source = public[row['source']]
        view = next(v for v in actor.views(source) if v['view'] == row['opaque_view'])
        plan = next(p for p in view['plans'] if p['name'] == row['plan'])
        messages = [{'role': 'system', 'content': plan['system']},
                    {'role': 'user', 'content': json.dumps(view['read_input'], ensure_ascii=False, sort_keys=True)}]
        wire = json.dumps(request_payload(executor_profile, messages=messages, thinking=False,
                                         schema=plan['schema']), ensure_ascii=False).encode()
        previous = read(BASE / 'pilot_reads_v3/calls' / digest(identity) / 'wire_request.json')
        original = base64.b64decode(previous['body_b64'])
        if hashlib.sha256(original).hexdigest() != previous['body_sha256'] or original != wire:
            raise ValueError('An unchanged-library read must preserve its exact paid pilot wire,including schema order')
        rows.append({'source': source['key'], 'view': view['view'], 'plan': plan['name'],
                     'physical_call_id': identity, 'literal_wire_sha256': previous['body_sha256']})
    if len(rows) != 132: raise ValueError('All132 identified old unchanged-library reads must remain reusable')
    return {'literal_paid_wire_matches': rows, 'new_model_requests': 0,
            'all_old_roles_are_inventory_only_not_all_primary_fit_sources': True}


def bind_single_study(registry_root, out, protocol_sha256):
    """A changed source hash cannot silently launch a second formal matrix."""
    registry_root, out = Path(registry_root).resolve(), Path(out).resolve()
    if not out.is_relative_to(registry_root) or out == registry_root:
        raise ValueError('The formal study must live inside its original registry')
    record = {'artifact_root': str(out), 'protocol_sha256': protocol_sha256,
              'one_original_formal_matrix': True, 'not_a_live_process_or_permission_receipt': True}
    path = registry_root / 'active_study.json'
    if path.exists() and read(path) != record:
        raise BudgetError('The one formal matrix is already bound;preserve and reconcile its original run before any scientific continuation')
    immutable_json(path, record)
    return record


def prepare(extra_reviews=None):
    registry_root, registry, readiness = prepare_registry(extra_reviews)
    source_path, pilot_path = BASE / 'prepared/source_lock.json', BASE / 'pilot_lock.json'
    sources, pilot = read(source_path), read(pilot_path)
    exposure_status = inspect_exposure(sources, BASE / 'exposure/incidents')
    roles = read(registry_root / 'roles.json')
    ablation_root, _, ablation_manifest = prepare_ablation_assets()
    diagnostic_plan = diagnostic_design(roles, sources)
    assets = restore_airline_wire_order(read(PREFLIGHT / 'plan_assets.json'), pilot['plans']['RuleArena_Airline'])
    wire_audit = wire_reuse_audit(assets, pilot['executor'])
    candidates = [p for plans in assets['unchanged_libraries'].values() for p in plans]
    candidates += [p for plans in assets['OE_by_public_regime'].values() for p in plans]
    schema_wires = {p['version']: json.dumps(p['schema'], ensure_ascii=False) for p in candidates}
    if (not sources['old_TEST_not_renamed_or_reused'] or sources['teacher_access_to_DEV_TEST']
            or not sources['source_and_public_template_fingerprints_isolated']):
        raise ValueError('Use the original source-disjoint fresh DEV/TEST manifests')
    for split, folder in PARTITIONS.items():
        for name in ('public', 'grading'):
            if sha(folder / (name + '.json')) != sources['prepared_sha256'][split][name]:
                raise ValueError('A fixed public/grade artifact changed: ' + split + '/' + name)
    bindings = dict(registry['production_alignment_source_sha256'])
    for name in ('experiments/two_method_formal_study.py', 'experiments/two_method_ordinary_control.py',
                 'experiments/two_method_scope_control.py', 'experiments/two_method_ablation_assets.py',
                 'experiments/two_method_asset_module.py', 'experiments/two_method_heldout_exposure_gate.py',
                 'docs/HELDOUT_EXPOSURE_20261117.json',
                 'docs/FORMAL_REVISION_HOLD_20261117.json',
                 'docs/M2_EVIDENCE_GATE_20261117.json',
                 'experiments/two_method_m2_gate_evidence.py',
                 'legal_skill_guard/inference/codex_cli_client.py'):
        bindings[name] = sha(ROOT / name)
    from legal_skill_guard.paired_interfaces.observable_transfer import ASSUMPTIONS
    protocol = {'experiment': 'one_original_TRAIN128_eight_batch_seven_system_formal_v2_observable_revision',
        'M2_primary_method': 'observable-rewrite-set-transfer-v1',
        'M2_necessary_transfer_assumptions': list(ASSUMPTIONS),
        'M2_unrestricted_hidden_error_risk_envelope': [0., 1.],
        'formal_revision_hold': read(ROOT / 'docs/FORMAL_REVISION_HOLD_20261117.json'),
        'M2_user_evidence_gate': read(ROOT / 'docs/M2_EVIDENCE_GATE_20261117.json'),
        'source_sha256': bindings, 'source_lock_sha256': sha(source_path), 'pilot_lock_sha256': sha(pilot_path),
        'registry_path': str(registry_root.relative_to(ROOT) / 'manifest.json'),
        'registry_file_sha256': sha(registry_root / 'manifest.json'), 'registry_sha256': registry['registry_sha256'],
        'plan_assets_sha256': sha(PREFLIGHT / 'plan_assets.json'),
        'literal_schema_order_sha256': {version: hashlib.sha256(text.encode()).hexdigest()
                                       for version, text in schema_wires.items()},
        'unchanged_paid_wire_reuse_audit_sha256': digest(wire_audit),
        'source_design': design(sources, pilot), 'control_optimizer_design': control_protocol(),
        'heldout_exposure_status': exposure_status,
        'postfreeze_diagnostic_design': diagnostic_plan,
        'ablation_asset_manifest_path': str((ablation_root / 'manifest.json').relative_to(ROOT)),
        'ablation_asset_manifest_sha256': sha(ablation_root / 'manifest.json'),
        'ablation_evidence_files_sha256': {str((ablation_root / name).relative_to(ROOT)): sha(ablation_root / name)
            for name in ('Airline_operator_paths.json', 'OE_operator_paths.json')},
        'executor': pilot['executor'], 'teacher': pilot['teacher'],
        'teacher_executable_sha256': sha(Path(pilot['teacher']['executable'])),
        'source_partition_bytes': sources['prepared_sha256'],
        'DEV_curves': 'evaluate saved B0/B1/B4/B8 libraries after all training freezes;never feed native DEV feedback to updates',
        'shared_variants': 'all arms receive the verified B4 information;interface learners retain natural-source-only primary calibration;controls may use auxiliary supervision,with no primary cohort expansion',
        'shared_available_information_is_not_a_claim_every_algorithm_uses_it_identically': True,
        'primary_resource_budget': 'original fixed three-family measurements;no gain-driven expansion',
        'control_budget': 'each arm charges distinct source/purpose/frozen-wire observations,including old paid reuse;cap equals original primary prefix measured observations',
        'optimizer_teacher_schedule_fixed_before_dispatch': True,
        'reference_annotation_phase_called': False,
        'original_rejected96_phase_not_dispatched_or_retried_by_this_entry': True,
        'main_matrix_then_fixed_diagnostics_without_primary_repair': True,
        'contribution_claims_costs_curves_and_final_delivery_require_separate_evidence_audit': True,
        'complete_goal_claimed': False}
    out = BASE / 'formal_study_v1' / digest(protocol)
    immutable_json(out / 'protocol.json', protocol)
    for name, expected in bindings.items():
        target = out / 'source_snapshot' / name; target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != expected:
            raise ValueError('An immutable formal study source snapshot changed')
        if not target.exists(): target.write_bytes((ROOT / name).read_bytes())
    immutable_json(out / 'prepared_readiness.json', readiness)
    immutable_json(out / 'wire_reuse_audit.json', wire_audit)
    immutable_json(out / 'literal_schema_wire_contracts.json', schema_wires)
    return out, protocol, sources, registry, roles, readiness


def run(extra_reviews=None):
    assert_unexposed_cohorts(read(BASE / 'prepared/source_lock.json'), BASE / 'exposure/incidents')
    hold = read(ROOT / 'docs/FORMAL_REVISION_HOLD_20261117.json')
    if hold['formal_dispatch_on_hold']:
        raise ValueError('Formal dispatch is on user-requested revision hold: docs/REVISION_SCOPE_20261117.md')
    from experiments.two_method_m2_gate_evidence import assert_dispatch_gates
    assert_dispatch_gates(ROOT / 'docs/M2_EVIDENCE_GATE_20261117.json')
    out, protocol, sources, manifest, roles, readiness = prepare(extra_reviews)
    if not readiness['full_prefix_ready']:
        raise MissingSourceReviews('Formal dispatch requires all missing source reviews;this entry cannot obtain or replace the rejected96 teacher proposals')
    global_lock = (out.parent / 'driver.lock').open('a')
    fcntl.flock(global_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    lock = (out / 'driver.lock').open('a'); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    with sqlite3.connect('file:' + str(LEDGER) + '?mode=ro', uri=True) as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise BudgetError('An existing physical request must settle before formal dispatch')
    bind_single_study(out.parent, out, sha(out / 'protocol.json'))
    binding = {'protocol_sha256': sha(out / 'protocol.json'), 'registry_sha256': manifest['registry_sha256'],
               'source_lock_sha256': protocol['source_lock_sha256'], 'enforce_physical_actor_audit': True}
    run_prefix = 'two_method_formal_v1_20261117_' + out.name[:16]
    public = {s['key']: s for s in read(TRAIN_ROOT / 'public.json')}
    plan_assets = restore_airline_wire_order(read(PREFLIGHT / 'plan_assets.json'),
                                           read(BASE / 'pilot_lock.json')['plans']['RuleArena_Airline'])
    # Reconcile exact old paid observations;none is an independent new trial.
    old_roots = [BASE / 'pilot_reads_v3',
        BASE / 'asset_port_reads_v1/71eee85048e48fe8ebf7f4a190c4df814cdc5f36efc1b1c450123c3e05b72f3c',
        BASE / 'ordinary_control_v1/53be93c23c18b7421bda36bcbe2f8a17472b38c04d11134d747d1d2716fd21eb',
        BASE / 'ordinary_control_accounting_recovery_v2/cc60703fc6b75b26d167c4005af59c0664ea7177ee448c7dc2faf9e210cf5e81',
        BASE / 'scope_control_v1/7a1f8dd8ba69375b5b1310fbcc6551650e92af5b8ceca41554596d21f7c5883f']
    wire_roots = {phase: out / 'wire' / phase for phase in
                  ('primary', 'ordinary', 'scope', 'dev', 'test', 'diagnostics_train', 'diagnostics_test')}
    def check():
        assert_unexposed_cohorts(sources, BASE / 'exposure/incidents')
        for name, expected in protocol['source_sha256'].items():
            if sha(ROOT / name) != expected: raise ValueError('An active formal source changed: ' + name)
        if sha(Path(protocol['teacher']['executable'])) != protocol['teacher_executable_sha256']:
            raise ValueError('The original teacher executable changed')
        for split, folder in PARTITIONS.items():
            for name in ('public', 'grading'):
                if sha(folder / (name + '.json')) != protocol['source_partition_bytes'][split][name]:
                    raise ValueError('An active source partition changed')
        path = ROOT / protocol['registry_path']
        if sha(path) != protocol['registry_file_sha256']:
            raise ValueError('The active source-only review registry changed')
        if (sha(BASE / 'prepared/source_lock.json') != protocol['source_lock_sha256']
                or sha(BASE / 'pilot_lock.json') != protocol['pilot_lock_sha256']
                or sha(PREFLIGHT / 'plan_assets.json') != protocol['plan_assets_sha256']):
            raise ValueError('An active cohort,plan or candidate artifact changed')
        for review in manifest['reviews']:
            if sha(ROOT / review['path']) != review['sha256']:
                raise ValueError('An active source-only reference review changed')
        if sha(ROOT / protocol['ablation_asset_manifest_path']) != protocol['ablation_asset_manifest_sha256']:
            raise ValueError('An active operator ablation manifest changed')
        for name, expected in protocol['ablation_evidence_files_sha256'].items():
            if sha(ROOT / name) != expected: raise ValueError('An operator proof/witness artifact changed')
        for plans in [*plan_assets['unchanged_libraries'].values(), *plan_assets['OE_by_public_regime'].values()]:
            for plan in plans:
                actual = hashlib.sha256(json.dumps(plan['schema'], ensure_ascii=False).encode()).hexdigest()
                if actual != protocol['literal_schema_order_sha256'][plan['version']]:
                    raise ValueError('The actual backend schema property order changed')
    def client(phase, freeze=None):
        frozen = {'batch': 8, 'artifact_sha256': freeze['freeze_sha256']} if freeze is not None else None
        ledger = EvolutionLedger(LEDGER, run_id=run_prefix + '_' + phase, sources=sources['sources'],
                                 binding=binding, freeze=frozen)
        executor = FrozenExecutor(ledger, wire_roots[phase], protocol['executor'])
        executor.exact_replay_roots = [*old_roots, *wire_roots.values()]
        return ledger, executor
    def train_grades(source, seal):
        permitted = {r['source'] for r in prefix(roles, seal['batch']) if r['role'] in ('development', 'calibration')}
        if source not in permitted:
            raise ValueError('A primary/reference-only/structural native-label boundary was crossed')
        immutable_json(out / 'label_access' / 'train' / (digest([source, seal]) + '.json'), {
            'source': source, 'batch': seal['batch'], 'seal_sha256': digest(seal),
            'grading_sha256': sources['prepared_sha256']['train']['grading'],
            'current_measured_TRAIN_source_only': True})
        return read(TRAIN_ROOT / 'grading.json')[source]
    primary_ledger, primary_executor = client('primary')
    actor = InterfaceActor(primary_executor, out / 'primary', plan_assets=plan_assets,
        source_inputs=inputs, pipeline_binding=manifest['production_alignment_source_sha256'])
    registry = ReferenceRegistry(ROOT, manifest, roles, public, actor)
    orders = {dataset: [plan['name'] for plan in plans] for dataset, plans in read(BASE / 'pilot_lock.json')['plans'].items()}
    interfaces = InterfaceBatchTrainer(out / 'interface_training', roles=roles, public=public, registry=registry,
        actor=actor, candidate_orders=orders, grade_provider=train_grades, study_binding=binding)
    def controls(arm, batch, cap):
        phase = 'ordinary' if arm == ORDINARY else 'scope'
        ledger, raw = client(phase)
        executor = PrefixBudgetExecutor(raw, out / 'controls' / phase / 'budget')
        if batch: executor.set_limit(batch, cap)
        teacher = FrozenTeacher(ledger, wire_roots[phase], protocol['teacher'])
        return ControlBatchTrainer(out / 'controls' / phase, arm=arm, roles=roles, public=public, registry=registry,
            teacher=teacher, executor=executor, grade_provider=train_grades, study_binding=binding,
            shared_variants_root=out / 'shared_training_variants')
    eval_sources = {p: read(PARTITIONS[p] / 'public.json') for p in ('dev', 'test')}
    for partition, values in eval_sources.items():
        if sorted(s['key'] for s in values) != sorted(sources['sources'][partition]):
            raise ValueError('An evaluation public cohort lost its fixed source identities')
    def eval_grades(partition, source, seal):
        verify(seal, 'prediction_seal_sha256')
        if (source not in sources['sources'][partition]
                or set(seal['predictions_sha256']) != set(sources['sources'][partition])):
            raise ValueError('Complete fixed-cohort predictions must precede evaluation labels')
        if partition == 'test' and not (out / 'evaluation/selection_freeze.json').exists():
            raise ValueError('Native TEST labels require the original B8 selection freeze')
        immutable_json(out / 'label_access' / partition / (digest([source, seal]) + '.json'), {
            'source': source, 'prediction_seal_sha256': seal['prediction_seal_sha256'],
            'grading_sha256': sources['prepared_sha256'][partition]['grading'], 'not_available_to_training': True})
        return read(PARTITIONS[partition] / 'grading.json')[source]
    evaluator = FormalEvaluation(out / 'evaluation', eval_sources, binding=binding, grade_provider=eval_grades)
    def evaluation_actor(arm, partition, freeze):
        _, executor = client(partition, freeze)
        if arm in INTERFACE_ARMS:
            return InterfaceActor(executor, out / 'inference' / partition, plan_assets=plan_assets,
                source_inputs=inputs, pipeline_binding=manifest['production_alignment_source_sha256'])
        return ProgramActor(executor, out / 'inference' / partition, max_calls=protocol['executor']['context_tokens'])
    def diagnostic_actor(arm, partition, freeze):
        phase = 'diagnostics_' + partition
        _, executor = client(phase, freeze)
        if arm in INTERFACE_ARMS:
            return InterfaceActor(executor, out / 'inference' / phase, plan_assets=plan_assets,
                source_inputs=inputs, pipeline_binding=manifest['production_alignment_source_sha256'])
        return ProgramActor(executor, out / 'inference' / phase, max_calls=protocol['executor']['context_tokens'])
    def diagnostic_grades(partition, source, seal):
        frozen = read(out / 'postfreeze_choice_seal.json'); verify(frozen, 'diagnostic_seal_sha256')
        if seal['diagnostic_seal_sha256'] != frozen['diagnostic_seal_sha256']:
            raise ValueError('Diagnostic labels require the original pre-evaluation choices')
        if seal['phase'] == 'transfer':
            verify(seal, 'probe_prediction_seal_sha256')
            expected = frozen['design']['transfer_TRAIN_sources']
            keys = sorted((d['source'], d['view'], plan, task) for d in frozen['transfer_decisions']
                          for plan in d['fixed_candidate_order'] for task in d['native_tasks'])
            if (partition != 'train' or seal['native_candidate_slots'] != len(keys)
                    or seal['native_slot_keys_sha256'] != digest(keys)):
                raise ValueError('Complete original fixed-pool TRAIN predictions must precede MOAR labels')
        elif seal['phase'] == 'internal_structure':
            verify(seal, 'diagnostic_prediction_seal_sha256')
            expected = frozen['design']['internal_structural_TRAIN_sources']
            if partition != 'train': raise ValueError('Internal structure is exposed TRAIN,not TEST')
        elif seal['phase'] == 'M1_ablation':
            verify(seal, 'diagnostic_prediction_seal_sha256')
            expected = frozen['design']['M1_ablation_fixed_TEST_sources']
            if partition != 'test' or seal['label'] not in ABLATIONS:
                raise ValueError('Use only the presealed two-module TEST ablations')
        else:
            raise ValueError('Unknown diagnostic source/label purpose')
        if sorted(seal['source_cohort']) != sorted(expected) or source not in expected:
            raise ValueError('Diagnostic label access differs from the fixed original cohort')
        immutable_json(out / 'label_access/diagnostics' / (digest([partition, source, seal]) + '.json'), {
            'source': source, 'partition': partition, 'phase': seal['phase'],
            'diagnostic_seal_sha256': frozen['diagnostic_seal_sha256'], 'prediction_seal_sha256': digest(seal),
            'native_labels_not_available_for_any_primary_repair': True})
        return read(PARTITIONS[partition] / 'grading.json')[source]
    diagnostics = PostfreezeExecution(out, roles=roles, source_lock=sources, public_train=public,
        public_test=eval_sources['test'], interface_trainer=interfaces,
        ablation_asset_manifest=read(ROOT / protocol['ablation_asset_manifest_path']),
        ablation_asset_manifest_sha256=protocol['ablation_asset_manifest_sha256'],
        actor_factory=diagnostic_actor, grade_provider=diagnostic_grades, source_binding_check=check)
    check()
    readiness_result = primary_executor.readiness()
    immutable_json(out / 'readiness' / (digest(readiness_result) + '.json'), readiness_result)
    study = FormalStudy(out, binding=binding, interface_trainer=interfaces, control_factory=controls,
        evaluator=evaluator, evaluation_actor_factory=evaluation_actor, source_binding_check=check, diagnostics=diagnostics)
    return study.run()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--extra-reviews', type=Path)
    parser.add_argument('--run', action='store_true', help='Dispatch only after the full source-review prerequisite passes')
    args = parser.parse_args()
    if args.run:
        print(json.dumps(run(args.extra_reviews), ensure_ascii=False))
    else:
        out, protocol, _, _, _, readiness = prepare(args.extra_reviews)
        print(json.dumps({'artifact_root': str(out.relative_to(ROOT)), 'formal_training_started': False,
                          'research_model_requests': 0, 'source_reference_readiness': readiness}, ensure_ascii=False))
