"""Fit ordinary and locked PARSE skills on the measured first TRAIN batch."""

import argparse
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_compact_teacher_pilot import teacher_system
from experiments.convergence_formal_b1_observe import POINTER as OBSERVED, load_roster
from experiments.convergence_native_teacher_pilot import INSTRUCTIONS
from experiments.convergence_parse_pilot import SYSTEM as SCHEMA_SYSTEM
from experiments.convergence_parse_runtime import EXTERNAL_ARM, ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor, common_cells
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import (
    SCHEMA, compact_native_passthrough, compile_proposal,
)
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire, public_field_types, schema_proposal
from legal_skill_guard.paired_interfaces.convergence_schema_order import normalize_proposal
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'formal_b1_fit_current.json'
ORDINARY = 'common_teacher_skill_learning'
ARMS = (ORDINARY, EXTERNAL_ARM)


def _feedback(sources, rows):
    payload = {}
    for dataset in sorted(ConvergenceEvaluation.datasets):
        region = [row for row in rows if row['dataset'] == dataset]
        utilities = [value for row in region for value in row['view_scores'].values()]
        fields = {}
        for source in (source for source in sources if source['dataset'] == dataset):
            for cell in common_cells(source):
                bundle = source_bundle(cell)
                for name, kinds in public_field_types(wire_schema(dataset, bundle)).items():
                    existing = fields.setdefault(name, [])
                    for kind in kinds:
                        if kind not in existing:
                            existing.append(kind)
        payload[dataset] = {'public_task_family': dataset, 'public_source_contract': INSTRUCTIONS[dataset],
            'measured_native_TRAIN_mothers': len(region), 'total_native_tasks': len(utilities),
            'aggregate_exact_success_count': sum(value == 1 for value in utilities),
            'aggregate_mean_native_utility': math.fsum(utilities) / len(utilities),
            'public_wire_field_types': fields, 'source_or_label_examples_included': False}
    return payload


