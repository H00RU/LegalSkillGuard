"""Fit and commit the five arms after the next fixed TRAIN observation batch."""

import argparse
from functools import lru_cache
import json
import math
import sqlite3

import jsonschema

from experiments.convergence_common_airline_actor import CommonAirlineActor
from experiments.convergence_compact_teacher_pilot import teacher_system
from experiments.convergence_formal_b1_fit import ARMS as CONTROL_ARMS, ORDINARY, POINTER as FIRST_CONTROLS, _feedback
from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_observe import pointer as observation_pointer
from experiments.convergence_m2_amount_judgment import (
    DATASET as DIVERSITY, first_visible_group, group_binding, measure as measure_amount,
    validate_update as verify_amount_update,
)
from experiments.convergence_m2_forward_oe import FILES as CONDITIONED_FILES, measure_update, prepare_conditioning
from experiments.convergence_m2_train_scope import ownership_groups
from experiments.convergence_m2_update_probe import measure_natural_projection
from experiments.convergence_oe_scoped_proposal import (
    SCOPED_SCHEMA, SCOPED_TEACHER_SUFFIX, native_asset_counts, scope_feedback, scoped_program,
)
from experiments.convergence_parse_pilot import SYSTEM as SCHEMA_SYSTEM
from experiments.convergence_parse_runtime import EXTERNAL_ARM, ParseControlActor
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces import diversity_claim_groups
from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_actors import ConvergenceActor, common_cells, M1_ARMS
from legal_skill_guard.paired_interfaces.convergence_compact_proposal import SCHEMA, compact_native_passthrough, compile_proposal
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_m1_batch import fit_interface_batch
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire, schema_proposal
from legal_skill_guard.paired_interfaces.convergence_schema_order import normalize_proposal
from legal_skill_guard.paired_interfaces.formal_actors import InterfaceActor, ProgramActor
from legal_skill_guard.paired_interfaces.formal_evaluation import ConvergenceEvaluation, sealed
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


M2 = 'method_two_only'
OE = 'OpenExempt'
CNI = 'ContractNLI'


def pointer(batch):
    return HANDOFF / f'formal_B{batch}_fit_current.json'


def _group(visible):
    groups, coverage = ownership_groups(visible)
    if not groups:
        return None, coverage
    # The visible roster determines the latest eligible reviewed mother.
    return groups[next(reversed(groups))], coverage


def _group_digest(group):
    return digest([case.public for case in group['cases']]) if group else None


def _prior_relation_feedback(stage, preceding_batch):
    terminal = read(stage / 'terminal.json')
    decisions = read(stage / 'matched_decisions.json')
    if (terminal['status'] != 'completed_all_five_TRAIN_updates' or terminal['batch'] != preceding_batch
            or terminal['TEST_opened'] or digest(decisions) != terminal['matched_decisions_sha256']):
        raise ValueError('Teacher feedback requires settled prior-TRAIN semantic validation')
    feedback = {}
    for dataset, decision in decisions['relation'].items():
        fields = sorted({row['field'] for group in decision.get('matched_controls', [])
                         for row in group.get('unsupported_literal_assertions', [])})
        if dataset == OE and 'ownership' in fields:
            feedback[dataset] = {
                'observed_issue': 'The prior candidate asserted title where the text established possession only.',
                'source_rule': 'Keep possession and ownership distinct, and leave title unresolved unless the input establishes it.',
                'native_labels_or_source_text_supplied': False,
            }
        if dataset == DIVERSITY and decision.get('judgment_gate') == 'missed_entailed_judgment':
            feedback[dataset] = {
                'observed_issue': 'The prior candidate omitted a legal threshold judgment proved by the stated amount alone.',
                'source_rule': 'With nonnegative claims, a stated amount over the threshold proves the judgment even if another amount is unknown.',
                'native_labels_or_source_text_supplied': False,
            }
    return feedback


def _apply_oe_feedback(feedback, conditioned, b5_stage=None):
    if not conditioned:
        return None
    oe_feedback = feedback.setdefault(OE, {})
    title_evidence = conditioned['teacher_feedback']
    if b5_stage is None:
        oe_feedback['shared_title_evidence'] = title_evidence
        return None
    revision = scope_feedback(b5_stage, title_evidence)
    oe_feedback['scoped_native_and_projection_evidence'] = revision['teacher_feedback']
    return {'B5_fit_root': str(b5_stage.relative_to(ROOT)), **revision['binding']}


