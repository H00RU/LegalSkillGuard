"""Send the settled CNI pilot through the production M1 calibration library."""

from contextlib import contextmanager
import json
import sqlite3

from experiments.convergence_cni_disclosure_probe import POINTER, SOURCE_REVIEWS
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha
from legal_skill_guard.paired_interfaces import cni_disclosure_relational as disclosure
from legal_skill_guard.paired_interfaces.convergence_training import calibrate_source, training_batches
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor
from legal_skill_guard.paired_interfaces.formal_training import RelationalInterfaceLibrary
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.objects import digest


def run():
    record = read(POINTER)
    probe = ROOT / record['artifact_root']
    execution = read(probe / 'binding.json')
    cases = read(probe / 'cases.json')
    if record['status'] != 'completed' or digest(cases) != execution['cases_sha256']:
        raise ValueError('Use the already complete and bound CNI experiment')
    if any(sha(ROOT / name) != value for name, value in execution['source_sha256'].items()):
        raise ValueError('Calibrate the recorded wire version or its exact saved source')
    roster_pointer = read(HANDOFF / 'sealed_source_roster_current.json')
    roster = read(ROOT / roster_pointer['artifact_root'] / 'binding.json')
    normalized = ROOT / roster['normalized_root']
    protocol = read(ROOT / 'reports/legal_skill_convergence_20261117/protocol.json')
    batches = training_batches(roster, read(normalized / 'train/public.json'), protocol['data']['train_quota'])
    train_sources = [source['key'] for batch in batches for source in batch]
    pilot_keys = [case['public_source']['key'] for case in cases]
    grade_path = normalized / 'train/CNI_MAUD_grading_only.json'
    if sha(grade_path) != execution['source_gold_sha256']:
        raise ValueError('Original native CNI grades changed')
    grades = read(grade_path)
    baseline = ROOT / read(HANDOFF / 'pilot_b0_current.json')['artifact_root']
    common = read(baseline / 'binding.json')['program']
    binding = {
        'pilot_sha256': digest(execution), 'completed_observations_sha256': sha(probe / 'terminal.json'),
        'common_initial_program_sha256': digest(common), 'study_roster_sha256': digest(roster),
        'calibration_code_sha256': sha(ROOT / 'legal_skill_guard/paired_interfaces/convergence_training.py'),
        'pilot_observations_must_not_be_preloaded_in_formal_arms': True,
    }
    out = BASE / 'cni_disclosure_pilot_library' / digest(binding)
    immutable_json(out / 'binding.json', binding)

    class ReadOnlyLedger:
        run_id = 'convergence-maud-clause-' + digest(execution)[:16]

        @contextmanager
        def transaction(self):
            with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as database:
                yield database

        def reserve(self, *args, **kwargs):
            raise ValueError('Calibration uses only the eight settled physical responses')

    executor = FrozenExecutor(ReadOnlyLedger(), probe, execution['executor'])
    actor = InterfaceActor(executor, probe, plan_assets={}, source_inputs=None,
                           pipeline_binding=execution['source_sha256'])
    learner = RelationalInterfaceLibrary(out, actor=actor, train_sources=train_sources,
                                         initial_common_library_sha256=digest(common))
    for case in cases:
        source, view = case['public_source'], case['view']
        anchor, membership = SOURCE_REVIEWS[source['key'][-8:]]
        public = source['views'][0]['public']
        begin, end = view['relational_public_source']['indexed_ranges'][anchor]
        possibilities = [membership] if membership else ['own_employees', 'other_recipients', None]
        review = {
            'module': disclosure.module(),
            'admissible_states': [{'disclosure_actor': 'receiver', 'recipient_group': member,
                                   'permission_force': 'allow'} for member in possibilities],
            'provenance': [{'kind': 'independent_source_audit',
                            'evidence_sha256': digest(public['source_text'][begin:end])}],
            'native_evidence_ids': {disclosure.TASK: disclosure.native_evidence(public, anchor, [begin, end])}
                                    if membership else {},
        }
        calibrate_source(learner, source, view, unit_reviews={disclosure.UNIT: review},
                         grade_provider=grades.__getitem__, visible_prefix=pilot_keys)
    snapshot = learner.snapshot(batch=0, visible_prefix=pilot_keys)
    restored = RelationalInterfaceLibrary.restore(out, actor=actor, train_sources=train_sources, snapshot=snapshot)
    selections = [restored.choose(case['public_source'], case['view'])[1] for case in cases]
    summary = {
        'artifact_root': str(out.relative_to(ROOT)), 'source_denominator': len(cases),
        'eight_batch_sizes': [len(batch) for batch in batches],
        'actual_paired_observations': len(snapshot['observations']),
        'audited_faithful_observations': sum(row['source_fidelity']['all_local_relations_source_faithful']
                                           for row in snapshot['observations']),
        'leave_one_source_out_selected_plans': [row['selected_plan'] for row in selections],
        'independent_new_mother_prediction_claimed': False, 'physical_requests_added': 0,
        'snapshot_sha256': snapshot['snapshot_sha256'],
    }
    immutable_json(out / 'summary.json', summary)
    (HANDOFF / 'cni_disclosure_pilot_library_current.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary), flush=True)


if __name__ == '__main__':
    run()
