"""Concrete local READ value shapes, including explicit arrays of records."""
from .native import record_schema

PRIMITIVES = ('boolean', 'integer', 'number', 'string', 'array')
ARRAY_ATOM = {'type': ['string', 'number', 'boolean', 'null']}


def value_schema(field, *, nullable=False):
    kind = field['type']
    if kind not in PRIMITIVES:
        raise ValueError('Local reads use explicit primitive, array, or record-array fields')
    schema = {'type': [kind, 'null'] if nullable else kind}
    if 'item_fields' in field:
        items = field['item_fields']
        if kind != 'array' or not isinstance(items, list) or not items:
            raise ValueError('Record-array READ requires nonempty explicit item fields')
        properties = {}
        for item in items:
            if (set(item) != {'name', 'type', 'question'} or not isinstance(item['name'], str)
                    or not item['name'] or item['name'] in properties
                    or not isinstance(item['question'], str) or not item['question']):
                raise ValueError('Record fields need distinct names, primitive types and questions')
            properties[item['name']] = value_schema({'type': item['type']})
        schema['items'] = record_schema(properties)
    elif kind == 'array':
        schema['items'] = dict(ARRAY_ATOM)
    return schema
