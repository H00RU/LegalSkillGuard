"""Measure the original B8 OpenExempt proposal on its omitted TRAIN disclosure anchor."""

import argparse
from dataclasses import asdict
from decimal import Decimal
import inspect
import json
from pathlib import Path
import re
import sqlite3

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, _validate_relation, pointer
from experiments.convergence_m2_forward_oe import selection_decision
from experiments.convergence_m2_train_scope import ownership_groups
from experiments.convergence_oe_component_probe import (
    SCHEMA, SYSTEM, _materials as typed_materials, _measure,
)
from experiments.convergence_oe_conditioned_value_probe import _condition, _source_inputs, _validate
from experiments.convergence_oe_natural_relation import OLD_TRAIN, REGISTRY, reference
from experiments.convergence_oe_title_partition_probe import crossed_groups, joint_group
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.convergence_oe_public_scope import supplied_jurisdiction_scope
from legal_skill_guard.paired_interfaces.shared_semantics import SourceCase, Theory, allowed_relation, source_variant
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'revision5_OE_disclosure_current.json'
HOME = BASE / 'revision5_OE_disclosure_20261119'
DONE = 'completed_revision5_OE_disclosure_TRAIN'


def audited_group(source):
    key = source['key']
    registry = read(REGISTRY)
    parent, = (row for row in read(OLD_TRAIN) if row['key'] == key)
    if (source['project_split'] != 'train' or source['dataset'] != OE or source['views'] != parent['views']
            or digest(parent) != registry['source_public_sha256'][key]):
        raise ValueError('The original TRAIN source must match the source-only review')
    cards = {}
    for row in registry['reviews']:
        if row['source'] != key or row['kind'] != 'asset_program_ports':
            continue
        path = ROOT / row['path']
        card = read(path)
        if (sha(path) != row['sha256'] or card['source_semantic_truth_verified'] is not True
                or card['native_answers_used'] is not False
                or card['native_answers_used_to_create_or_repair_graph'] is not False):
            raise ValueError('Title ambiguity must come from the independent source-only review')
        cards[row['view']] = (row['sha256'], card)
    ec_hash, ec = cards['v0']
    _, ev = cards['v1']
    asset, = (a for a in ec['port_record']['assets'] if a['ownership_evidence']['status'] == 'unknown')
    label = asset['fields']['asset_descriptions']['value']
    quote = asset['ownership_evidence']['quote']
    valuation = asset['fields']['asset_values']
    ec_text, = (view['public']['original_input'] for view in source['views'] if view['id'] == 'EC')
    ev_asset, = (a for a in ev['port_record']['assets'] if a['fields']['asset_descriptions']['value'] == label)
    opening = 'A disclosure of assets by the Debtors reports a '
    pattern = re.escape(opening + label + ' with a current value of ') + r'(\$[0-9,]+\.00)\.'
    match = re.fullmatch(pattern, quote)
    if (not match or ec_text.count(quote) != 1 or ec_text.count(label) != 1
            or ev_asset['ownership_evidence']['status'] != 'unknown' or valuation['status'] != 'stated'):
        raise ValueError('A unique valuation disclosure with no separate title statement is required')
    text_amount = match[1]
    amount = int(text_amount[1:-3].replace(',', ''))
    if amount <= 0 or amount != valuation['value']:
        raise ValueError('The quoted dollar value must agree with the separate source-only review')
    offset = ec_text.index(quote)
    span = (offset + match.start(1), offset + match.end(1))
    jurisdiction = supplied_jurisdiction_scope(ec_text)
    if not jurisdiction or jurisdiction['premise'] != (
            'The Debtors may claim property exemptions under Federal and Wisconsin statutes.'):
        raise ValueError('Bind the actual public jurisdiction of the disclosure source')
    scope = 'OpenExempt:Wisconsin:unchanged_literal_EC'
    theory = Theory(
        {scope: [{'ownership_projection': 'ownership by a current debtor'}]},
        {key: [{'ownership': False}, {'ownership': True}]},
        reference, digest(inspect.getsource(reference)),
        provenance=({'kind': 'independent_source_audit', 'evidence_sha256': ec_hash,
                     'interpretation': 'this asset disclosure states its value and leaves debtor title unresolved'},),
        allowed_edits=frozenset({'amount'}),
    )
    original = SourceCase(key, key, scope, {'text': ec_text, 'asset': label}, {'amount': amount},
                          spans={'amount': ('text', *span)})
    render = (lambda value: f'${value:,}.00') if ',' in text_amount else (lambda value: f'${value}.00')
    edit = source_variant(original, theory, {'amount': amount + 100}, {'amount': render})
    if edit['status'] != 'REALIZABLE' or edit['case'].public['text'] != (
            ec_text[:span[0]] + render(amount + 100) + ec_text[span[1]:]):
        raise ValueError('The compared variants may differ only at the exact valuation span')
    return {'theory': theory, 'cases': [original, edit['case']], 'edit': edit['receipt']}, label


