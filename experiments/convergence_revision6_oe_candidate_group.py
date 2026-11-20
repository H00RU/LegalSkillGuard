"""Compare refutation-based group acquisition on two original reader portfolios."""

import json
import sqlite3
from pathlib import Path
from statistics import mean

from experiments import convergence_revision6_oe_illinois_eligibility as published_rules
from experiments import convergence_revision6_oe_joint_acquisition as archive
from experiments.convergence_formal_train_fit import EXTERNAL_ARM
from experiments.convergence_formal_train_observe import pointer as observe_pointer
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from experiments.convergence_revision5_m2_cumulative_audit import physical_wire
from experiments.convergence_revision6_maud_covenant_fit import snapshot
from legal_skill_guard.paired_interfaces import convergence_oe_candidate_group as selection
from legal_skill_guard.paired_interfaces.control_answers import (
    decode_native,
    source_bundle,
    wire_schema,
)
from legal_skill_guard.paired_interfaces.convergence_actors import common_cells
from legal_skill_guard.paired_interfaces.convergence_ev_inventory import with_ev_inventory
from legal_skill_guard.paired_interfaces.convergence_schema_control import ReversibleWire
from legal_skill_guard.paired_interfaces.formal_evaluation import sealed
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import request_payload
from legal_skill_guard.skill_evolution.native import record_schema, restore_enum_transport
from legal_skill_guard.skill_evolution.objects import digest

STAGE = 'revision6_oe_candidate_group'
POINTER = HANDOFF / f'{STAGE}_current.json'
BATCHES = (4, 7)
ROLES = ('incumbent', 'proposal', 'parse')


def restore_parse(db, source, result, proposal, config):
    if config.get('ev_asset_inventory_wire'):
        source = with_ev_inventory(source, jurisdiction_scope=config.get('oe_public_jurisdiction_scope', False))
    roles, physical = {}, set()
    for cell, trace in zip(common_cells(source), result['schema_reads'], strict=True):
        key, identity = cell['key'], trace['physical_call_id']
        physical_wire(db, {key}, identity, key)
        (body,) = db.execute('select result from calls where id=?', (identity,)).fetchone()
        raw = json.loads(body)
        payload = read(Path(raw['artifact_directory']) / 'request.json')['payload']
        bundle = source_bundle(cell)
        codec = ReversibleWire(wire_schema(archive.OE, bundle), proposal)
        schema = record_schema({'value': codec.schema})
        user, = (row['content'] for row in payload['messages'] if row['role'] == 'user')
        if (json.loads(user) != {'public': bundle['public'], 'answer_schema': bundle['answer_schema']}
                or payload != request_payload(config['executor'], messages=payload['messages'],
                                              thinking=False, schema=schema)
                or trace['source_sha256'] != digest(cell) or trace['proposal_sha256'] != digest(proposal)
                or digest(raw['content']) != trace['response_sha256'] or raw['usage'] != trace['usage']
                or raw['finish_reason'] != trace['finish_reason'] or result['fallback_executed']):
            raise ValueError('Require the exact original PARSE request, source, program and response')
        task, = trace['native']
        saved = trace['native'][task]
        if result['native'][task] != saved:
            raise ValueError('Match the original per-task decoder')
        if raw['finish_reason'] == 'stop' and trace['production_error'] is None:
            restored, _ = restore_enum_transport(json.loads(raw['content']), schema)
            native_wire = codec.restore(restored['value'])
            answer, evidence = decode_native(archive.OE, bundle, native_wire)
            if (native_wire != trace['restored_native_wire'] or not saved['handled']
                    or saved['answer'] != answer[task] or saved['evidence_sentence_ids'] != evidence[task]):
                raise ValueError('Require a lossless replay of the archived reader')
            roles[task] = saved['answer']
        elif saved['handled']:
            raise ValueError('An incomplete response cannot supply acquired evidence')
        else:
            roles[task] = None
        physical.add(identity)
    if set(roles) != set(archive.PORTS) or len(physical) != len(archive.PORTS):
        raise ValueError('Both tasks must have separate original reads')
    ev = archive.archive.assets.scopes(archive.archive.assets.dev_archive.ev_view(source),
                                     roles['EV'])['same_public_jurisdiction']
    ec = archive.ec.common_scope(archive.ec.view_for(source), roles['EC'])
    return {'EC': ec, 'EV': ev}, physical