def prepare(*, recover_from=None):
    observations = ROOT / read(OBSERVED)['artifact_root']
    observed, terminal = read(observations / 'binding.json'), read(observations / 'terminal.json')
    bootstrap = ROOT / observed['bootstrap_root']
    study = read(bootstrap / 'binding.json')
    if (observations.name != digest(observed) or digest(study) != observed['study_binding_sha256']
            or terminal['status'] != 'completed_B1_observations' or terminal['TEST_opened']
            or study['external_family'] != 'PARSE_style_interface_optimization'):
        raise ValueError('Use actual shared B1 observations and the same locked external family')
    batches = load_roster(study)
    journal = TrainingJournal(bootstrap, study, batches)
    for arm in ConvergenceEvaluation.arms:
        if journal._observations(arm, 1)['train_observation_sha256'] != terminal['observation_receipts'][arm]:
            raise ValueError('All five arms need the verified pre-update TRAIN observations')
    rows = read(observations / 'native_scores.json')
    if digest(rows) != terminal['native_scores_sha256'] or [row['source'] for row in rows] != [s['key'] for s in batches[0]]:
        raise ValueError('Teacher feedback can use only the actual native scores from the fixed first batch')
    payload = _feedback(batches[0], rows)
    files = set(observed['source_sha256']) | {'experiments/convergence_formal_b1_fit.py',
        'experiments/convergence_parse_runtime.py', 'experiments/convergence_compact_teacher_pilot.py',
        'experiments/convergence_parse_pilot.py', 'legal_skill_guard/paired_interfaces/convergence_compact_proposal.py',
        'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
        'legal_skill_guard/paired_interfaces/convergence_schema_order.py'}
    binding = {'study': 'convergence_measured_B1_ordinary_and_locked_external',
               'observations_root': str(observations.relative_to(ROOT)), 'observations_terminal_sha256': sha(observations / 'terminal.json'),
               'bootstrap_root': observed['bootstrap_root'], 'study_binding_sha256': digest(study),
               'teacher_profile': study['teacher_profile'], 'teacher_config': study['teacher_config'],
               'executor': study['executor'], 'source_sha256': {name: sha(ROOT / name) for name in sorted(files)},
               'feedback_sha256': digest(payload), 'one_proposal_per_library_per_control': True, 'fit_arms': list(ARMS)}
    if recover_from is not None:
        previous = ROOT / recover_from
        old = read(previous / 'binding.json')
        failure = read(previous / 'interruption_receipt.json')
        if (previous.parent != BASE / 'formal_b1_fit' or previous.name != digest(old)
                or {k: v for k, v in old.items() if k != 'source_sha256'} !=
                   {k: v for k, v in binding.items() if k != 'source_sha256'}
                or failure['status'] != 'interrupted_before_executor_dispatch'
                or read(previous / 'source_snapshot_receipt.json')['files'] != old['source_sha256']):
            raise ValueError('Only recover the archived context failure on the same first batch')
        binding['recovery'] = {'root': recover_from, 'parent_binding_sha256': digest(old),
                               'settled_teacher_call': failure['teacher_call_id']}
    out = BASE / 'formal_b1_fit' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'teacher_feedback.json', payload)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'batch': 1, 'fit_arms': list(ARMS), 'native_tasks': terminal['native_tasks']}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding, payload = read(out / 'binding.json'), read(out / 'teacher_feedback.json')
    checkpoint, observations = ROOT / binding['bootstrap_root'], ROOT / binding['observations_root']
    study, observed = read(checkpoint / 'binding.json'), read(observations / 'binding.json')
    terminal = read(observations / 'terminal.json')
    before = read(observations / 'native_scores.json')
    if (out.name != digest(binding) or digest(study) != binding['study_binding_sha256']
            or sha(observations / 'terminal.json') != binding['observations_terminal_sha256']
            or digest(before) != terminal['native_scores_sha256'] or digest(payload) != binding['feedback_sha256']
            or any(sha(ROOT / name) != expected for name, expected in binding['source_sha256'].items())):
        raise ValueError('The original primary reads, training feedback or candidate contracts changed')
    batches = load_roster(study)
    cohort = batches[0]
    keys = [source['key'] for source in cohort]
    journal = TrainingJournal(checkpoint, study, batches)
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle existing model requests first')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-fit-' + out.name[:16],
                             sources={'train': keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.exact_replay_roots = [observations, *(ROOT / path for path in observed['prior_train_replay_roots'])]
    reader.readiness()
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    recovery = binding.get('recovery')
    if recovery:
        previous = ROOT / recovery['root']
        old = read(previous / 'binding.json')
        if digest(old) != recovery['parent_binding_sha256']:
            raise ValueError('The original teacher request binding changed')
        prior_ledger = EvolutionLedger(LEDGER, run_id='convergence-formal-B1-fit-' + previous.name[:16],
                                       sources={'train': keys, 'dev': [], 'test': []}, binding=old)
        original_teacher = FrozenTeacher(prior_ledger, previous, old['teacher_config'],
                                        authorized_profile=old['teacher_profile'])
    common = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1), interface_actor=None,
                              providers={}, train_sources=keys, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(common, reader, out), reader, out)
    train_grades = {}
    updates = {}
    for arm in ARMS:
        initial = journal.library(arm, 0)
        cohort_seal = journal._observations(arm, 1)['train_observation_sha256']
        state = {**{key: value for key, value in initial.items() if key != 'snapshot_sha256'}, 'batch': 1}
        programs = dict(state['programs'])
        schema_plans = {}
        decisions = {}
        for dataset in sorted(payload):
            write_status(out, {'status': 'running', 'arm': arm, 'dataset': dataset}, POINTER)
            directory = out / 'candidates' / arm / dataset
            sources = [source for source in cohort if source['dataset'] == dataset]
            identity = ledger.run_id + ':teacher:' + arm + ':' + dataset
            schema = schema_proposal() if arm == EXTERNAL_ARM else SCHEMA
            system = SCHEMA_SYSTEM if arm == EXTERNAL_ARM else teacher_system('ordinary', dataset)
            proposer = teacher
            if recovery and (arm, dataset) == (ORDINARY, 'ContractNLI'):
                identity = recovery['settled_teacher_call']
                with prior_ledger.transaction() as db:
                    status = db.execute("select status from calls where id=? and role='teacher'", (identity,)).fetchone()
                if status != ('completed',):
                    raise ValueError('Recovery cannot repeat the settled physical teacher call')
                proposer = original_teacher
            reply = proposer.propose(identity, source_ids=[source['key'] for source in sources], system_prompt=system,
                                     user_prompt=json.dumps(payload[dataset], sort_keys=True), output_schema=schema)
            if reply['model'] != binding['teacher_config']['model']:
                raise ValueError('Use the frozen matched teacher for every draft')
            draft = {**state, 'programs': dict(initial['programs'])}
            artifact = None
            previous = [row['native_utility'] for row in before if row['dataset'] == dataset]
            result = {'teacher_physical_call_id': identity, 'teacher_proposal_sha256': digest(reply['value']),
                      'original_native_utility': math.fsum(previous) / len(previous), 'sources': len(sources)}
            try:
                if arm == EXTERNAL_ARM:
                    artifact = normalize_proposal(reply['value'], payload[dataset]['public_wire_field_types'])
                    for source in sources:
                        for cell in common_cells(source):
                            ReversibleWire(wire_schema(dataset, source_bundle(cell)), artifact)
                    draft['schema_proposals'] = {dataset: artifact}
                else:
                    if dataset == 'ContractNLI' and reply['value']['schema_mode'] != 'native':
                        raise ValueError('The current program runtime expects the native evidence wire')
                    artifact = compile_proposal(reply['value'], keys)
                    raw = artifact
                    artifact = compact_native_passthrough(artifact)
                    result['native_direct_passthrough_compacted'] = artifact != raw
                    draft['programs'][dataset] = artifact
            except (ValueError, SyntaxError, TypeError, KeyError, jsonschema.SchemaError, jsonschema.ValidationError) as error:
                result.update(selected='incumbent', status='invalid_teacher_candidate', error=type(error).__name__)
            else:
                proposal = sealed(draft, 'snapshot_sha256')
                predictions = {}
                for source in sources:
                    output = actor(source, proposal, 'skill_actor')
                    actor.verify_saved(source, proposal, 'skill_actor', output)
                    predictions[source['key']] = output
                immutable_json(directory / 'predictions.json', predictions)
                path = observed['native_grade_paths'][dataset]
                if path not in train_grades:
                    if sha(ROOT / path) != observed['native_grade_sha256'][path]:
                        raise ValueError('The native TRAIN grade file changed')
                    train_grades[path] = read(ROOT / path)
                mothers = []
                for source in sources:
                    key = source['key']
                    native = predictions[key]['native']
                    values = [grade_view(dataset, task, train_grades[path][key][task['id']], native[task['id']]['answer'],
                              native[task['id']].get('evidence_sentence_ids', []))['grade'] if native[task['id']]['handled'] else 0.0
                              for task in source['views']]
                    mothers.append(math.fsum(values) / len(values))
                after = math.fsum(mothers) / len(mothers)
                pick = after > result['original_native_utility']
                result.update(selected='candidate' if pick else 'incumbent', status='measured',
                              candidate_native_utility=after, candidate_sha256=digest(artifact), predictions_sha256=digest(predictions))
                if pick:
                    (schema_plans if arm == EXTERNAL_ARM else programs)[dataset] = artifact
            immutable_json(directory / 'decision.json', result)
            decisions[dataset] = result
        state['programs'] = programs
        if arm == EXTERNAL_ARM:
            state['schema_proposals'] = schema_plans
        library = sealed(state, 'snapshot_sha256')
        evidence = {'visible_prefix_sha256': digest(keys), 'before_observation_sha256': cohort_seal,
                    'selected_candidates': decisions, 'fitter_binding_sha256': digest(binding)}

        def verify_update(old, new, supplied, visible):
            if old != initial or new != library or supplied != evidence or list(visible) != keys:
                return False
            for dataset, record in decisions.items():
                directory = out / 'candidates' / arm / dataset
                if read(directory / 'decision.json') != record or (record['status'] == 'measured' and
                        digest(read(directory / 'predictions.json')) != record['predictions_sha256']):
                    return False
            return True

        updates[arm] = journal.commit_update(arm, 1, library, evidence, verify_update=verify_update)
    result = {'status': 'completed_two_B1_control_updates', 'arms': updates, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'completed_arms': list(updates)}, POINTER)
    print(json.dumps({'status': result['status'], 'completed_arms': list(updates)}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('--recover-from')
    args = parser.parse_args()
    if args.phase == 'prepare':
        prepare(recover_from=args.recover_from)
    else:
        if args.recover_from:
            parser.error('--recover-from is a prepare argument')
        run()
