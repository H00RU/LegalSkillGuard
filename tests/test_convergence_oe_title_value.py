import json

from experiments.convergence_oe_natural_relation import build_natural_group
from legal_skill_guard.paired_interfaces.convergence_oe_title_value import (
    LITERAL_FIELDS, compile_title_value, decode_observation, selections,
)
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.paired_interfaces.shared_semantics_validation import unsupported_literal_assertions


def _group():
    text = 'A debtor possesses a bicycle appraised at $900.00. A cart also costs $900.00.'
    literal = '$900.00'
    start = text.index(literal)
    source = {'key': 'OpenExempt:fixture', 'views': [{'id': 'EC', 'public': {'original_input': text}}]}
    group = build_natural_group(source, 'a' * 64, 'bicycle', (start, start + len(literal)), 900)
    return compile_title_value(group)


def _observation(quote, amount, contribution, title=None):
    return {'finish_reason': 'stop', 'content': json.dumps({'quote': quote, 'ownership': title,
            'stated_value': amount, 'title_filtered_value': contribution})}


def _choices(group, rows):
    outputs = [row['value'] for row in rows]
    shared = tuple(group['shared']['signatures'].values())
    independent = tuple(group['independent']['signatures'].values())
    check = {'unsupported_literal_assertions': unsupported_literal_assertions(outputs, shared, LITERAL_FIELDS),
             'independent_per_case_compatible': any(matches_assertions(outputs, sig) for sig in independent),
             'single_witness_compatible': matches_assertions(outputs, shared[0]),
             'shared_prefix_compatible': any(matches_assertions(outputs, sig) for sig in shared)}
    return selections(group, rows, True, {'matched_controls': [check]})


def test_title_value_uses_one_ownership_assignment_without_asserting_literal_title():
    group = _group()
    old, edited = group['cases']
    first, first_anchored = decode_observation(
        _observation('bicycle appraised at $900.00', 900, 0), old, group['anchors'][0])
    second, second_anchored = decode_observation(
        _observation('bicycle appraised at $1000.00', 1000, 1000), edited, group['anchors'][1])
    evidence = [{'value': first, 'anchored': first_anchored}, {'value': second, 'anchored': second_anchored}]
    contrast = _choices(group, evidence)
    assert contrast['literal_evidence_complete']
    assert contrast['isolated_shared_rejection']
    assert contrast['shared_compatible_signature_count'] == 0


def test_title_value_separates_unresolved_judgment_and_literal_amount_binding():
    group = _group()
    old, edited = group['cases']
    missing, anchored = decode_observation(
        _observation('bicycle appraised at $900.00', 900, None), old, group['anchors'][0])
    assert anchored and missing['stated_value'] == 900
    assert missing['title_filtered_value'] is None
    _, wrong_asset = decode_observation(_observation('cart also costs $900.00', 900, None), old, group['anchors'][0])
    assert not wrong_asset
    _, wrong_span = decode_observation(
        _observation('bicycle appraised at $900.00. A cart also costs $900.00', 900, None), old, group['anchors'][0])
    assert not wrong_span
    new, new_anchored = decode_observation(
        _observation('bicycle appraised at $1000.00', 1000, None), edited, group['anchors'][1])
    comparison = _choices(group, [{'value': missing, 'anchored': anchored}, {'value': new, 'anchored': new_anchored}])
    assert comparison['literal_evidence_complete'] and not comparison['derived_observation_present']
    assert comparison['shared_compatible_signature_count'] == 2
    assert not comparison['candidate_selected_by']['shared_explanation']
