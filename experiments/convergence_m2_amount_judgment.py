"""Read a candidate's amount judgment while independently verifying literal support."""

from collections import defaultdict
import json
import re

import jsonschema

from legal_skill_guard.paired_interfaces.diversity_amount_judgment_supervision import (
    controlled_amount_judgment_relation,
)
from legal_skill_guard.paired_interfaces.diversity_supervision import build
from legal_skill_guard.paired_interfaces.formal_actors import verify_physical_response
from legal_skill_guard.paired_interfaces.shared_semantics_validation import validate_patch
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


DATASET = 'LegalBench_Diversity'
AMOUNT = {'type': ['integer', 'null'], 'minimum': 0}
SCHEMA = record_schema({'stated_amount': AMOUNT, 'unstated_amount': AMOUNT,
                        'exceeds_threshold': {'type': ['boolean', 'null']}, 'quote': {'type': 'string'}})
SYSTEM = (
    'Read the marked joint claim clause for the specified plaintiff and defendant. Copy the clause verbatim. '
    'Report the stated amount in dollars and leave an unstated amount null. Then separately give the legal '
    'judgment whether the sum of exactly these two claims strictly exceeds 75000 dollars. Claim amounts '
    'are nonnegative. Use null if the comparison cannot be resolved. A known amount alone can prove the '
    'comparison when it already exceeds the threshold. Return the specified fields only. '
    'The stated_amount field is the full exact dollar value from the clause, even if reusable guidance '
    'below describes a different wire unit, clipping scheme, or output format. Use that guidance only '
    'for binding the named parties and deriving the judgment.\n'
)


def first_visible_group(sources):
    """Choose the first structurally eligible mother and clause in TRAIN order."""
    for source in sources:
        if source['dataset'] != DATASET:
            continue
        case, _, _ = build(source)
        by_pair = defaultdict(list)
        for entry in case.primitives['claim_bindings']:
            by_pair[entry['plaintiff'], entry['defendant']].append(entry['amount_field'])
        pairs_by_fields = defaultdict(list)
        for pair, fields in by_pair.items():
            if len(fields) == 2:
                pairs_by_fields[tuple(fields)].append(pair)
        eligible = [fields for fields, pairs in pairs_by_fields.items() if len(pairs) > 1]
        if eligible:
            return controlled_amount_judgment_relation(source, min(eligible))
    return None


def group_binding(group):
    if group is None:
        return None
    return digest({'cases': [(case.source_id, case.public) for case in group['cases']],
                   'reference': group['theory'].reference_sha256,
                   'literal_fields': group['literal_assertion_fields'],
                   'shared': group['shared']['signatures'], 'independent': group['independent']['signatures'],
                   'transport': {'system': SYSTEM, 'schema': SCHEMA}})


def _marked_clause(case, edit):
    field, start, _, _ = edit['patched_spans'][0]
    text = case.public[field]
    clause, = (match[0].strip() for match in re.finditer(r'[^.]+\.', text) if match.start() <= start < match.end())
    return clause


def _decode(response, clause):
    if response['finish_reason'] != 'stop':
        raise ValueError('The structured reading did not finish')
    output = json.loads(response['content'])
    jsonschema.validate(output, SCHEMA)
    if output.pop('quote').strip() != clause.strip():
        raise ValueError('The reading lacks the exact marked source clause')
    amounts = re.findall(r'\$([0-9][\d,]*)', clause)
    if len(amounts) != 1 or 'an unspecified dollar amount' not in clause:
        raise ValueError('The bound source has an invalid stated or masked amount')
    if output['stated_amount'] is None:
        raise ValueError('The alleged source reading omitted the visible amount')
    for field in ('stated_amount', 'unstated_amount'):
        if output[field] is not None:
            output[field] = int(output[field])
    return output


