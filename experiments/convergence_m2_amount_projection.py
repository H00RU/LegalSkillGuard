"""Recover an independently verifiable amount lower bound from a typed model read."""

import argparse
import json
import re
import sqlite3

import jsonschema

from experiments.convergence_m2_amount_update import POINTER as BOOLEAN
from experiments.convergence_pilot_b0 import BASE, HANDOFF, LEDGER, ROOT, read, sha, write_status
from legal_skill_guard.paired_interfaces.diversity_amount_supervision import controlled_amount_relation
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


POINTER = HANDOFF / 'm2_amount_projection_current.json'
SCHEMA = record_schema({'first_amount': {'type': ['integer', 'null'], 'minimum': 0},
                        'second_amount': {'type': ['integer', 'null'], 'minimum': 0}, 'quote': {'type': 'string'}})
SYSTEM = ('Read the two dollar amounts in the marked joint claim clause, in order. Report the exact '
          'number of dollars, with no rounding. Use null for an unstated dollar amount. Copy the entire '
          'marked clause verbatim as quote. Do not calculate or answer any threshold question.')


def verified_projection(physical, clause):
    """Accept a lower bound only if the measured coordinate matches its literal evidence."""
    if physical['finish_reason'] != 'stop':
        raise ValueError('The reader response did not stop cleanly')
    output = json.loads(physical['content'])
    jsonschema.validate(output, SCHEMA)
    if output['quote'].strip() != clause.strip():
        raise ValueError('The measured evidence must be the exact marked clause')
    amounts = [int(value.replace(',', '')) for value in re.findall(r'\$([0-9][\d,]*)', clause)]
    if len(amounts) != 1 or 'an unspecified dollar amount' not in clause:
        raise ValueError('This audited intervention must contain one stated and one hidden amount')
    if output['first_amount'] != amounts[0] or output['second_amount'] is not None:
        raise ValueError('A literal amount was changed or a missing amount invented')
    # A nonnegative missing value cannot reduce the known part of the total.
    return True if output['first_amount'] > 75000 else None


def _cases(orig, binding):
    source, = (row for row in read(orig / 'sources.json') if row['key'] == binding['group_mother'])
    group = controlled_amount_relation(source, binding['group_fields'], entailed_anchor=True)
    rows = []
    for case, receipt in zip(group['cases'], group['edit_receipts'], strict=True):
        field, start, _, _ = receipt['patched_spans'][0]
        text = case.public[field]
        clause, = (m[0].strip() for m in re.finditer(r'[^.]+\.', text) if m.start() <= start < m.end())
        rows.append({'case': case.source_id, 'source_text_sha256': digest(text), 'marked_clause': clause})
    return source, group, rows


def prepare():
    orig = ROOT / read(BOOLEAN)['artifact_root']
    old, terminal = read(orig / 'binding.json'), read(orig / 'terminal.json')
    old_rows = [row for program in terminal['measurements'].values() for row in program['projected']]
    if (terminal['status'] != 'completed' or len(old_rows) != 9
            or any(row['projection'] is not None or row['decode_error'] is not None for row in old_rows)):
        raise ValueError('This distinct reader is justified by the observed abstention even on the entailed anchor')
    source, group, rows = _cases(orig, old)
    files = set(old['source_sha256']) | {'experiments/convergence_m2_amount_projection.py'}
    binding = {'study': 'M2_numeric_lower_bound_actual_reader', 'executor': old['executor'],
               'source_sha256': {path: sha(ROOT / path) for path in sorted(files)},
               'prior_amount_root': str(orig.relative_to(ROOT)), 'prior_terminal_sha256': sha(orig / 'terminal.json'),
               'projected_cases_sha256': digest(rows), 'mother': source['key'], 'expected_anchor_projection': True,
               'controlled_missingness': True, 'physical_logical_cells': len(group['cases'])}
    out = BASE / 'm2_amount_projection' / digest(binding)
    immutable_json(out / 'binding.json', binding)
    immutable_json(out / 'cases.json', rows)
    if not (out / 'terminal.json').exists():
        write_status(out, {'status': 'prepared', 'executor_cells': len(rows)}, POINTER)
    print(json.dumps(read(POINTER)), flush=True)


def run():
    out = ROOT / read(POINTER)['artifact_root']
    if (out / 'terminal.json').exists():
        print(json.dumps(read(out / 'terminal.json')), flush=True)
        return
    binding = read(out / 'binding.json')
    prior = ROOT / binding['prior_amount_root']
    source, group, cases = _cases(prior, read(prior / 'binding.json'))
    if (out.name != digest(binding) or sha(prior / 'terminal.json') != binding['prior_terminal_sha256']
            or cases != read(out / 'cases.json') or digest(cases) != binding['projected_cases_sha256']
            or any(sha(ROOT / path) != expected for path, expected in binding['source_sha256'].items())):
        raise ValueError('The precise rendered source and comparison observations changed')
    with sqlite3.connect(LEDGER.as_uri() + '?mode=ro', uri=True) as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise ValueError('Settle the previous physical request first')
    ledger = EvolutionLedger(LEDGER, run_id='convergence-amount-projection-' + out.name[:16],
                             sources={'train': [source['key']], 'dev': [], 'test': []}, binding=binding)
    reader = FrozenExecutor(ledger, out, binding['executor'])
    reader.readiness()
    write_status(out, {'status': 'running', 'executor_cells': len(cases)}, POINTER)
    results = []
    for case, expected in zip(group['cases'], cases, strict=True):
        payload = {'source_text': case.public['source_text'], 'marked_clause': expected['marked_clause']}
        messages = [{'role': 'system', 'content': SYSTEM},
                    {'role': 'user', 'content': json.dumps(payload, sort_keys=True, ensure_ascii=False)}]
        identity = ledger.run_id + ':' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=source['key'], purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        physical = raw.get('reused_physical_call_id', identity)
        verify_physical_response(reader, identity=physical, source=source['key'], purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            result = verified_projection(raw, expected['marked_clause'])
            error = None
        except (ValueError, jsonschema.ValidationError) as exc:
            result, error = None, str(exc)
        row = {'physical_call_id': physical, 'projection': result, 'production_error': error,
               'executor_tokens': raw['usage']['total_tokens']}
        immutable_json(out / 'projection_reads' / (digest(case.source_id) + '.json'), row)
        results.append(row)
    outputs = [row['projection'] for row in results]
    terminal = {'status': 'completed', 'outputs': outputs, 'production_errors': [row['production_error'] for row in results],
                'all_compatible_with_shared_relation': any(matches_assertions(outputs, expected)
                                                           for expected in group['shared']['signatures'].values()),
                'entailed_anchor_read_correctly': outputs[-1] is True, 'physical_call_ids': [row['physical_call_id'] for row in results],
                'executor_tokens': sum(row['executor_tokens'] for row in results),
                'native_update_effect_measured': False, 'TEST_opened': False}
    immutable_json(out / 'terminal.json', terminal)
    write_status(out, terminal, POINTER)
    print(json.dumps(terminal, sort_keys=True), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=('prepare', 'run'))
    (prepare if parser.parse_args().phase == 'prepare' else run)()
