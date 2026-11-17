"""Parse canonical numeric strings at declared numeric consumer ports only.

The graph schema permits a string value. A string such as "51" is a valid
numeric serialization, not an absent measurement. No value is taken from a
quote, label, other item, or default, and unknown statuses remain unknown.
"""
from copy import deepcopy
from decimal import Decimal
import math
import re


NUMERIC_PORTS = {'length', 'width', 'height', 'weight', 'amount', 'ticket_price', 'quantity'}
CANONICAL_NUMBER = re.compile(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?\Z')


def number(value):
    if not isinstance(value, str) or not CANONICAL_NUMBER.fullmatch(value):
        return value
    decimal = Decimal(value)
    if decimal == decimal.to_integral():
        return int(decimal)
    converted = float(value)
    if math.isfinite(converted) and Decimal(str(converted)) == decimal:
        return converted
    return value


def port_number(predicate, value):
    """Accept an explicit unit only at the matching declared measurement port."""
    converted = number(value)
    if not isinstance(converted, str):
        return converted
    units = {'weight': r'(?:lb|lbs|pound|pounds)',
             'length': r'(?:in|inch|inches)', 'width': r'(?:in|inch|inches)',
             'height': r'(?:in|inch|inches)'}
    if predicate in units:
        match = re.fullmatch(r'(-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?)\s+' + units[predicate], value)
        if match:
            return number(match[1])
    if predicate in ('amount', 'ticket_price') and re.fullmatch(r'\$(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?', value):
        return number(value[1:].replace(',', ''))
    return value


def normalize_numeric_ports(graph):
    result, changes = deepcopy(graph), []
    for i, edge in enumerate(result['relations']):
        if edge['predicate'] not in NUMERIC_PORTS or edge['status'] != 'stated':
            continue
        before = edge['value']
        after = port_number(edge['predicate'], before)
        if type(before) is str and type(after) in (int, float):
            edge['value'] = after
            changes.append({'relation_index': i, 'predicate': edge['predicate'],
                'arguments': edge['arguments'], 'before': before, 'after': after})
    return result, {'changes': changes, 'field_statuses_and_source_anchors_unchanged': True,
                    'no_missing_value_inferred': True, 'no_weight_value_mapped_to_a_residual_code': True}
