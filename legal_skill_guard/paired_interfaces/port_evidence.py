"""Bind a verbatim port quote to its unique offered source-unit occurrence.

Only an evidence pointer changes. Values, codes, semantic statuses, inventory
and unresolved statements are untouched. Ambiguous or nonverbatim quotes stay
unresolved; there is no source-value extraction or label-assisted repair.
"""
from copy import deepcopy
import re


def bind_port_evidence(plan, value, units):
    result, changes = deepcopy(value), []
    by_id = {u['id']: u for u in units}
    def bind(identity, quote, path):
        if identity in by_id and quote and quote in by_id[identity]['text']:
            return identity
        matches = [(u['id'], m.start(), m.end()) for u in units
                   for m in re.finditer(re.escape(quote), u['text'])] if quote else []
        if len(matches) != 1:
            raise ValueError('Port evidence has no unique verbatim occurrence in the offered current source')
        actual, start, end = matches[0]
        changes.append({'path': path, 'original_unit_id': identity, 'bound_unit_id': actual,
                        'source_local_span': [start, end], 'quote': quote})
        return actual
    for field in ('ticket_price', 'cabin_class', 'origin_city', 'destination_city'):
        cell = result[field]
        cell['unit_id'] = bind(cell['unit_id'], cell['quote'], [field, 'unit_id'])
    if plan['name'] == 'columns':
        if len(result['bag_unit_ids']) != len(result['bag_quotes']):
            raise ValueError('Evidence arrays are unaligned; do not truncate')
        for i, quote in enumerate(result['bag_quotes']):
            result['bag_unit_ids'][i] = bind(result['bag_unit_ids'][i], quote, ['bag_unit_ids', i])
    else:
        for i, bag in enumerate(result['bags']):
            bag['unit_id'] = bind(bag['unit_id'], bag['quote'], ['bags', i, 'unit_id'])
    return result, {'bindings': changes, 'values_codes_statuses_and_scope_unchanged': True,
                    'nonverbatim_or_ambiguous_evidence_not_repaired': True,
                    'shared_public_evidence_binding_not_a_learned_method': True}
