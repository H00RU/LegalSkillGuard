"""Compare a typed title-allocation read on the original fixed TRAIN probe."""

import argparse
import json
import sqlite3
from collections import Counter

import jsonschema

from experiments.convergence_formal_b1_observe import load_roster
from experiments.convergence_formal_train_fit import M2, OE, ORDINARY, pointer as fit_pointer
from experiments.convergence_m2_forward_oe import prepare_conditioning, selection_decision
from experiments.convergence_oe_conditioned_value_probe import _validate
from experiments.convergence_oe_scoped_proposal import projection_policy
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.convergence_journal import TrainingJournal
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'B8_OE_typed_component_current.json'
SCHEMA = record_schema({'allocation': {'type': 'string', 'enum': ['full', 'zero', 'unresolved']}})
SYSTEM = (
    'Choose the allocation for the requested component of the named asset. '
    'Under debtor ownership, the forwarded component receives the full value and the withheld component '
    'receives zero. Under nonownership, the withheld component receives the full value and the forwarded '
    'component receives zero. Use the supplied program to interpret the source-level title evidence. '
    'The stated valuation by itself determines neither title nor the allocation. If the policy leaves '
    'the component unresolved, return unresolved. Otherwise return full or zero for the requested '
    'component. Return only the allocation tag.'
)


def decode(response, amount):
    if type(amount) is not int or amount <= 0:
        raise ValueError('The fixed probe requires a positive, independently verified whole-dollar valuation')
    if response['finish_reason'] != 'stop':
        raise ValueError('The typed projection response did not complete')
    document = json.loads(response['content'])
    jsonschema.validate(document, SCHEMA)
    tag = document['allocation']
    return tag, {'full': amount, 'zero': 0, 'unresolved': None}[tag]


def _materials():
    stage = ROOT / read(fit_pointer(8))['artifact_root']
    original = read(stage / 'binding.json')
    terminal = read(stage / 'terminal.json')
    archive = read(stage / 'source_snapshot_receipt.json')
    matched = read(stage / 'matched_decisions.json')
    if (stage.name != digest(original) or terminal['status'] != 'completed_all_five_TRAIN_updates'
            or terminal['batch'] != 8 or terminal['TEST_opened']
            or terminal['matched_decisions_sha256'] != digest(matched)
            or archive['files'] != original['source_sha256'] or archive['archived_terminal_binding'] != stage.name):
        raise ValueError('The typed probe requires the exact settled B8 fit')
    signal = matched['relation'][OE]
    prior = signal['conditioned_projection']
    controls = signal['candidate_selected_by']
    if (signal['status'] != 'eligible_train_update' or not controls['native_only'] or not controls['literal_only']
            or not controls['independent_completions'] or controls['shared_explanation']
            or prior['comparison']['incumbent']['shared_compatible']
            or signal['isolated_shared_rejection_applied']):
        raise ValueError('Use the recovered literal match and measured B8 component failure')
    checkpoint = ROOT / original['checkpoint_root']
    study = read(checkpoint / 'binding.json')
    if digest(study) != original['study_binding_sha256']:
        raise ValueError('The B8 comparison study changed')
    batches = load_roster(study)
    visible = [source for group in batches for source in group]
    journal = TrainingJournal(checkpoint, study, batches)
    context = prepare_conditioning(visible, original['executor'])
    if context['binding'] != prior['binding']:
        raise ValueError('The comparison must use the original audited pilot source and components')
    expected = [row['independently_verified_source_facts']['stated_value_dollars'] for row in context['inputs']]
    for role in ('incumbent', 'candidate'):
        projection = prior['evidence'][role]['reads']
        if [row['value'] for row in projection] != expected or any(row['failure'] is not None for row in projection):
            raise ValueError('The typed probe requires the measured repetition of the full amount for both programs')
    measured = read(stage / 'candidates' / ORDINARY / OE / 'measurements.json')
    candidate = measured['candidate']
    if digest(candidate) != signal['matched_proposal_sha256']:
        raise ValueError('Recover the original matched B8 proposal')
    programs = {'incumbent': journal.library(M2, 7)['programs'][OE], 'candidate': candidate}
    if journal.library(M2, 8)['programs'][OE] != candidate:
        raise ValueError('Use the actual saved training decisions')
    files = {*original['source_sha256'], 'experiments/convergence_oe_component_probe.py'}
    binding = {'stage': stage.name, 'B8_terminal_sha256': sha(stage / 'terminal.json'),
               'original_comparison_sha256': digest(prior), 'original_context': context['binding'],
               'program_sha256': {role: digest(program) for role, program in programs.items()},
               'wire_sha256': digest([SYSTEM, SCHEMA]), 'executor': original['executor'],
               'source_sha256': {f: sha(ROOT / f) for f in sorted(files)},
               'TEST_opened': False}
    return binding, signal, visible, context, programs