def extend_with_archived_candidates(db, cases):
    formal = archive.FORMAL
    bound_stage = archive.archive.prior.archive.bound_stage
    stamps, matches = {}, set()
    for batch, pair in cases.items():
        fit, spec, terminal = bound_stage(formal.pointer(batch))
        observe, forward, observed = bound_stage(observe_pointer(batch + 1))
        decisions = read(fit / 'matched_decisions.json')
        decision = decisions['teacher'][EXTERNAL_ARM][archive.OE]
        parsed = read(fit / 'candidates' / EXTERNAL_ARM / archive.OE / 'measurements.json')
        root = ROOT / spec['checkpoint_root']
        study = read(root / 'binding.json')
        roster = formal.load_roster(study)
        journal = archive.archive.exact.TrainingJournal(root, study, roster)
        saved_library = journal.library(EXTERNAL_ARM, batch)
        schema = parsed['candidate']
        if (terminal['matched_decisions_sha256'] != digest(decisions)
                or digest(parsed['predictions']) != decision['predictions_sha256']
                or decision['selected'] != 'candidate' or schema != saved_library['schema_proposals'][archive.OE]
                or spec['executor'] != study['executor'] or forward['executor'] != study['executor']
                or forward['checkpoint_root'] != spec['checkpoint_root']
                or observed['observation_receipts'][EXTERNAL_ARM]
                != journal._observations(EXTERNAL_ARM, batch + 1)['train_observation_sha256']):
            raise ValueError('Use only the verified original learned schema and its next-batch reads')
        pair['programs']['parse'] = digest(schema)
        stamps[batch] = {'fit': sha(fit / 'terminal.json'), 'forward': sha(observe / 'terminal.json'),
                         'external_program': digest(schema)}
        for phase, n, config in (('train', batch, spec), ('forward', batch + 1, forward)):
            cohort = [s for s in roster[n - 1] if s['dataset'] == archive.OE and s['project_split'] == 'train']
            if len(cohort) != 4 or {s['key'] for s in cohort} != set(pair[phase]):
                raise ValueError('Keep all four original OpenExempt mothers in each batch')
            for source in cohort:
                key = source['key']
                result = (parsed['predictions'][key] if phase == 'train' else
                          archive.archive.raw_prediction(journal, EXTERNAL_ARM, n, key))
                if phase == 'forward' and result['schema_library_sha256'] != saved_library['snapshot_sha256']:
                    raise ValueError('Only reuse an actual read of the candidate training library')
                native, ids = restore_parse(db, source, result, schema, config)
                pair[phase][key]['answers']['parse'] = native
                matches.update(ids)
    return stamps, matches


def same_controls(row):
    views = row['views']
    exclusions = {task: published_rules.policy.exclusions(view) for task, view in views.items()}
    answers = {}
    for role, bank in row['answers'].items():
        cleaned = archive.common(views, bank, True)
        answers[role] = {task: published_rules.filter_claims(task, native, exclusions[task])
                         if native is not None else None for task, native in cleaned.items()}
    return {**row, 'answers': answers}


def fit(batch, labels):
    readings = {key: row['answers'] for key, row in batch.items()}
    native = archive.scored(batch, readings, labels)
    utilities = {role: mean(r['grade'] for r in values) for role, values in native.items()}
    gain = {role: value - utilities['incumbent'] for role, value in utilities.items()}
    groups = {}
    for row in batch.values():
        if any(x is None for answers in row['answers'].values() for x in answers.values()):
            continue
        incoming = row['answers']['incumbent']
        groups[row['position']] = {
            role: archive.group_evidence(
                {**row, 'answers': {'incumbent': incoming, 'proposal': row['answers'][role]}}, True,
            )['whole_proposal'] for role in ROLES[1:]
        }
    return {'groups': groups, 'candidate_native_gain': gain, 'choices': selection.choose(groups, gain)}


