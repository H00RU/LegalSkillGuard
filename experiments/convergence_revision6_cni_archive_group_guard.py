"""Compare signed source-screen acquisition on exact early CNI candidate carriers."""

import json
import sqlite3
from pathlib import Path

from experiments import convergence_revision5_cni_scoped_update as b4
from experiments import convergence_revision5_common_native_dev as base
from experiments import convergence_revision6_cni_external_recipients as external
from experiments import convergence_revision6_cni_scoped_adoption as scoped
from experiments import convergence_revision6_cni_agreement_disclosure_release as agreement
from experiments import convergence_revision6_cni_qualification_release as qualification
from experiments.convergence_formal_train_fit import EXTERNAL_ARM, ORDINARY
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_cni_retention_controls import archive_context, bound_stage
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import cni_signed_candidate_groups as guard
from legal_skill_guard.paired_interfaces.control_answers import decode_native, source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_cni_archive_group_guard'
POINTER = HANDOFF / f'{STAGE}_current.json'
CNI = b4.DATASET
CHOICES = ('incumbent', 'proposal')
ROLES = external.acquisition.roles


def observed(journal, arm, batch, source, stage):
    record = read(journal.directory(arm, batch) / 'predictions' / f'{digest(source)}.json')
    receipt = journal._observations(arm, batch)
    if (receipt['train_observation_sha256'] != stage['observation_receipts'][arm]
            or digest(record) != receipt['predictions'][source] or record['source'] != source):
        raise ValueError('Restore the original entering program and its exact observation')
    return record['result']


def physical(db, source, result, program, schema):
    identity, _, transport = ROLES.train_response(db, source, result, schema, program)
    row = json.loads(db.execute('select result from calls where id=?', (identity,)).fetchone()[0])
    request = read(Path(row['artifact_directory']) / 'request.json')['payload']
    if schema is not None:
        trace, = result['schema_reads']
        cell, = b4.common_cells(source)
        bundle = source_bundle(cell)
        codec = ReversibleWire(wire_schema(CNI, bundle), schema)
        transport_schema = record_schema({'value': codec.schema})
        if (trace['source_sha256'] != digest(cell) or trace['finish_reason'] != row['finish_reason']
                or trace['usage'] != row['usage'] or request['response_format']['json_schema']['schema'] != transport_schema):
            raise ValueError('Bind the archived reversible reader and its recorded transport')
        if trace['production_error'] is None:
            normalized, _ = restore_enum_transport(json.loads(row['content']), transport_schema)
            record = codec.restore(normalized['value'])
            answer, evidence = decode_native(CNI, bundle, record)
            if (row['finish_reason'] != 'stop' or record != trace['restored_native_wire']
                    or any(not cell['handled'] or cell['answer'] != answer[task]
                           or cell['evidence_sentence_ids'] != evidence[task]
                           for task, cell in trace['native'].items())):
                raise ValueError('The measured reversible response must reproduce its native labels and evidence')
    user = [message for message in request['messages'] if message['role'] == 'user']
    return identity, digest([transport, user])


def bank_b1(db, journal, roster):
    fit, fs, stop = bound_stage(HANDOFF / 'formal_b1_fit_current.json')
    first, os, initial = bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    if fs['observations_terminal_sha256'] != sha(first / 'terminal.json'):
        raise ValueError('The original B1 fit must use its physical observations')
    bank, positions, ids, hashes = {}, {}, set(), [sha(fit / 'terminal.json')]
    folder = fit / 'candidates' / ORDINARY / CNI
    decision, proposal = (read(folder / filename) for filename in ('decision.json', 'predictions.json'))
    evidence = read(journal.directory(ORDINARY, 1) / 'update_evidence.json')
    receipt = journal._completed_batch(ORDINARY, 1)
    before, after = [journal.library(ORDINARY, k)['programs'][CNI] for k in (0, 1)]
    if (receipt != stop['arms'][ORDINARY] or receipt['update_evidence_sha256'] != digest(evidence)
            or decision != evidence['selected_candidates'][CNI] or decision['selected'] != 'candidate'
            or decision['candidate_sha256'] != digest(after) or decision['predictions_sha256'] != digest(proposal)):
        raise ValueError('Bind the original B1 accepted teacher proposal')
    for batch, rows in enumerate(roster[:3], 1):
        arc, _, obs = (first, os, initial) if batch == 1 else bound_stage(b4.observe_pointer(batch))
        hashes.append(sha(arc / 'terminal.json'))
        old_arm = ORDINARY if batch == 1 else EXTERNAL_ARM
        if journal.library(old_arm, batch - 1)['programs'][CNI] != before \
                or CNI in journal.library(old_arm, batch - 1).get('schema_proposals', {}):
            raise ValueError('Each older B1 carrier must execute the actual B0 program')
        for index, source in enumerate(x for x in rows if x['dataset'] == CNI):
            key = source['key']
            positions[key] = (batch, index)
            older = observed(journal, old_arm, batch, key, obs)
            newer = proposal[key] if batch == 1 else observed(journal, ORDINARY, batch, key, obs)
            pair = [physical(db, source, result, program, None) for result, program in (
                (older, before), (newer, after),
            )]
            verify_pair(pair, ids)
            bank[key] = dict(zip(CHOICES, [older['native'], newer['native']], strict=True))
    return bank, positions, ids, hashes


