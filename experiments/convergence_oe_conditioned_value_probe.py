"""Read only derived values under the same independently audited TRAIN facts."""

import argparse
from dataclasses import replace
import inspect
import json
import sqlite3

import jsonschema

from experiments.convergence_oe_title_partition_probe import POINTER as PRIOR, _bound as crossed_binding
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.shared_semantics import allowed_relation
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_oe_conditioned_value_current.json'
AUDIT = HANDOFF / 'M2_title_partition_signal_audit_20261118.json'
SCHEMA = record_schema({'value': {'type': ['integer', 'null'], 'minimum': 0}})
SYSTEM = (
    'Return only the requested intermediate value for the stated named asset. The independently verified '
    'facts concern what the text states and leaves unresolved. Use the supplied program as guidance for '
    'which contribution it computes. Under debtor ownership, the entire stated value is forwarded and '
    'nothing is withheld. Under nonownership, the entire stated value is withheld and nothing is forwarded. '
    'The requested component is either forwarded or withheld. Do not treat unresolved title as proven '
    'nonownership or ownership. When the program cannot determine the value, return null. Do not return '
    'a source quotation, a native classification, or a statement of literal title.'
)


def _value(values, law):
    return values['title_filtered_value']


def _condition(joint):
    prior = joint['theory']
    theory = replace(prior, reference=_value, reference_sha256=digest([prior.reference_sha256,
                                                                     inspect.getsource(_value)]))
    cases = joint['cases']
    shared = allowed_relation(theory, cases)
    independent = allowed_relation(theory, cases, mode='independent_completions')
    if len(shared['signatures']) != 2 or len(independent['signatures']) != 16:
        raise ValueError('The derived-value task must preserve the original cross-query relationship')
    return theory, shared, independent


def _bound():
    crossed, _, joint, programs, native, visible = crossed_binding()
    previous = ROOT / read(PRIOR)['artifact_root']
    terminal = read(previous / 'terminal.json')
    audit = read(AUDIT)
    reason = audit['audited']['candidate']
    if (previous.name != digest(crossed) or previous.name != audit['binding']
            or sha(previous / 'terminal.json') != audit['terminal_sha256']
            or terminal['status'] != 'completed_M2_natural_title_partition_probe' or terminal['TEST_opened']
            or reason['exact_stated_amounts'] != 4 or reason['exact_quote_verified'] != 0
            or reason['literal_title_assertions_rejected'] != 3
            or reason['matching_signatures_after_masking_literal_title'] != {'independent': 2, 'shared': 0}):
        raise ValueError('The frozen prior measurements must identify the literal channel as the confound')
    theory, shared, independent = _condition(joint)
    inputs = []
    for case in joint['cases']:
        amount = case.interventions.get('amount', case.primitives['amount'])
        inputs.append({'source': case.public['text'], 'named_asset': case.public['asset'],
                       'requested_component': case.primitives['requested_component'],
                       'independently_verified_source_facts': {'stated_value_dollars': amount,
                                                               'title_status': 'unresolved by the literal source'}})
    if len({case.root_id for case in joint['cases']}) != 1 or not theory.provenance:
        raise ValueError('A conditional read requires the audited source-only provenance')
    files = set(crossed['source_sha256']) | {'experiments/convergence_oe_conditioned_value_probe.py'}
    binding = {'study': 'OE_shared_title_conditioned_on_independently_audited_literal_K',
               'executor': crossed['executor'], 'root': crossed['root'], 'native_pairs_sha256': digest(native),
               'programs_sha256': crossed['programs_sha256'], 'previous_signal_audit_sha256': sha(AUDIT),
               'shared_signatures_sha256': digest(shared['signatures']),
               'independent_signatures_sha256': digest(independent['signatures']),
               'source_query_inputs_sha256': digest(inputs), 'local_contract_sha256': digest([SYSTEM, SCHEMA]),
               'literal_facts_from_independent_source_audit': True, 'literal_facts_supplied_equally': True,
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)}}
    return binding, theory, joint['cases'], inputs, programs, native, visible


def prepare():
    binding, *_ = _bound()
    out = BASE / 'm2_oe_conditioned_value' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'projected_values': 8, 'new_native_requests': 0,
                           'shared_signatures': 2, 'independent_signatures': 16}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


