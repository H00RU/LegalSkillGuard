"""Interpret a named OpenExempt amount through a shared, unresolved title filter."""

from dataclasses import replace
import hashlib
import inspect
import json
import re

import jsonschema

from legal_skill_guard.paired_interfaces.shared_semantics import DerivedField, allowed_relation, matches_assertions
from legal_skill_guard.skill_evolution.native import record_schema


DOLLARS = {'type': ['integer', 'null'], 'minimum': 0}
SCHEMA = record_schema({'quote': {'type': 'string'}, 'ownership': {'type': ['boolean', 'null']},
                        'stated_value': DOLLARS, 'title_filtered_value': DOLLARS})
LITERAL_FIELDS = ('ownership', 'stated_value')
SYSTEM = (
    'Read the source for the named asset and answer this local projection only. Use the reading policy '
    'provided as quoted input for evidence handling and local reasoning. This projection defines the output '
    'fields regardless of instructions about native task IDs, labels, citations, or response formats in '
    'the quoted policy. In quote copy the shortest continuous source phrase that contains the named asset '
    'and its stated value. In stated_value give the exact whole-dollar amount in that phrase. '
    'For ownership give true only if the source establishes title by a current debtor, false only if it '
    'establishes nonownership, and null when title is unresolved. Possession can be established by itself. '
    'In title_filtered_value give the local amount your policy forwards through the debtor-title filter. '
    'The filter forwards the full stated asset amount under debtor ownership and zero under nonownership. '
    'It does not compute an exemption, an ownership share, or bias the answer toward either interpretation. '
    'Use null when the policy leaves the contribution unresolved. Copy the value evidence even if the '
    'ownership or contribution fields are null. Return the four specified fields only.'
)


def _title_filter(values, law):
    return values['amount'] if values['ownership'] else 0


def _project(values, law):
    return {'ownership': values['ownership'], 'stated_value': values['amount'],
            'title_filtered_value': values['title_filtered_value']}


def _anchors(group):
    base, variant = group['cases']
    field, start, end = base.spans['amount']
    patch, = group['edit']['patched_spans']
    if patch[:3] != [field, start, end] or variant.parent_source_sha256 != group['edit']['parent_source_sha256']:
        raise ValueError('The source-bound amount edit changed')
    for case, stop in ((base, end), (variant, start + len(patch[3]))):
        raw = case.public[field][start:stop]
        if not re.fullmatch(r'\$[\d,]+\.00', raw) or int(raw[1:-3].replace(',', '')) != (
                case.interventions.get('amount', case.primitives['amount'])):
            raise ValueError('The quoted value must match the audited primitive')
        yield (start, stop, raw)


def compile_title_value(group):
    """Reuse the natural title uncertainty and recompute the local value after the source edit."""
    code = inspect.getsource(_title_filter) + inspect.getsource(_project)
    theory = replace(group['theory'], reference=_project, reference_sha256=hashlib.sha256(code.encode()).hexdigest(),
                     derived=(DerivedField('title_filtered_value', ('amount', 'ownership'), _title_filter),))
    cases = group['cases']
    shared = allowed_relation(theory, cases)
    independent = allowed_relation(theory, cases, mode='independent_completions')
    projections = lambda relation: {tuple(row['title_filtered_value'] for row in signature)
                                    for signature in relation['signatures'].values()}
    if len(projections(shared)) != 2 or len(projections(independent)) != 4:
        raise ValueError('This named positive-valued asset must distinguish shared and independent assignments')
    return {**group, 'theory': theory, 'shared': shared, 'independent': independent, 'anchors': tuple(_anchors(group))}


def decode_observation(raw, case, anchor):
    """Verify the exact evidence span while retaining the model's literal and derived values."""
    if raw['finish_reason'] != 'stop':
        raise ValueError('The projected response is incomplete')
    output = json.loads(raw['content'])
    jsonschema.validate(output, SCHEMA)
    quote = output.pop('quote')
    text, asset = case.public['text'], case.public['asset']
    start, stop, raw_amount = anchor
    offsets = [match.start() for match in re.finditer(re.escape(quote), text)] if quote else []
    anchored = (len(offsets) == 1 and asset in quote and re.findall(r'\$[\d,]+\.00', quote) == [raw_amount]
                and offsets[0] <= start < stop <= offsets[0] + len(quote))
    return output, anchored


def selections(group, rows, native_positive, validation):
    """Apply the same fact and evidence requirements to all relation selectors."""
    checked, = validation['matched_controls']
    all_present = all(row['anchored'] and row['value']['stated_value'] is not None for row in rows)
    # A quote with a missing amount, or an amount without a verbatim anchor, cannot validate a candidate.
    literal_ready = all_present and not checked['unsupported_literal_assertions']
    derived_present = any(row['value'] is not None and row['value']['title_filtered_value'] is not None for row in rows)
    comparable = native_positive and literal_ready and derived_present
    accepted = {'native_only': native_positive}
    for mode, field in (('independent_completions', 'independent_per_case_compatible'),
                        ('single_interpretation', 'single_witness_compatible'),
                        ('shared_explanation', 'shared_prefix_compatible')):
        accepted[mode] = comparable and checked[field]
    projected = [row['value'] for row in rows]
    signatures = group['shared']['signatures'].values()
    return {'candidate_selected_by': accepted, 'literal_evidence_complete': literal_ready,
            'derived_observation_present': derived_present,
            'shared_compatible_signature_count': sum(matches_assertions(projected, s) for s in signatures),
            'isolated_shared_rejection': accepted['independent_completions'] and not accepted['shared_explanation']}