def verify_pair(pair, used):
    a, b = pair
    if a[0] == b[0] or a[1] != b[1] or a[0] in used or b[0] in used:
        raise ValueError('Match two distinct physical responses with the same exact public input and settings')
    used.update((a[0], b[0]))


def bank_b4(db, journal, roster):
    protocol, _, _, proposal, _, _ = b4.materials()
    fit, _, fit_end = bound_stage(b4.fit_pointer(4))
    _, _, obs4 = bound_stage(b4.observe_pointer(4))
    _, _, obs5 = bound_stage(b4.observe_pointer(5))
    stage = ROOT / read(b4.POINTER)['artifact_root']
    terminal = read(stage / 'terminal.json')
    if (digest(protocol) != stage.name or protocol != read(stage / 'binding.json')
            or sha(fit / 'terminal.json') != protocol['fit_terminal_sha256']
            or sha(stage / 'predictions.json') != terminal['predictions_sha256']
            or terminal['new_calls'] != 3 or not terminal['original_decisions_preserved']):
        raise ValueError('Preserve the original B4 PARSE forward experiment and full response bundles')
    folder = fit / 'candidates' / EXTERNAL_ARM / CNI
    decision = read(folder / 'decision.json')
    decisions = read(fit / 'matched_decisions.json')
    earlier, current = (read(folder / name) for name in ('prior_TRAIN_regression.json', 'measurements.json'))
    if (digest(decisions) != fit_end['matched_decisions_sha256'] or decision != decisions['teacher'][EXTERNAL_ARM][CNI]
            or decision['selected'] != 'incumbent' or digest(earlier) != decision['earlier_TRAIN_regression']['evidence_sha256']
            or digest(current['predictions']) != decision['predictions_sha256']
            or proposal != current['candidate'] or digest(proposal) != protocol['proposal_sha256']):
        raise ValueError('Preserve the exact positive-fit but rejected B4 proposal')
    before = journal.library(EXTERNAL_ARM, 3)['programs'][CNI]
    if before != journal.library(EXTERNAL_ARM, 4)['programs'][CNI]:
        raise ValueError('The earlier B4 baseline must remain the actual B5 entering carrier')
    bank, positions, ids = {}, {}, set()
    saved = read(stage / 'predictions.json')
    for batch, rows in enumerate(roster[:5], 1):
        for index, source in enumerate(x for x in rows if x['dataset'] == CNI):
            key = source['key']
            positions[key] = (batch, index)
            if batch < 4:
                older, newer = earlier['before'][key], earlier['candidate'][key]
            elif batch == 4:
                older = observed(journal, EXTERNAL_ARM, batch, key, obs4)
                newer = current['predictions'][key]
            else:
                older = observed(journal, EXTERNAL_ARM, batch, key, obs5)
                trace = read(stage / 'reads' / f'{index}.json')
                if (trace['source_sha256'] != digest(next(iter(b4.common_cells(source))))
                        or trace['native'] != saved[key]['whole_candidate']
                        or older['native'] != saved[key]['incumbent'] or trace['production_error'] is not None):
                    raise ValueError('Use the exact prior B5 execution of the rejected B4 candidate')
                newer = {'schema_reads': [trace], 'native': trace['native']}
            pair = [physical(db, source, older, before, None), physical(db, source, newer, before, proposal)]
            verify_pair(pair, ids)
            bank[key] = dict(zip(CHOICES, [older['native'], newer['native']], strict=True))
    return bank, positions, ids, [protocol['fit_terminal_sha256'], sha(stage / 'terminal.json')]


