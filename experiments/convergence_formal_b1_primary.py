"""Commit B1 primary arm libraries from measured candidate banks and source audits."""

import argparse
import json
import sqlite3

from experiments.convergence_formal_b1_fit import ORDINARY, POINTER as CONTROLS
from experiments.convergence_formal_b1_m1 import POINTER as INTERFACES
from experiments.convergence_formal_b1_observe import POINTER as OBSERVED, load_roster
from experiments.convergence_m2_update_probe import measure_natural_projection
from experiments.convergence_oe_natural_relation import build_natural_group, eligible_assets
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed, verify
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_b1_primary_current.json'
ARMS = ('method_one_only', 'method_two_only', 'both')
OE = 'OpenExempt'


def _current():
    return {key: ROOT / read(pointer)['artifact_root'] for key, pointer in (
        ('controls', CONTROLS), ('interface', INTERFACES), ('observer', OBSERVED))}


def _eligible(sources):
    for source, card, label, span, amount in eligible_assets():
        if source['key'] in sources:
            group = build_natural_group(source, sha(card), label, span, amount)
            return source, group
    return None, None


def prepare():
    stages = _current()
    required = {'controls': 'completed_two_B1_control_updates', 'interface': 'completed_B1_interface_fit',
                'observer': 'completed_B1_observations'}
    for kind, stage in stages.items():
        if read(stage / 'terminal.json')['status'] != required[kind]:
            raise ValueError('Complete each measured B1 component before assembling the primary libraries')
    observation = read(stages['observer'] / 'binding.json')
    checkpoint = ROOT / observation['bootstrap_root']
    study = read(checkpoint / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(checkpoint, study, batches)
    ordinary = journal._completed_batch(ORDINARY, 1)
    source, group = _eligible({s['key'] for s in batches[0] if s['dataset'] == OE})
    checked = read(stages['controls'] / 'candidates' / ORDINARY / OE / 'decision.json')
    use_group = group is not None and checked['selected'] == 'candidate'
    files = set(observation['source_sha256']) | {'experiments/convergence_formal_b1_primary.py',
        'experiments/convergence_m2_update_probe.py', 'experiments/convergence_oe_natural_relation.py',
        'legal_skill_guard/paired_interfaces/shared_semantics.py',
        'legal_skill_guard/paired_interfaces/shared_semantics_validation.py'}
    binding = {'study': 'convergence_B1_primary_arm_update_from_actual_measurements',
               'executor': study['executor'], 'study_binding_sha256': digest(study),
               'bootstrap_root': observation['bootstrap_root'], 'ordinary_B1_sha256': ordinary['completed_batch_sha256'],
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
               'ordered_visible_sha256': digest([row['key'] for row in batches[0]]),
               'stages': {key: {'root': str(stage.relative_to(ROOT)), 'terminal_sha256': sha(stage / 'terminal.json')}
                          for key, stage in stages.items()},
               'OE_audited_root': source['key'] if source is not None else None,
               'OE_group_sha256': digest([case.public for case in group['cases']]) if group is not None else None,
               'apply_relation_to_positive_candidate': use_group}
    out = BASE / 'formal_b1_primary' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'arms': list(ARMS), 'new_logical_reads_if_no_exact_replay': 2 if use_group else 0}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding = read(out / 'binding.json')
    checkpoint = ROOT / binding['bootstrap_root']
    study = read(checkpoint / 'binding.json')
    stages = {key: ROOT / item['root'] for key, item in binding['stages'].items()}
    if (out.name != digest(binding) or digest(study) != binding['study_binding_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())
            or any(sha(stages[key] / 'terminal.json') != record['terminal_sha256'] for key, record in binding['stages'].items())):
        raise ValueError('The matched candidate bank, fixed first batch or source constraints changed')
    batches = load_roster(study)
    visible = [s['key'] for s in batches[0]]
    if digest(visible) != binding['ordered_visible_sha256']:
        raise ValueError('Changing the first-batch prefix would invalidate the measured library')
    journal = TrainingJournal(checkpoint, study, batches)
    source, group = _eligible({s['key'] for s in batches[0] if s['dataset'] == OE})
    if group and (source['key'] != binding['OE_audited_root'] or
                  digest([case.public for case in group['cases']]) != binding['OE_group_sha256']):
        raise ValueError('The observed possession scope must remain bound to the candidate validation')
    before = journal.library(ORDINARY, 0)['programs']
    ordinary = journal.library(ORDINARY, 1)['programs']
    measured_ordinary = journal._completed_batch(ORDINARY, 1)
    if measured_ordinary['completed_batch_sha256'] != binding['ordinary_B1_sha256']:
        raise ValueError('Do not substitute an independently fitted ordinary teacher pool')
    relational = dict(ordinary)
    relation = {'status': 'no_positive_native_proposal_in_scope' if group else 'no_audited_partial_source_in_scope'}
    if binding['apply_relation_to_positive_candidate']:
        with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():
                raise ValueError('Settle any running comparison first')
        ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-primary-' + out.name[:16],
                                 sources={'train': visible, 'dev': [], 'test': []}, binding=binding)
        reader = FrozenExecutor(ledger, out, binding['executor'])
        reader.readiness()
        write_status(out, {'status': 'running', 'stage': 'OE_matched_relation'}, POINTER)
        rows = [measure_natural_projection(reader, out, ordinary[OE], case) for case in group['cases']]
        prediction_dir = stages['controls'] / 'candidates' / ORDINARY / OE
        decision = read(prediction_dir / 'decision.json')
        predictions = read(prediction_dir / 'predictions.json')
        if digest(predictions) != decision['predictions_sha256'] or decision['candidate_sha256'] != digest(ordinary[OE]):
            raise ValueError('Validation needs the same physically measured candidate proposal')
        baseline = {row['source']: row['native_utility'] for row in read(stages['observer'] / 'native_scores.json') if row['dataset'] == OE}
        grading = read(stages['observer'] / 'binding.json')
        path = grading['native_grade_paths'][OE]
        if sha(ROOT / path) != grading['native_grade_sha256'][path]:
            raise ValueError('Use the prebound local native TRAIN grading')
        grades = read(ROOT / path)
        native = []
        for mother in (row for row in batches[0] if row['dataset'] == OE):
            key = mother['key']
            score = []
            for task in mother['views']:
                answer = predictions[key]['native'][task['id']]
                score.append(grade_view(OE, task, grades[key][task['id']], answer['answer'])['grade'] if answer['handled'] else 0.)
            native.append({'source': key, 'baseline_utility': baseline[key], 'patch_utility': sum(score) / len(score)})
        patch = digest(ordinary[OE])
        cases = group['cases']
        relation = validate_patch(group['theory'], patch, [{'cases': cases, 'outputs': [r[0] for r in rows],
            'physical_call_ids': [r[1] for r in rows], 'literal_assertion_fields': ('ownership', 'stated_value')}],
            native, visible_train=visible, verify_projection=lambda program, physical, case, output: program == patch and
            any(bound.source_id == case.source_id and row == (output, physical) for bound, row in zip(cases, rows)),
            verify_native_pair=lambda program, row: program == patch and row in native)
        if relation['status'] != 'eligible_train_update':
            relational[OE] = before[OE]
    immutable_json(out / 'relation_decision.json', relation)
    interface_report = read(stages['interface'] / 'terminal.json')
    updates = {}
    for arm in ARMS:
        old = journal.library(arm, 0)
        fit = interface_report['arms'].get(arm)
        snapshot = None
        if fit:
            snapshot = read(checkpoint / 'interface_libraries' / (fit['interface_library_sha256'] + '.json'))
            verify(snapshot, 'snapshot_sha256')
            artifact = journal.directory(arm, 1) / 'interface_update.json'
            if digest(read(artifact)) != fit['interface_fit_sha256']:
                raise ValueError('The M1 state must retain its actual paired fit evidence')
        update = sealed({**{k: v for k, v in old.items() if k != 'snapshot_sha256'}, 'batch': 1,
                         'programs': ordinary if arm == 'method_one_only' else relational,
                         'interface_library': snapshot}, 'snapshot_sha256')
        proof = {'visible_prefix_sha256': digest(visible), 'ordinary_B1_sha256': binding['ordinary_B1_sha256'],
                 'interface_fit': fit, 'relation_provider_scope': [OE], 'M2_relation_decision_sha256': digest(relation)
                 if arm != 'method_one_only' else None, 'shared_bootstrap': True}
        updates[arm] = journal.commit_update(arm, 1, update, proof, verify_update=lambda before, new, receipt, prefix:
                                            before == old and new == update and receipt == proof and list(prefix) == visible)
    all_receipts = {arm: journal._completed_batch(arm, 1)['completed_batch_sha256'] for arm in ConvergenceEvaluation.arms}
    result = {'status': 'completed_all_five_B1_updates', 'arm_receipts': all_receipts,
              'M2_relation_scope': [OE], 'M2_selection_status': relation['status'],
              'M1_interface_calibration_scope': ['LegalBench_Diversity'], 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, result, POINTER)
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