def run():
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        complete, _, old_ev, ref = archive.archive.history(db)
        cases = {batch: complete[batch] for batch in BATCHES}
        ec = archive.extract(db, cases)
        receipts, external = extend_with_archived_candidates(db, cases)
        ledger = dict(db.execute('select status,count(*) from calls group by status'))
    if ledger.get('reserved') or len(external) != 32 or external & (set(ec) | set(old_ev)):
        raise ValueError('All sixteen source uses have two original PARSE reads')
    grade, expected = ref
    path = ROOT / grade
    if 'train' not in path.parts or sha(path) != expected:
        raise ValueError('Use only the original TRAIN references')
    cases = {batch: {**paired, **{split: {key: same_controls(row) for key, row in paired[split].items()}
                                  for split in ('train', 'forward')}} for batch, paired in cases.items()}
    paths = (__file__, selection.__file__, archive.__file__, published_rules.__file__,
             published_rules.policy.__file__)
    binding = {
        'stage': STAGE, 'partition': 'TRAIN', 'TEST_opened': False, 'matched_portfolios': receipts,
        'TRAIN_grade_sha256': expected, 'pairwise_cases_sha256': digest(cases),
        'all_checked_physical_ids_sha256': digest(sorted(external | set(ec) | set(old_ev))),
        'source_sha256': {str(Path(f).relative_to(ROOT)): sha(Path(f)) for f in paths},
        'design': 'Retrospective comparison on B4/B7, where both original proposals have same-source '
                  'next-batch reads. The screen and portfolio are identical across group policies.',
    }
    out = BASE / STAGE / digest(binding)
    immutable_json(out / 'binding.json', binding)
    snapshot(out, binding['source_sha256'])
    fit_rows, forward, predictions = {}, {}, {}
    for batch, paired in cases.items():
        labels = {key: read_label for key, read_label in read(path).items() if key in paired['train']}
        result = fit_rows[batch] = fit(paired['train'], labels)
        for name, choice in result['choices'].items():
            library = sealed({'choice': choice, 'batch': batch, 'binding_sha256': out.name,
                              'chosen_reader_sha256': paired['programs'][choice['selected']]}, 'snapshot_sha256')
            immutable_json(out / 'TRAIN_batch_libraries' / f'B{batch}' / f'{name}.json', library)
        for key, row in paired['forward'].items():
            forward[key] = row
            predictions[key] = {'incumbent': row['answers']['incumbent'], **{
                name: row['answers'][choice['selected']] for name, choice in result['choices'].items()}}
    pred = immutable_json(out / 'sealed_predictions.json', predictions)
    labels = read(path)
    by_batch = {batch: archive.summary(paired['forward'], {k: predictions[k] for k in paired['forward']}, labels)
                for batch, paired in cases.items()}
    all_scores = archive.summary(forward, predictions, labels)
    effect = all_scores['paired_candidate_driven']
    advance = all(effect[name]['paired_source_bootstrap_95'][0] > 0
                  for name in selection.POLICIES if name != 'candidate_driven')
    t = sealed({
        'status': f'settled_{STAGE}', 'binding_sha256': out.name, 'predictions_sha256': pred,
        'fit': fit_rows, 'next_batch_TRAIN': by_batch, 'all_next_batch_TRAIN': all_scores,
        'fit_and_forward_mothers': len(forward) * 2, 'new_executor_requests': 0, 'new_teacher_requests': 0,
        'checked_old_requests': len(external | set(ec) | set(old_ev)), 'checked_original_PARSE_requests': len(external),
        'support_expanded_validation': advance, 'ledger': ledger, 'TEST_opened': False,
    }, 'terminal_sha256')
    immutable_json(out / 'terminal.json', t)
    write_status(out, {'status': t['status'], 'terminal_sha256': t['terminal_sha256']}, POINTER)
    print(out)


if __name__ == '__main__':
    run()