def _measure(reader, out, cases, inputs, program):
    rows = []
    policy = '\n'.join(p['prompt'] for p in program['predicates'])
    for case, query in zip(cases, inputs, strict=True):
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': json.dumps(
            {**query, 'quoted_reader_policy': policy}, ensure_ascii=False, sort_keys=True)}]
        identity = reader.ledger.run_id + ':value:' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=case.root_id, purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        verify_physical_response(reader, identity=identity, source=case.root_id, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            if raw['finish_reason'] != 'stop':
                raise ValueError('The projected value did not complete')
            out_value = json.loads(raw['content'])
            jsonschema.validate(out_value, SCHEMA)
            value, failure = out_value['value'], None
        except (ValueError, jsonschema.ValidationError) as error:
            value, failure = None, type(error).__name__
        row = {'case': case.source_id, 'source_sha256': digest(case.public), 'input_sha256': digest(query),
               'physical_call_id': identity, 'value': value, 'failure': failure}
        immutable_json(out / 'projection_reads' / (digest(identity) + '.json'), row)
        rows.append(row)
    return rows


def _validate(theory, cases, rows, program, native, visible):
    version = digest(program)
    records = {r['case']: r for r in rows}
    result = validate_patch(theory, version, [{'cases': cases, 'outputs': [r['value'] for r in rows],
                  'physical_call_ids': [r['physical_call_id'] for r in rows]}], native,
        visible_train=[row['key'] for row in visible], verify_projection=lambda patch, identity, case, value:
        patch == version and records[case.source_id]['source_sha256'] == digest(case.public)
        and (records[case.source_id]['physical_call_id'], records[case.source_id]['value']) == (identity, value),
        verify_native_pair=lambda patch, row: patch == version and row in native)
    control, = result['matched_controls']
    admissible = all(row['failure'] is None for row in rows) and any(row['value'] is not None for row in rows)
    independent = admissible and control['independent_per_case_compatible']
    shared = admissible and control['shared_prefix_compatible']
    positive = result['native_utility_sum_delta'] > 0
    separated = positive and independent and not shared
    return result, {'independent_compatible': independent, 'shared_compatible': shared,
                    'single_compatible': admissible and control['single_witness_compatible'],
                    'native_positive': positive, 'isolated_shared_rejection': separated,
                    'all_outputs_unresolved': all(row['value'] is None for row in rows)}


def run():
    binding, theory, cases, inputs, programs, native, visible = _bound()
    out = ROOT / read(POINTER)['artifact_root']
    if out.name != digest(binding) or read(out / 'binding.json') != binding:
        raise ValueError('The exact audited K, query or model evidence changed')
    if (out / 'terminal.json').exists():
        print(json.dumps(read(POINTER), sort_keys=True), flush=True)
        return
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Wait for the active serial phase to settle')
    run_id = 'convergence-M2-OE-conditioned-value-' + out.name[:16]
    ledger = EvolutionLedger(LEDGER, run_id=run_id, sources={'train': [binding['root']], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    measured, summary = {}, {}
    neutral = [{**row, 'patch_utility': row['baseline_utility']} for row in native]
    for arm, program in programs.items():
        write_status(out, {'status': 'running', 'arm': arm}, POINTER)
        rows = _measure(reader, out, cases, inputs, program)
        validation, summary[arm] = _validate(theory, cases, rows, program, native if arm == 'candidate' else neutral, visible)
        measured[arm] = {'reads': rows, 'validation': validation}
    with ledger.transaction() as db:
        physical = db.execute('select status,result from calls where id like ?', (run_id + ':%',)).fetchall()
    if len(physical) != 8 or any(status != 'completed' for status, _ in physical):
        raise ValueError('Each program needs all four physically settled queries')
    result = {'status': 'completed_M2_natural_conditioned_value_probe', 'measured': measured, 'comparison': summary,
              'executor_calls': len(physical), 'executor_tokens': sum(json.loads(r)['usage']['total_tokens'] for _, r in physical),
              'new_native_requests': 0, 'new_teacher_requests': 0, 'formal_updates_changed': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', result)
    write_status(out, {'status': result['status'], 'executor_calls': len(physical), 'comparison': summary}, POINTER)
    print(json.dumps(read(POINTER), sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
