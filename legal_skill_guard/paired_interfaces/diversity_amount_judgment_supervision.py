"""Keep verified source amounts separate from the derived legal threshold judgment."""

from dataclasses import replace
import hashlib
import inspect

from legal_skill_guard.paired_interfaces.diversity_amount_supervision import _amount_result, controlled_amount_relation
from legal_skill_guard.paired_interfaces.diversity_supervision import derive_claims
from legal_skill_guard.paired_interfaces.shared_semantics import allowed_relation


LITERAL_FIELDS = ('stated_amount', 'unstated_amount')


def _amount_projection(values, law):
    pair = values['compared_pair']
    first, _ = [row['amount'] for row in values['claims']
                if [row['plaintiff'], row['defendant']] == pair]
    return {'stated_amount': first, 'unstated_amount': None, 'exceeds_threshold': _amount_result(values, law)}


def controlled_amount_judgment_relation(source, shared_fields):
    """Compile a legal conclusion with a separate evidence check on its source coordinates.

    The omitted amount stays unobserved even when evaluating a completed
    legal world. Its possible values affect the threshold judgment only.
    """
    group = controlled_amount_relation(source, shared_fields, entailed_anchor=True)
    code = '\n'.join(inspect.getsource(fn) for fn in (_amount_projection, _amount_result, derive_claims))
    theory = replace(group['theory'], reference=_amount_projection,
                     reference_sha256=hashlib.sha256(code.encode()).hexdigest())
    cases = group['cases']
    shared = allowed_relation(theory, cases)
    independent = allowed_relation(theory, cases, mode='independent_completions')
    stated = tuple(group['ordered_stated_amounts'])
    expected = ((False, False, True), (False, True, True), (True, True, True))
    measured = set()
    for signature in shared['signatures'].values():
        if (tuple(row['stated_amount'] for row in signature) != stated
                or any(row['unstated_amount'] is not None for row in signature)):
            raise ValueError('An allowed signature changed a literal amount or stated a missing amount')
        measured.add(tuple(row['exceeds_threshold'] for row in signature))
    if measured != set(expected) or not shared['signatures'].keys() < independent['signatures'].keys():
        raise ValueError('Source evidence and the nontrivial shared legal relation must both hold')
    return {**group, 'theory': theory, 'shared': shared, 'independent': independent,
            'single_interpretation': allowed_relation(theory, cases, mode='single_interpretation'),
            'literal_assertion_fields': LITERAL_FIELDS, 'judgment_field': 'exceeds_threshold'}