def proof_scopes(source):
    """Use conservative determinate subsets from already released source rules."""
    modes = ('Entailment', 'Contradiction', 'NotMentioned', None)
    rules = base.contract_rules(source)
    reference = {}
    for task, adapt in rules.items():
        outputs = [adapt({'answer': mode, 'evidence_sentence_ids': []}) for mode in modes]
        if all(pick == outputs[0] for pick in outputs) and outputs[0]['answer'] is not None:
            reference[task] = outputs[0]
    recipient = ROLES.complete_group(next(v for v in source['views'] if v['id'] == ROLES.TASKS[0]))
    if recipient is not None:
        reference.update(recipient[1])
    for task, hint in (
        (agreement.TASK, agreement.effect(agreement.view_of(source))),
        (qualification.TASK, qualification.source_effect(qualification.contract_view(source))),
    ):
        if hint is not None:
            reference[task] = hint
    paths = external.proof(source)
    if len(paths) == 1 and external.TASK not in reference:
        chain, = paths.values()
        reference[external.TASK] = {'answer': 'Entailment', 'evidence_sentence_ids': chain}
    return {task: {k: row[k] for k in ('answer', 'evidence_sentence_ids')}
            for task, row in reference.items()}


def share(native, proof):
    return {task: {**value, **proof[task], 'handled': True} if task in proof else value for task, value in native.items()}


def score_fit(sources, raw, labels):
    total = {}
    for key, variants in raw.items():
        for role, native in variants.items():
            for row in scoped.native_rows(sources[key], labels[key], native):
                fit = total.setdefault(row['view'], {name: [0.0, 0.0] for name in CHOICES})[role]
                fit[0] += row['correct']
                fit[1] += row['grounded']
    return total


def fit_and_project(bank, positions, fit_batch, sources, labels):
    prefix = {k: v for k, v in bank.items() if positions[k][0] <= fit_batch}
    current = {k: v for k, v in prefix.items() if positions[k][0] == fit_batch}
    forward = {k: v for k, v in bank.items() if positions[k][0] > fit_batch}
    # Proofs are compiled from source alone. Fit labels only affect the matched native gate and native controls.
    proof = {k: proof_scopes(sources[k]) for k in positions}
    shared_bank = {k: {role: share(output, proof[k]) for role, output in vals.items()} for k, vals in bank.items()}
    archive_prefix = {k: shared_bank[k] for k in prefix}
    archive_current = {k: shared_bank[k] for k in current}
    prefix_fit = score_fit({k: sources[k] for k in prefix}, archive_prefix, labels)
    batch_fit = score_fit({k: sources[k] for k in current}, archive_current, labels)
    per_hypothesis = {task: 'proposal' if values['proposal'] > values['incumbent'] else 'incumbent'
                      for task, values in prefix_fit.items()}
    gain = sum(v['proposal'][0] - v['incumbent'][0] for v in batch_fit.values())
    prefix_gain = sum(v['proposal'][0] - v['incumbent'][0] for v in prefix_fit.values())
    groups = {k: {'position': positions[k], **guard.compatibility(raw['incumbent'], raw['proposal'], proof[k]),
                  'disagreement': sum(v['answer'] != raw['proposal'][task]['answer'] for task, v in raw['incumbent'].items()),
                  'proof_tasks': sorted(proof[k])} for k, raw in prefix.items() if proof[k]}
    decisions = guard.select(list(groups.values()), gain)
    decisions['native_prefix_only'] = {'decision': 'proposal' if prefix_gain > 0 else 'incumbent'}
    # A native scoped control can choose among the exact same two readers per hypothesis.
    selected = {**{name: v['decision'] for name, v in decisions.items()},
                'native_per_hypothesis': per_hypothesis, 'incumbent': 'incumbent', 'whole_proposal': 'proposal'}
    output = {}
    for name, choice in selected.items():
        output[name] = {
            k: {task: pair[choice[task]][task] for task in choice} if isinstance(choice, dict) else pair[choice]
            for k, pair in shared_bank.items() if k in forward}
    fit_specs = {'fit_batch': fit_batch, 'same_rules_fit_native_delta': gain,
                 'same_rules_prefix_native_delta': prefix_gain, 'groups': list(groups.values()),
                 'decisions': decisions, 'native_per_hypothesis': per_hypothesis,
                 'mothers': {'fit': len(prefix), 'forward': len(forward)},
                 'certified_source_mothers': sum(bool(q) for q in proof.values())}
    untouched = {role: {key: pair[role] for key, pair in forward.items()} for role in CHOICES}
    return fit_specs, proof, output, untouched


