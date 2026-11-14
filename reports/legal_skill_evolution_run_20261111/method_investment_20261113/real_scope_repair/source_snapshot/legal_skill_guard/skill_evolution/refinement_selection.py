"""Diagnose which factual interface can make a partial proof decisive.

Counterfactual assignments are probes, never case facts or training labels.
An eligible refinement also needs a separately evidenced input refutation.
"""
from .callable_rules import evaluate


def boolean_pivots(library, planned, case_values, *, unknown_only=False):
    if not planned['supported']:
        return []
    initial=evaluate(library,planned,case_values)
    if initial['value'] is not None:
        return []
    unit=library['units'][planned['unit']]
    candidates=[]
    for field in unit['fields']:
        name=field['name']
        if field['type']!='boolean' or (unknown_only and name in case_values):
            continue
        for value in (False,True):
            if name in case_values and case_values[name] is value:
                continue
            hypothetical={**case_values,name:value}
            outcome=evaluate(library,planned,hypothetical)
            if outcome['value'] is not None:
                candidates.append({'field':name,'was_known':name in case_values,
                    'original_value':case_values.get(name),'counterfactual_value':value,
                    'computed_property_if_supported':outcome['value'],
                    'used_units':outcome['used_units'],
                    'hypothetical_not_a_corrected_case_value':True})
    return candidates


def evidenced_refinement_candidates(pivots,refutations):
    """Keep only pivots with independent current-case evidence for that value.

This does not certify source semantics of an arbitrary supplied refutation;
its provenance and producer must be reviewed separately. No values are fed
back into real execution by selecting a repair target.
"""
    selected=[]
    for pivot in pivots:
        witness=refutations.get(pivot['field'])
        if not witness or type(witness['value']) is not bool or not witness.get('evidence'):
            continue
        if witness['value'] is pivot['counterfactual_value']:
            selected.append({**pivot,'refutation':witness,'action':'learn_or_repair_the_field_producer'})
    return selected