def native_support(source, before, after, labels, asset):
    exact = lambda rows: {(r['citation'], Decimal(str(r['claim_value']))) for r in rows}
    target = exact(labels['EV']['answer'][asset])
    counts = {role: len(exact(native['EV']['answer'][asset]) & target)
              for role, native in (('incumbent', before), ('candidate', after))}
    scores = {role: {task['id']: grade_view(OE, task, labels[task['id']], native[task['id']]['answer'])['grade']
                     for task in source['views']}
              for role, native in (('incumbent', before), ('candidate', after))}
    task, = (task for task in source['views'] if task['id'] == 'EV')
    swap = {**before['EV']['answer'], asset: after['EV']['answer'][asset]}
    swapped_grade = grade_view(OE, task, labels['EV'], swap)['grade']
    if counts['candidate'] <= counts['incumbent'] or swapped_grade <= scores['incumbent']['EV']:
        raise ValueError('The omitted anchor needs a localized measured native gain')
    return {'source_native_scores': scores, 'exact_EV_claims_for_omitted_asset': counts,
            'incumbent_EV_replay_with_candidate_asset': swapped_grade}


def materials():
    original, signal, visible, _, programs = typed_materials()
    fit = ROOT / read(pointer(8))['artifact_root']
    fit_binding = read(fit / 'binding.json')
    stage = ROOT / fit_binding['observations_root']
    root = ROOT / fit_binding['checkpoint_root']
    study = read(root / 'binding.json')
    batches = load_roster(study)
    journal = TrainingJournal(root, study, batches)
    native = signal['native_comparisons']
    winner, = (row for row in native if row['patch_utility'] > row['baseline_utility'])
    if len(native) != 4 or any(row['patch_utility'] < row['baseline_utility'] for row in native):
        raise ValueError('Use the unique improving mother of the sealed four-source B8 comparison')
    key = winner['source']
    source, = (s for s in batches[7] if s['key'] == key)
    former, _ = ownership_groups(visible)
    if key in former:
        raise ValueError('This development experiment concerns a genuinely omitted anchor')
    group, label = audited_group(source)
    projected_group = joint_group(crossed_groups(group))
    theory, shared, independent = _condition(projected_group)
    projected = projected_group['cases']
    context = {'cases': projected, 'inputs': _source_inputs(projected), 'theory': theory}

    before = read(journal.directory(M2, 8) / 'predictions' / (digest(key) + '.json'))
    if journal._observations(M2, 8)['predictions'][key] != digest(before):
        raise ValueError('The incumbent native result must match its sealed TRAIN observation')
    path = fit / 'candidates' / ORDINARY / OE
    after = read(path/'measurements.json')
    if digest(after['predictions']) != read(path/'decision.json')['predictions_sha256']:
        raise ValueError('The proposal native result must match its measured TRAIN receipt')
    grades = read(stage / 'binding.json')
    grade_path = grades['native_grade_paths'][OE]
    if sha(ROOT/grade_path) != grades['native_grade_sha256'][grade_path]:
        raise ValueError('Only the original sealed TRAIN annotations may score the two policies')
    support = native_support(source, before['result']['native'], after['predictions'][key]['native'],
                             read(ROOT/grade_path)[key], label)
    for role, field in (('incumbent', 'baseline_utility'), ('candidate', 'patch_utility')):
        if sum(support['source_native_scores'][role].values())/2 != winner[field]:
            raise ValueError('The native localization must reproduce the sealed utility')
    literal_shared = allowed_relation(group['theory'], group['cases'])
    source_paths = {*original['source_sha256'],
                    str(Path(__file__).resolve().relative_to(ROOT)), 'experiments/convergence_m2_update_probe.py',
                    'legal_skill_guard/paired_interfaces/shared_semantics_validation.py'}
    binding = {'study': 'revision5_OpenExempt_omitted_B8_disclosure', 'executor': fit_binding['executor'],
               'fit_terminal_sha256': original['B8_terminal_sha256'], 'program_sha256': original['program_sha256'],
               'native_utility_pairs_sha256': digest(native), 'native_localization': support,
               'source_only_disclosure_evidence': group['theory'].provenance,
               'source_edit_sha256': digest(group['edit']), 'literal_signatures_sha256': digest(literal_shared['signatures']),
               'literal_cases_sha256': digest([asdict(c) for c in group['cases']]),
               'projected_queries_sha256': digest(context['inputs']), 'typed_reader_sha256': digest([SYSTEM, SCHEMA]),
               'projection_signature_sha256': {x: digest(v['signatures'])
                                                for x, v in (('shared', shared), ('independent', independent))},
               'expected_new_executor_calls': 10, 'expected_new_native_calls': 0, 'TEST_opened': False,
               'source_sha256': {p: sha(ROOT/p) for p in sorted(source_paths)}}
    # JSON writes provenance tuples as lists. Use the exact serialized binding on re-entry.
    return json.loads(json.dumps(binding)), visible, key, group, context, native, programs