def prepare(batch):
    observations = ROOT / read(observation_pointer(batch))['artifact_root']
    observed, terminal = read(observations / 'binding.json'), read(observations / 'terminal.json')
    checkpoint = ROOT / observed['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if (terminal['status'] != 'completed_TRAIN_observations' or terminal['batch'] != batch
            or terminal['TEST_opened'] or observations.name != digest(observed)
            or observed['study_binding_sha256'] != digest(study)):
        raise ValueError('Fitting requires the physically verified observations of the same next TRAIN batch')
    batches = load_roster(study)
    visible = [row for cohort in batches[:batch] for row in cohort]
    group, coverage = _group(visible)
    quantity_group = first_visible_group(visible)
    first = ROOT / read(FIRST_CONTROLS)['artifact_root']
    fit_roots = [first, *(ROOT / read(pointer(index))['artifact_root'] for index in range(2, batch))]
    replay = {}
    for stage in fit_roots:
        if read(stage / 'terminal.json')['TEST_opened'] or read(stage / 'binding.json')['executor'] != study['executor']:
            raise ValueError('Earlier candidates may be reused only from settled same-model TRAIN runs')
        replay[str(stage.relative_to(ROOT))] = sha(stage / 'terminal.json')
    prior_fit = fit_roots[-1]
    prior_feedback = _prior_relation_feedback(prior_fit, batch - 1) if batch > 2 else {}
    conditioned = prepare_conditioning(visible, study['executor']) if batch >= 5 else None
    b5_stage = ROOT / read(pointer(5))['artifact_root'] if batch >= 6 else None
    scoped_oe = _apply_oe_feedback(prior_feedback, conditioned, b5_stage)
    files = set(observed['source_sha256']) | {'experiments/convergence_formal_train_fit.py',
       'experiments/convergence_formal_b1_fit.py', 'experiments/convergence_m2_train_scope.py',
       'experiments/convergence_m2_amount_judgment.py',
       'legal_skill_guard/paired_interfaces/diversity_amount_judgment_supervision.py',
       'legal_skill_guard/paired_interfaces/diversity_amount_supervision.py',
       'legal_skill_guard/paired_interfaces/diversity_supervision.py',
       'experiments/convergence_parse_pilot.py', 'experiments/convergence_compact_teacher_pilot.py',
       'legal_skill_guard/paired_interfaces/convergence_schema_control.py',
       'legal_skill_guard/paired_interfaces/convergence_schema_order.py',
       'legal_skill_guard/paired_interfaces/convergence_compact_proposal.py'}
    if conditioned:
        files.update(CONDITIONED_FILES)
        files.add('experiments/convergence_oe_scoped_proposal.py')
    binding = {'study': 'convergence_matched_five_arm_TRAIN_update', 'batch': batch,
               'checkpoint_root': observed['checkpoint_root'], 'study_binding_sha256': digest(study),
               'observations_root': str(observations.relative_to(ROOT)),
               'observations_terminal_sha256': sha(observations / 'terminal.json'),
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
               'ordered_visible_sha256': digest([row['key'] for row in visible]),
               'natural_scope_sha256': digest(coverage),
               'natural_group_public_sha256': _group_digest(group),
               'quantity_group_sha256': group_binding(quantity_group),
               'quantity_scope': 'controlled_missingness_on_visible_TRAIN_only',
               'fit_replay_roots': replay,
               'previous_feedback_root': str(prior_fit.relative_to(ROOT)) if batch > 2 else None,
               'previous_relation_feedback_sha256': digest(prior_feedback),
               'conditioned_oe_projection': conditioned['binding'] if conditioned else None,
               **({'oe_native_projection_scope': scoped_oe} if scoped_oe else {}),
               'CNI_previous_TRAIN_regression_gate': True,
               'teacher_profile': study['teacher_profile'], 'teacher_config': study['teacher_config'],
               'executor': study['executor'], 'one_proposal_per_library_per_control': True}
    out = BASE / 'formal_train_fit' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'batch': batch, 'arms': list(ConvergenceEvaluation.arms)}, pointer(batch))
    print(json.dumps(read(pointer(batch)), sort_keys=True), flush=True)


