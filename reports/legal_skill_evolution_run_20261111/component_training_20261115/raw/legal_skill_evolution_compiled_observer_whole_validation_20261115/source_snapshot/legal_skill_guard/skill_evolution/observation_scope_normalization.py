"""Normalize equivalent residence parse annotations without changing facts.

The current learned family readers sometimes describe the same witnessed
residence twice, or choose an incompatible linguistic form for that same place.
Only finite categorical parsing fields may change. Every source/world field
must remain identical, and every admissible successful framing must produce
the same facts under the original acquired converter. No native label is read.
"""
from copy import deepcopy
from itertools import product
import json

import jsonschema

from .literal_statutory_givens import constrain
from .objects import digest
from .observation_component_library import component_value


WORLD_FIELDS = {'persons', 'location', 'start_date', 'start_text', 'end_date',
                'end_text', 'witnesses', 'source_term'}


def _domains(schema, fields):
    result = {name: [] for name in fields}
    def visit(node):
        if not isinstance(node, dict):
            return
        for name, rule in node.get('properties', {}).items():
            if name in result and isinstance(rule, dict):
                choices = [rule['const']] if 'const' in rule else rule.get('enum', [])
                for value in choices:
                    if value not in result[name]:
                        result[name].append(value)
        for key in ('allOf', 'anyOf', 'oneOf'):
            for child in node.get(key, []):
                visit(child)
    visit(schema)
    return {key: values for key, values in result.items() if values}


def normalize(library, kernel, public, observation):
    value, receipts = deepcopy(observation), []
    cid = 'family_relationship_residence'
    if cid not in value:
        return value, receipts
    component = next(c for c in library['components'] if c['id'] == cid)
    schema = json.loads(component['schema_json'])
    record_schema = schema['properties']['views']['items']['properties']['residences']['items']
    projected = constrain(record_schema, public, kernel)
    for index, view in enumerate(value[cid]['views']):
        records = view.get('residences')
        if view.get('extraction_status') != 'complete' or not isinstance(records, list) or not records:
            continue
        finite = _domains(projected, set(records[0]) - WORLD_FIELDS)
        if not finite:
            continue
        style = set(finite)
        # A single source claim may have several categorical descriptions.
        # Distinct places, persons, dates or witnesses are never coalesced.
        worlds = [{k: deepcopy(v) for k, v in record.items() if k not in style} for record in records]
        if any(w != worlds[0] for w in worlds[1:]):
            continue
        before = component_value(library, component, kernel, public, view)
        if len(records) == 1 and before['complete']:
            continue
        candidates = []
        keys = sorted(finite)
        for values in product(*(finite[k] for k in keys)):
            record = deepcopy(records[0])
            record.update(dict(zip(keys, values)))
            if not jsonschema.Draft202012Validator(projected).is_valid(record):
                continue
            trial = deepcopy(view)
            trial['residences'] = [record]
            if not jsonschema.Draft202012Validator(schema).is_valid({'views': [trial]}):
                continue
            part = component_value(library, component, kernel, public, trial)
            if part['complete']:
                facts = {'facts': sorted(part['facts'], key=digest),
                         'negative_givens': sorted(part['negative_givens'], key=digest)}
                candidates.append((record, digest(facts), part))
        fact_sets = {fingerprint for _, fingerprint, _ in candidates}
        if len(fact_sets) != 1:
            continue
        record, fingerprint, part = min(candidates, key=lambda r: json.dumps(r[0], sort_keys=True))
        assert {k: v for k, v in record.items() if k not in style} == worlds[0]
        value[cid]['views'][index]['residences'] = [record]
        receipts.append({'component': cid, 'view': index, 'original_records': deepcopy(records),
            'normalized_record': deepcopy(record), 'world_and_source_fields_unchanged': True,
            'original_equivalent_record_count': len(records), 'valid_parse_framings': len(candidates),
            'all_successful_framings_same_fact_set': fingerprint,
            'original_converter_passed_without_modified_checks': part['complete'],
            'no_missing_field_or_fact_added': True, 'native_answer_used': False})
    return value, receipts
