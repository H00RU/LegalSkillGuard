"""Collect publishable summaries linked to one completed B8 TEST binding."""

from collections import Counter, defaultdict

from experiments.convergence_eval_cost_audit import completed_stage
from experiments.convergence_formal_test import INITIAL_ARM, POINTER
from experiments.convergence_pilot_b0 import BASE, HANDOFF, ROOT, read, sha
from legal_skill_guard.paired_interfaces.formal_evaluation import verify
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import digest


def verified_audit(pointer, terminal_sha256):
    path = ROOT / read(HANDOFF / pointer)['receipt']
    result = read(path)
    if result['terminal_sha256'] != terminal_sha256 or result['new_model_requests'] != 0:
        raise ValueError('All analysis receipts must refer to this frozen terminal result')
    return path, result


def seal_summary(directory, score_sha256, cohort, expected_library):
    task = read(directory / 'task.json')
    prediction = verify(read(directory / 'prediction_seal.json'), 'prediction_seal_sha256')
    score = verify(read(directory / 'scores.json'), 'cell_sha256')
    keys = set(cohort)
    views = defaultdict(set)
    for row in score['source_scores']:
        if row['view'] in views[row['source']]:
            raise ValueError('A sealed native grade cannot repeat a source view')
        views[row['source']].add(row['view'])
    if (prediction['task_sha256'] != digest(task) or score['cell_sha256'] != score_sha256
            or score['partition'] != 'test'
            or score['prediction_seal_sha256'] != prediction['prediction_seal_sha256']
            or set(prediction['predictions_sha256']) != keys
            or views.keys() != keys):
        raise ValueError('The prediction and scoring seals must cover the frozen sources')
    for key, expected in prediction['predictions_sha256'].items():
        record = read(directory / 'predictions' / (digest(key) + '.json'))
        if (digest(record) != expected or record['source'] != key or record['dataset'] != cohort[key]
                or record['library_sha256'] != expected_library[cohort[key]]['library_sha256']
                or record['result']['native'].keys() != views[key]):
            raise ValueError('Use the original prediction from the selected skill library')
    return {'prediction_seal_sha256': prediction['prediction_seal_sha256'],
            'native_cell_sha256': score_sha256, 'library_by_dataset': expected_library,
            'mothers': len(keys), 'native_units': len(score['source_scores'])}


def export_table(source, destination):
    body = source.read_bytes()
    if destination.exists():
        if destination.read_bytes() != body:
            raise ValueError('Published table bytes must match the recomputation')
    else:
        with destination.open('xb') as stream:
            stream.write(body)
    return sha(destination)