def run(execute):
    if POINTER.exists():
        saved = read(POINTER)
        if saved['status'] == DONE:
            print(saved['artifact_root'], flush=True)
            return
    binding, visible, key, group, context, native, programs = materials()
    stage = HOME / digest(binding)
    if execute and (not POINTER.exists() or ROOT/read(POINTER)['artifact_root'] != stage):
        raise ValueError('Run only the prepared immutable experiment')
    immutable_json(stage/'binding.json', binding)
    immutable_json(stage/'preflight.json', {'native': binding['native_localization'],
                                          'scope': 'TRAIN', 'new_model_calls': 0})
    if not execute:
        if POINTER.exists() and read(POINTER)['status'] == 'running':
            raise ValueError('Preserve the active run')
        write_status(stage, {'status': 'prepared', 'executor_calls_planned': 10}, POINTER)
        print(stage.relative_to(ROOT), flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Reconcile the serial executor before dispatch')
    for name, value in binding['source_sha256'].items():
        archive = stage/'source_snapshot'/name
        archive.parent.mkdir(parents=True, exist_ok=True)
        if not archive.exists():
            with archive.open('xb') as file:
                file.write((ROOT/name).read_bytes())
        if sha(archive) != value:
            raise ValueError('The new experiment source snapshot changed')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-revision5-OE-disclosure-'+stage.name[:16],
                             sources={'train': [key], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, stage, binding['executor'])
    reader.readiness()
    write_status(stage, {'status': 'running', 'step': 'literal'}, POINTER)
    literal = _validate_relation(reader, stage, programs['candidate'], group, [s['key'] for s in visible], native)
    neutral = [{**row, 'patch_utility': row['baseline_utility']} for row in native]
    results = {}
    for role, program in programs.items():
        write_status(stage, {'status': 'running', 'step': role}, POINTER)
        rows = _measure(reader, stage, program, context)
        validation, summary = _validate(context['theory'], context['cases'], rows, program,
                                        native if role == 'candidate' else neutral, visible)
        results[role] = {'reads': rows, 'validation': validation,
                         'summary': {**summary, 'all_queries_observed': all(r['value'] is not None for r in rows)}}
    paired = selection_decision(results['candidate']['summary'], results['incumbent']['summary'], literal['status'])
    with ledger.transaction() as db:
        calls = db.execute('select status,result from calls where id like ?', (ledger.run_id+':%',)).fetchall()
    if len(calls) != binding['expected_new_executor_calls'] or any(status != 'completed' for status,_ in calls):
        raise ValueError('Seal only the full matched physical comparison')
    terminal = {'status': DONE, 'native_localization': binding['native_localization'],
                'literal': literal, 'results': results, 'selection': paired,
                'executor_calls': len(calls), 'executor_tokens': sum(json.loads(v)['usage']['total_tokens']
                                                                   for _,v in calls),
                'teacher_calls': 0, 'new_native_calls': 0, 'TEST_opened': False}
    immutable_json(stage/'terminal.json', terminal)
    write_status(stage, {'status': DONE, 'executor_calls': len(calls)}, POINTER)
    print(json.dumps({'selection': paired, 'literal_status': literal['status'],
                      'calls': len(calls), 'tokens': terminal['executor_tokens']}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    run(parser.parse_args().phase == 'run')