def run():
    root, study, roster = archive_context()
    journal = b4.TrainingJournal(root, study, roster)
    sources = {x['key']: x for rows in roster for x in rows if x['dataset'] == CNI and x['project_split'] == 'train'}
    _, grade_spec, _ = bound_stage(HANDOFF / 'formal_b1_observe_current.json')
    grade_path = grade_spec['native_grade_paths'][CNI]
    if len(sources) != 24 or 'train' not in Path(grade_path).parts or sha(ROOT / grade_path) != grade_spec['native_grade_sha256'][grade_path]:
        raise ValueError('Use the complete original fixed CNI TRAIN and native grade')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        first = bank_b1(db, journal, roster)
        fourth = bank_b4(db, journal, roster)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if len(first[2]) != 18 or len(fourth[2]) != 30 or set(ledger) - {'completed', 'failed'}:
        raise ValueError('Use the original physical pairs with no live generation')
    labels = read(ROOT / grade_path)
    fits, all_proofs, predictions, raw_forward = {}, {}, {}, {}
    for number, archive in ((1, first), (4, fourth)):
        outputs, coordinates, _, _ = archive
        key = str(number)
        fit_labels = {k: labels[k] for k, pos in coordinates.items() if pos[0] <= number}
        fits[key], all_proofs[key], predictions[key], raw_forward[key] = fit_and_project(
            outputs, coordinates, number, sources, fit_labels)
    files = (__file__, guard.__file__, b4.__file__, base.__file__, scoped.__file__,
             external.__file__, qualification.__file__, agreement.__file__)
    spec = {'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'DEV_labels_opened': False,
            'train_grade_sha256': sha(ROOT / grade_path), 'original_stage_sha256': {'1': first[3], '4': fourth[3]},
            'physical_request_ids_sha256': digest(sorted(first[2] | fourth[2])),
            'source_proofs_sha256': digest(all_proofs),
            'decision_locks': {key: digest(lock) for key, lock in fits.items()},
            'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in files}}
    out = BASE / STAGE / digest(spec)
    immutable_json(out / 'binding.json', spec)
    snapshot(out, spec['source_sha256'])
    immutable_json(out / 'source_proofs.json', all_proofs)
    immutable_json(out / 'fit_decisions.json', fits)
    pred_sha = immutable_json(out / 'sealed_predictions.json', predictions)
    results = {}
    for key, bank in predictions.items():
        forward = {k: sources[k] for k in bank['incumbent']}
        comparison = scoped.evaluate(forward, bank, labels)['all']
        raw = score_fit(forward, {k: {role: raw_forward[key][role][k] for role in CHOICES} for k in forward}, labels)
        scores = {role: {'correct': sum(v[role][0] for v in raw.values()),
                         'correct_class_evidence_F1': sum(v[role][1] for v in raw.values()) / (len(raw) * len(forward))}
                  for role in CHOICES}
        results[key] = {**fits[key], 'forward': comparison, 'raw_original_forward': scores}
    terminal = sealed({'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'branches': results,
                       'predictions_sha256': pred_sha, 'archived_physical_reads': len(first[2] | fourth[2]),
                       'archived_branch_reads': {'1': 18, '4': 30}, 'TEST_opened': False,
                       'new_executor_requests': 0, 'new_teacher_requests': 0, 'ledger': ledger}, 'terminal_sha256')
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, {'status': terminal['status'], 'terminal_sha256': terminal['terminal_sha256']}, POINTER)
    print(out, flush=True)


if __name__ == '__main__':
    run()