def run():
    if read(POINTER)['status'] != 'completed_fixed_B8_TEST':
        raise ValueError('Collect the public summaries after the five test arms and B0 reference settle')
    stage, checkpoint, terminal, arm_seals = completed_stage('test', 8)
    terminal_sha = sha(stage / 'terminal.json')
    spec = read(stage / 'binding.json')
    freeze = verify(read(checkpoint / 'selection_freeze.json'), 'freeze_sha256')
    if freeze['freeze_sha256'] != terminal['freeze_sha256'] or freeze['freeze_sha256'] != spec['B8_frozen_selection_sha256']:
        raise ValueError('Use the test results from this exact B8 selection')
    for file, expected in spec['source_sha256'].items():
        if sha(stage / 'source_snapshot' / file) != expected:
            raise ValueError('A frozen runtime file differs from its original checksum')
    roster = read(ROOT / spec['roster_path'])
    cohort = {r['source']: r['dataset'] for r in roster['sealed_TEST_identities']}
    counts = Counter(cohort.values())
    if len(cohort) != 160 or len(counts) != 5 or set(counts.values()) != {32}:
        raise ValueError('Keep all 160 held-out mothers and all five datasets')
    seals = {arm: seal_summary(checkpoint / 'test/B8' / arm, expected, cohort, freeze['choices'][arm])
             for arm, expected in sorted(arm_seals.items())}
    reference = terminal['static_initial_reference']
    if (not reference['reference_only']
            or reference['reference_freeze_sha256'] != spec['static_initial_reference']['freeze_sha256']):
        raise ValueError('The inference-only B0 reference must have its original selection')
    seals['static_initial_reference'] = seal_summary(
        stage / 'initial_reference/test/B8' / INITIAL_ARM, reference['cell_sha256'], cohort,
        spec['static_initial_reference']['choices'][INITIAL_ARM])
    if {item['native_units'] for item in seals.values()} != {768}:
        raise ValueError('Each condition must report the same native task coverage')
    grade_hashes = terminal['grading_receipts_sha256']
    if grade_hashes.keys() != counts.keys():
        raise ValueError('Every frozen dataset must have an original grading receipt')
    for dataset, expected in grade_hashes.items():
        path = stage / 'grading_receipts' / (dataset + '.json')
        if sha(path) != expected or read(path)['mothers'] != counts[dataset]:
            raise ValueError('Native grader receipts must match this test cohort')
    pointers = {
        'paired_native_effects': 'TEST_B8_native_effects_20261118.json',
        'physical_cost': 'TEST_B8_physical_cost_audit_20261118.json',
        'coverage': 'TEST_B8_coverage.json',
        'mechanism': 'B8_TEST_mechanism_audit.json',
    }
    audits = {name: verified_audit(pointer, terminal_sha) for name, pointer in pointers.items()}
    for name, used in {**audits['physical_cost'][1]['arms'],
                       'static_initial_reference': audits['physical_cost'][1]['static_initial_reference']}.items():
        if used['prediction_seal_sha256'] != seals[name]['prediction_seal_sha256']:
            raise ValueError('Physical costs must be tied to the same prediction seals')
    coverage = audits['coverage'][1]
    coverage_table = ROOT / coverage['table']
    if sha(coverage_table) != coverage['table_sha256']:
        raise ValueError('The supplementary coverage table changed after scoring')
    tables = ROOT / 'reports/legal_skill_convergence_20261117/paper/tables'
    exported = {
        'TEST_B8_NATIVE_TABLES.md': export_table(
            BASE / 'evaluation_tables/test/B8' / terminal_sha / 'tables.md',
            tables / 'TEST_B8_NATIVE_TABLES.md'),
        'TEST_B8_COVERAGE.md': export_table(coverage_table, tables / 'TEST_B8_COVERAGE.md'),
    }
    mechanism = audits['mechanism'][1]
    public_mechanism = tables / 'TEST_B8_MECHANISM_AUDIT.json'
    immutable_json(public_mechanism, mechanism)
    exported[public_mechanism.name] = sha(public_mechanism)
    receipt = {'TEST_terminal_sha256': terminal_sha, 'frozen_binding_sha256': stage.name,
               'selection_freeze_sha256': freeze['freeze_sha256'],
               'TRAIN_B8_seal_sha256': freeze['training_B8_seal']['training_seal_sha256'],
               'source_snapshot_receipt_sha256': sha(stage / 'source_snapshot_receipt.json'),
               'frozen_file_count': len(spec['source_sha256']), 'mothers_by_dataset': dict(counts),
               'cells': seals, 'grading_receipt_sha256': grade_hashes,
               'audit_sha256': {name: sha(path) for name, (path, _) in audits.items()},
               'test_physical_usage': audits['physical_cost'][1]['new_physical_usage'],
               'paper_artifact_sha256': exported, 'new_model_requests': 0}
    manifest = tables / 'TEST_B8_EVIDENCE_MANIFEST.json'
    immutable_json(manifest, receipt)
    immutable_json(HANDOFF / 'B8_TEST_public_evidence_manifest.json',
                   {'manifest': str(manifest.relative_to(ROOT)), 'manifest_sha256': sha(manifest)})
    print(manifest.relative_to(ROOT), flush=True)


if __name__ == '__main__':
    run()
