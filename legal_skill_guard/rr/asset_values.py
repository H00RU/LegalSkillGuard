"""Shared exact-span asset/value frontend, not a learned discrimination skill."""
from decimal import Decimal

from .payment_scope import MONEY
from .semantic_frames import obj, occurrences
from .source_discrimination import sentence_spans

PAIR_SCHEMA = obj({name: {'type': 'string'} for name in ('asset_span', 'amount_span', 'evidence_span')})
ASSET_VALUE_SCHEMA = obj({'bindings': {'type': 'array', 'items': PAIR_SCHEMA}})


def decode_asset_values(value, text):
    if type(value) is not dict or set(value) != {'bindings'} or type(value['bindings']) is not list:
        raise ValueError('Wrong asset/value envelope')
    result = []; seen = set()
    units = list(sentence_spans(text))
    for row in value['bindings']:
        if type(row) is not dict or set(row) != set(PAIR_SCHEMA['properties']):
            raise ValueError('Wrong asset/value fields')
        evidence = occurrences(text, row['evidence_span'])
        asset = occurrences(text, row['asset_span']); amount = occurrences(text, row['amount_span'])
        if not MONEY.fullmatch(row['amount_span']):
            raise ValueError('Value must point to an exact dollar literal')
        positions = [(a, m) for a in asset for m in amount if any(
            start <= min(a[0], m[0]) and max(a[1], m[1]) <= end for start, end in evidence)]
        if not positions:
            raise ValueError('Asset and amount must occur together in their stated evidence')
        if any(max(a[0], m[0]) < min(a[1], m[1]) for a, m in positions):
            raise ValueError('An amount pointer is not itself an asset description')
        key = (row['asset_span'], row['amount_span'])
        if key in seen:
            raise ValueError('A repeated binding is not an additional asset')
        seen.add(key)
        controls = []
        for a in asset:
            containing = [(start, end) for start, end in units if start <= a[0] < a[1] <= end]
            for start, end in containing:
                prices = [x.group() for x in MONEY.finditer(text[start:end])]
                controls.append({'asset_position': a, 'unit': [start, end], 'dollar_spans_in_unit': prices,
                    'single_price_matches': prices[0] == row['amount_span'] if len(prices) == 1 else None})
        decisions = [r['single_price_matches'] for r in controls]
        ordinary = decisions[0] if decisions and all(v == decisions[0] for v in decisions) else None
        result.append({'values': row, 'evidence_positions': evidence, 'admissible_position_pairs': positions,
                       'amount_decimal': str(Decimal(row['amount_span'][1:].replace(',', ''))),
                       'single_price_source_unit_control': ordinary, 'source_unit_details': controls})
    return {'bindings': result, 'relation_truth_proved_by_membership': False,
            'completeness_verified': False, 'native_EC_EV_answer': None}