def _candidate(reply, arm, dataset, payload, cohort, visible_keys):
    if arm == EXTERNAL_ARM:
        proposal = normalize_proposal(reply, payload['public_wire_field_types'])
        for source in cohort:
            for cell in common_cells(source):
                ReversibleWire(wire_schema(dataset, source_bundle(cell)), proposal)
        return proposal
    if dataset == CNI and reply['schema_mode'] != 'native':
        raise ValueError('ContractNLI requires the evidence-bearing native wire')
    return compact_native_passthrough(compile_proposal(reply, visible_keys))


def _mean(dataset, cohort, predictions, grade):
    members = {}
    for source in cohort:
        key = source['key']
        gold, native = grade(dataset)[key], predictions[key]['native']
        values = [
            grade_view(dataset, task, gold[task['id']], native[task['id']]['answer'],
                       native[task['id']].get('evidence_sentence_ids', []))['grade']
            if native[task['id']]['handled'] else 0.0 for task in source['views']
        ]
        members[key] = math.fsum(values) / len(values)
    return members


def _measure(actor, library, sources):
    predictions = {}
    for source in sources:
        result = actor(source, library, 'skill_actor')
        actor.verify_saved(source, library, 'skill_actor', result)
        predictions[source['key']] = result
    return predictions


def _contract_regression(actor, before, candidate, earlier, grade, out):
    prior = _measure(actor, before, earlier)
    changed = _measure(actor, candidate, earlier)
    before_scores = _mean(CNI, earlier, prior, grade)
    after_scores = _mean(CNI, earlier, changed, grade)
    delta = math.fsum(after_scores[key] - value for key, value in before_scores.items()) / len(earlier)
    evidence = {'earlier_mothers': len(earlier), 'native_tasks': sum(len(row['views']) for row in earlier),
                'native_utility_delta': delta, 'holds': delta >= 0, 'before': prior, 'candidate': changed}
    immutable_json(out / 'prior_TRAIN_regression.json', evidence)
    return {'passed': evidence['holds'], 'native_utility_delta': delta, 'evidence_sha256': digest(evidence)}


def _validate_relation(reader, out, artifact, group, visible_keys, comparisons):
    cases = group['cases']
    measurements = [measure_natural_projection(reader, out, artifact, case) for case in cases]
    version = digest(artifact)
    by_case = {case.source_id: row for case, row in zip(cases, measurements, strict=True)}
    return validate_patch(group['theory'], version, [{
        'cases': cases, 'outputs': [row[0] for row in measurements],
        'physical_call_ids': [row[1] for row in measurements],
        'literal_assertion_fields': ('ownership', 'stated_value'),
    }], comparisons, visible_train=visible_keys,
        verify_projection=lambda patch, physical, case, output: patch == version
            and by_case.get(case.source_id) == (output, physical),
        verify_native_pair=lambda patch, row: patch == version and row in comparisons)