def measure(reader, out, program, group):
    """Obtain real projected observations from the frozen reader under candidate guidance."""
    rows = []
    plaintiff, defendant = min(group['covered_pairs'])
    guidance = '\n'.join(predicate['prompt'] for predicate in program['predicates'])
    for case, edit in zip(group['cases'], group['edit_receipts'], strict=True):
        clause = _marked_clause(case, edit)
        messages = [{'role': 'system', 'content': SYSTEM + guidance}, {'role': 'user', 'content': json.dumps(
            {**case.public, 'marked_clause': clause, 'plaintiff': plaintiff, 'defendant': defendant},
            sort_keys=True, ensure_ascii=False)}]
        identity = reader.ledger.run_id + ':amount-judgment:' + digest([case.source_id, messages, SCHEMA])
        raw = reader.generate(identity, source=case.root_id, purpose='skill_actor', messages=messages,
                              schema=SCHEMA, thinking=False)
        physical = raw.get('reused_physical_call_id', identity)
        verify_physical_response(reader, identity=physical, source=case.root_id, purpose='skill_actor',
                                 content_sha256=digest(raw['content']), usage=raw['usage'], finish_reason=raw['finish_reason'])
        try:
            value, failure = _decode(raw, clause), None
        except (ValueError, jsonschema.ValidationError) as exc:
            value, failure = None, type(exc).__name__
        row = {'case': case.source_id, 'case_sha256': digest(case.public), 'physical_call_id': physical,
               'value': value, 'production_failure': failure, 'executor_tokens': raw['usage']['total_tokens']}
        immutable_json(out / 'amount_judgment_reads' / (digest(identity) + '.json'), row)
        rows.append(row)
    return rows


def _judgment_gate(group, rows):
    if any(row['production_failure'] is not None for row in rows):
        return 'invalid_evidence_read'
    signatures = tuple(group['shared']['signatures'].values())
    field = group['judgment_field']
    for i, row in enumerate(rows):
        possible = {signature[i][field] for signature in signatures}
        if len(possible) == 1 and row['value'][field] is not next(iter(possible)):
            return 'missed_entailed_judgment'
    return 'passed'


def validate_update(program, group, rows, native_pairs, visible_keys):
    """Keep native utility and the entailed anchor common to all local selectors."""
    version = digest(program)
    cases = group['cases']
    observed = {row['case']: row for row in rows}
    if len(rows) != len(cases) or set(observed) != {case.source_id for case in cases}:
        raise ValueError('A quantitative update requires exactly the bound projected cohort')
    result = validate_patch(group['theory'], version, [{
        'cases': cases, 'outputs': [observed[case.source_id]['value'] for case in cases],
        'physical_call_ids': [observed[case.source_id]['physical_call_id'] for case in cases],
        'literal_assertion_fields': group['literal_assertion_fields'],
    }], native_pairs, visible_train=visible_keys,
        verify_projection=lambda patch, physical, case, value: patch == version and any(
            row['case'] == case.source_id and row['case_sha256'] == digest(case.public)
            and row['physical_call_id'] == physical and row['value'] == value for row in rows),
        verify_native_pair=lambda patch, row: patch == version and row in native_pairs)
    gate = _judgment_gate(group, [observed[case.source_id] for case in cases])
    match, = result['matched_controls']
    native_positive = result['native_utility_sum_delta'] > 0
    eligible = gate == 'passed' and native_positive and not match['unsupported_literal_assertions']
    result['candidate_selected_by'] = {'native_only': native_positive, **{
        name: eligible and match[field] for name, field in (
            ('independent_completions', 'independent_per_case_compatible'),
            ('single_interpretation', 'single_witness_compatible'),
            ('shared_explanation', 'shared_prefix_compatible'),
        )}}
    result['judgment_gate'] = gate
    if result['status'] == 'eligible_train_update' and gate != 'passed':
        result['status'] = 'rejected_' + gate
    if result['candidate_selected_by']['shared_explanation'] != (result['status'] == 'eligible_train_update'):
        raise ValueError('The shared selection must agree with the anchored update decision')
    return result