def _measure(reader, out, program, context):
    rows = []
    for case, query in zip(context['cases'], context['inputs'], strict=True):
        amount = query['independently_verified_source_facts']['stated_value_dollars']
        payload = {**query, 'quoted_reader_policy': projection_policy(program, query)}
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(
            payload, ensure_ascii=False, sort_keys=True)}]
        identity = reader.ledger.run_id + ':component:' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=case.root_id, purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        verify_physical_response(reader, identity=identity, source=case.root_id, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            tag, value = decode(raw, amount)
            failure = None
        except (ValueError, jsonschema.ValidationError) as exc:
            tag, value, failure = None, None, type(exc).__name__
        row = {'case': case.source_id, 'source_sha256': digest(case.public), 'physical_call_id': identity,
               'read_tag': tag, 'value': value, 'failure': failure, 'input_sha256': digest(payload)}
        immutable_json(out / 'projection_reads' / (digest(identity) + '.json'), row)
        rows.append(row)
    return rows


def main(execute):
    binding, signal, visible, context, programs = _materials()
    out = BASE / 'B8_OE_typed_component' / digest(binding)
    if execute and (not POINTER.exists() or ROOT / read(POINTER)['artifact_root'] != out):
        raise ValueError('Use the prepared source, programs, and typed request contract')
    immutable_json(out / 'binding.json', binding)
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')['summary'], sort_keys=True), flush=True)
        return
    if (HANDOFF / 'formal_B8_TEST_current.json').exists():
        raise ValueError('Run the diagnostic before freezing the final TEST')
    if not execute:
        write_status(out, {'status': 'prepared', 'physical_calls_planned': 8, 'TEST_opened': False}, POINTER)
        print(out.relative_to(ROOT), flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('The serial executor is still in use')
    root, = {row.root_id for row in context['cases']}
    run_id = 'convergence-B8-OE-typed-component-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [root], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()

    native = signal['native_comparisons']
    neutral = [{**row, 'patch_utility': row['baseline_utility']} for row in native]
    details, summaries = {}, {}
    for role, program in programs.items():
        write_status(out, {'status': 'running', 'arm': role, 'TEST_opened': False}, POINTER)
        rows = _measure(reader, out, program, context)
        validation, summary = _validate(context['theory'], context['cases'], rows, program,
                                        native if role == 'candidate' else neutral, visible)
        summaries[role] = {**summary, 'all_queries_observed': all(row['value'] is not None for row in rows)}
        details[role] = {'reads': rows, 'validation': validation,
                         'tag_counts': dict(Counter(row['read_tag'] or 'invalid' for row in rows))}
    outcome = selection_decision(summaries['candidate'], summaries['incumbent'], signal['status'])
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if len(physical) != 8 or any(status != 'completed' for status, _ in physical):
        raise ValueError('Both programs require four distinct physically settled typed responses')
    result = {'status': 'completed_B8_OE_typed_component_diagnostic', 'summary': {**outcome, 'programs': summaries},
              'details': details, 'executor_calls': len(physical),
              'executor_tokens': sum(json.loads(raw)['usage']['total_tokens'] for _, raw in physical),
              'teacher_calls': 0, 'native_calls': 0, 'training_library_changes': 0, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'executor_calls': len(physical), 'TEST_opened': False}, POINTER)
    print(json.dumps(result['summary'], sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    main(parser.parse_args().phase == 'run')