def run(batch):
    out = ROOT / read(pointer(batch))['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json'), sort_keys=True), flush=True)
        return
    binding = read(out / 'binding.json')
    checkpoint, observations = ROOT / binding['checkpoint_root'], ROOT / binding['observations_root']
    study, observed = read(checkpoint / 'binding.json'), read(observations / 'binding.json')
    terminal = read(observations / 'terminal.json')
    if (binding['batch'] != batch or out.name != digest(binding) or digest(study) != binding['study_binding_sha256']
            or sha(observations / 'terminal.json') != binding['observations_terminal_sha256']
            or any(sha(ROOT / file) != saved for file, saved in binding['source_sha256'].items())):
        raise ValueError('The bound TRAIN feedback, model profile or update implementation changed')
    batches = load_roster(study)
    cohort = batches[batch - 1]
    visible = [row for part in batches[:batch] for row in part]
    visible_keys = [row['key'] for row in visible]
    group, coverage = _group(visible)
    quantity_group = first_visible_group(visible)
    if (digest(visible_keys) != binding['ordered_visible_sha256']
            or digest(coverage) != binding['natural_scope_sha256']
            or _group_digest(group) != binding['natural_group_public_sha256']
            or group_binding(quantity_group) != binding['quantity_group_sha256']):
        raise ValueError('Use the same originally audited visible TRAIN prefix')
    journal = TrainingJournal(checkpoint, study, batches)
    before = {arm: journal.library(arm, batch - 1) for arm in ConvergenceEvaluation.arms}
    native_scores, seals = {}, {}
    for arm in ConvergenceEvaluation.arms:
        seals[arm] = journal._observations(arm, batch)['train_observation_sha256']
        if seals[arm] != terminal['observation_receipts'][arm]:
            raise ValueError('A new update needs the measured entering predictions for every arm')
        rows = read(observations / 'native_scores' / (arm + '.json'))
        if (digest(rows) != terminal['native_scores_sha256'][arm]
                or [row['source'] for row in rows] != [source['key'] for source in cohort]):
            raise ValueError('Native feedback must cover the complete current batch')
        native_scores[arm] = {row['source']: row['native_utility'] for row in rows}
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the existing physical request first')
    run_id = f'convergence-formal-B{batch}-fit-{out.name[:16]}'
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': visible_keys, 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    replay = {str(observations.relative_to(ROOT)): binding['observations_terminal_sha256'],
              **observed['prior_train_replay_roots'], **binding['fit_replay_roots']}
    if any(sha(ROOT / root / 'terminal.json') != expected for root, expected in replay.items()):
        raise ValueError('An earlier response cohort changed')
    prior_feedback = (_prior_relation_feedback(ROOT / binding['previous_feedback_root'], batch - 1)
                      if binding['previous_feedback_root'] else {})
    conditioned = prepare_conditioning(visible, binding['executor']) if batch >= 5 else None
    scoped_oe = binding.get('oe_native_projection_scope')
    if (batch >= 6) != (scoped_oe is not None):
        raise ValueError('Use the scoped OpenExempt contract for the verified post-B5 training batches')
    if scoped_oe and scoped_oe['B5_fit_root'] not in binding['fit_replay_roots']:
        raise ValueError('The scoped teacher feedback must bind the completed B5 fitting stage')
    b5_stage = ROOT / scoped_oe['B5_fit_root'] if scoped_oe else None
    if _apply_oe_feedback(prior_feedback, conditioned, b5_stage) != scoped_oe:
        raise ValueError('The measured B5 coverage evidence or teacher contract changed')
    if conditioned:
        record = conditioned['binding']
        if record != binding['conditioned_oe_projection']:
            raise ValueError('The pre-bound TRAIN title projection changed')
        replay[record['root']] = record['terminal_sha256']
    if digest(prior_feedback) != binding['previous_relation_feedback_sha256']:
        raise ValueError('Prior measured relation feedback changed before dispatch')
    reader.exact_replay_roots = [ROOT / root for root in replay]
    reader.readiness()
    teacher = FrozenTeacher(ledger, out, binding['teacher_config'], authorized_profile=binding['teacher_profile'])
    actor = ConvergenceActor(out, program_actor=ProgramActor(reader, out, max_calls=1),
                             interface_actor=None, providers={}, train_sources=visible_keys, study_binding=study)
    actor = CommonAirlineActor(ParseControlActor(actor, reader, out), reader, out)

    @lru_cache(maxsize=None)
    def grade(dataset):
        path = observed['native_grade_paths'][dataset]
        if sha(ROOT / path) != observed['native_grade_sha256'][path]:
            raise ValueError('Retain the same independent TRAIN grader')
        return read(ROOT / path)

    programs = {arm: dict(before[arm]['programs']) for arm in (*CONTROL_ARMS, M2)}
    schemas = dict(before[EXTERNAL_ARM].get('schema_proposals', {}))
    earlier_contracts = [row for part in batches[:batch - 1] for row in part if row['dataset'] == CNI]
    if before[M2]['programs'][CNI] != before[ORDINARY]['programs'][CNI]:
        raise ValueError('Both arms need the same entering ContractNLI program for the matched prior-TRAIN guard')
    decisions, relations = {}, {}
    for arm in CONTROL_ARMS:
        feedback = _feedback(cohort, read(observations / 'native_scores' / (arm + '.json')))
        decisions[arm] = {}
        for dataset, payload in feedback.items():
            if dataset in prior_feedback:
                payload = {**payload, 'previous_TRAIN_semantic_feedback': prior_feedback[dataset]}
            write_status(out, {'status': 'running', 'batch': batch, 'arm': arm, 'dataset': dataset}, pointer(batch))
            sources = [row for row in cohort if row['dataset'] == dataset]
            keys = [row['key'] for row in sources]
            directory = out / 'candidates' / arm / dataset
            identity = run_id + ':teacher:' + arm + ':' + dataset
            system = SCHEMA_SYSTEM if arm == EXTERNAL_ARM else teacher_system('ordinary', dataset)
            schema = schema_proposal() if arm == EXTERNAL_ARM else SCHEMA
            coverage_diagnostic = dataset == OE and scoped_oe is not None
            scoped_candidate = coverage_diagnostic and arm == ORDINARY
            if scoped_candidate:
                system += SCOPED_TEACHER_SUFFIX
                schema = SCOPED_SCHEMA
            result = teacher.propose(identity, source_ids=keys, system_prompt=system,
                                     user_prompt=json.dumps(payload, sort_keys=True), output_schema=schema)
            if result['model'] != binding['teacher_config']['model']:
                raise ValueError('Teacher identity drift breaks the matched update comparison')
            decision = {'teacher_call': identity, 'proposal_sha256': digest(result['value'])}
            try:
                artifact = (scoped_program(result['value'], visible_keys) if scoped_candidate else
                            _candidate(result['value'], arm, dataset, payload, sources, visible_keys))
            except (ValueError, SyntaxError, TypeError, KeyError, jsonschema.SchemaError, jsonschema.ValidationError) as error:
                decision.update(status='invalid_teacher_candidate', error=type(error).__name__)
            else:
                cleaned = {key: value for key, value in before[arm].items() if key != 'snapshot_sha256'}
                draft = {**cleaned, 'batch': batch, 'programs': dict(before[arm]['programs'])}
                if arm == EXTERNAL_ARM:
                    draft['schema_proposals'] = {**schemas, dataset: artifact}
                else:
                    draft['programs'][dataset] = artifact
                library = sealed(draft, 'snapshot_sha256')
                predictions = _measure(actor, library, sources)
                immutable_json(directory / 'measurements.json', {
                    'candidate': artifact, 'library_sha256': library['snapshot_sha256'], 'predictions': predictions,
                })
                scores = _mean(dataset, sources, predictions, grade)
                gain = math.fsum(scores[key] - native_scores[arm][key] for key in keys) / len(keys)
                retain = gain <= 0
                if dataset == CNI and gain > 0:
                    regression = _contract_regression(actor, before[arm], library, earlier_contracts, grade, directory)
                    decision['earlier_TRAIN_regression'] = regression
                    retain = not regression['passed']
                decision.update(status='measured', selected='incumbent' if retain else 'candidate',
                                native_utility_delta=gain, predictions_sha256=digest(predictions), scores=scores)
                if coverage_diagnostic:
                    decision['native_asset_counts'] = native_asset_counts(sources, predictions, grade(OE))
                if not retain:
                    (schemas if arm == EXTERNAL_ARM else programs[arm])[dataset] = artifact
                if arm == ORDINARY:
                    natural_in_scope = dataset == OE and group is not None
                    quantity_in_scope = dataset == DIVERSITY and quantity_group is not None
                    pairs = [{'source': key, 'baseline_utility': native_scores[M2][key],
                              'patch_utility': scores[key]} for key in keys]
                    improves = math.fsum(row['patch_utility'] - row['baseline_utility'] for row in pairs) > 0
                    receipt = {'status': 'retain_incumbent_on_native_train'}
                    if dataset == CNI and improves and retain:
                        receipt['status'] = 'retain_incumbent_on_prior_TRAIN_regression'
                    elif improves:
                        if natural_in_scope:
                            receipt = _validate_relation(reader, out, artifact, group, visible_keys, pairs)
                            if conditioned:
                                evidence = measure_update(reader, out, conditioned, artifact, programs[M2][OE],
                                                          pairs, visible, receipt)
                                receipt = {**receipt, **evidence}
                                if evidence['isolated_shared_rejection_applied']:
                                    receipt['status'] = 'reject_conditioned_shared_title'
                        elif quantity_in_scope:
                            amount_reads = measure_amount(reader, out, artifact, quantity_group)
                            receipt = verify_amount_update(artifact, quantity_group, amount_reads, pairs, visible_keys)
                        else:
                            receipt = {'status': 'eligible_train_update'}
                        if receipt['status'] == 'eligible_train_update':
                            programs[M2][dataset] = artifact
                    relations[dataset] = {**receipt, 'relation_in_scope': natural_in_scope or quantity_in_scope,
                                          'controlled_quantity_relation': quantity_in_scope,
                                          'matched_proposal_sha256': digest(artifact)}
            immutable_json(directory / 'decision.json', decision)
            decisions[arm][dataset] = decision
    provider = diversity_claim_groups.Provider()
    fitter = InterfaceActor(reader, out, plan_assets={}, source_inputs=None, relational_provider=provider,
                            pipeline_binding=binding['source_sha256'])
    fitted = {}
    for arm in sorted(M1_ARMS):
        write_status(out, {'status': 'running', 'batch': batch, 'arm': arm, 'stage': 'interface_fit'}, pointer(batch))
        fitted[arm] = fit_interface_batch(journal, arm, batch, actor=fitter,
            reviewers={'LegalBench_Diversity': diversity_claim_groups.unit_reviews},
            grade_provider=lambda key: grade('LegalBench_Diversity')[key])
    if len({snapshot['snapshot_sha256'] for snapshot, _ in fitted.values()}) != 1:
        raise ValueError('The two M1 arms need the same paired observations under the same channel')
    matched = {'teacher': decisions, 'relation': relations}
    immutable_json(out / 'matched_decisions.json', matched)
    completed = {}
    for arm, initial in before.items():
        current = {**{key: value for key, value in initial.items() if key != 'snapshot_sha256'}, 'batch': batch}
        control = ORDINARY if arm == 'method_one_only' else M2 if arm == 'both' else arm
        current['programs'] = programs[control]
        if arm == EXTERNAL_ARM:
            current['schema_proposals'] = schemas
        if arm in M1_ARMS:
            current['interface_library'] = fitted[arm][0]
        proof = {'visible_prefix_sha256': digest(visible_keys), 'observation_sha256': seals[arm],
                 'decision_binding_sha256': digest(binding), 'program_control_arm': control,
                 'matched_candidate_decisions_sha256': digest(matched),
                 'relation_decisions_sha256': digest(relations) if control == M2 else None,
                 'interface_fit_sha256': digest(fitted[arm][1]) if arm in M1_ARMS else None}
        library = sealed(current, 'snapshot_sha256')
        completed[arm] = journal.commit_update(arm, batch, library, proof, verify_update=lambda old, new, supplied, prefix:
            old == initial and new == library and supplied == proof and list(prefix) == visible_keys
            and digest(read(out / 'matched_decisions.json')) == proof['matched_candidate_decisions_sha256'])
    with ledger.transaction() as db:
        counts = dict(db.execute('select role,count(*) from calls where id like ? and status=? group by role',
                                 (run_id + ':%', 'completed')).fetchall())
        incomplete = db.execute('select 1 from calls where id like ? and status!=?', (run_id + ':%', 'completed')).fetchone()
    if incomplete:
        raise ValueError('Reconcile every dispatched physical call before certifying the fitted batch')
    result = {'status': 'completed_all_five_TRAIN_updates', 'batch': batch,
              'arm_receipts': {arm: row['completed_batch_sha256'] for arm, row in completed.items()},
              'physical_calls': counts, 'matched_decisions_sha256': digest(matched),
              'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, result, pointer(batch))
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    parser.add_argument('--batch', type=int, required=True, choices=range(2, 9))
    args = parser.parse_args()
    (prepare if args.phase == 'prepare' else run)(args.batch)
