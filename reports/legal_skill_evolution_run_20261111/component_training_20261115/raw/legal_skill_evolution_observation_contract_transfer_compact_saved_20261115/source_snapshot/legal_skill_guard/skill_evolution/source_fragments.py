"""Bind selected current-source spans to literal text, without legal inference."""
from copy import deepcopy


def fragment_field(specification):
    representation = specification.get('representation')
    if representation is None:return False
    if representation != 'source_spans' or specification.get('type') != 'array':
        raise ValueError('Source-fragment fields must be explicit arrays with representation source_spans')
    return True


def bind_fragment_value(ids, spans):
    if (not isinstance(ids, list) or not ids
            or any(type(i) is not int or i < 0 or i >= len(spans) for i in ids)):
        raise ValueError('A known fragment selection needs valid current-source span IDs')
    ordered = sorted(set(ids))  # The interface selects a set; text keeps source order.
    support = [deepcopy(spans[i]) for i in ordered]
    return [s['text'] for s in support], support, {
        'wire_support_ids': deepcopy(ids), 'source_order_ids': ordered,
        'binding': 'exact current-source span text; no semantic value inferred'}
