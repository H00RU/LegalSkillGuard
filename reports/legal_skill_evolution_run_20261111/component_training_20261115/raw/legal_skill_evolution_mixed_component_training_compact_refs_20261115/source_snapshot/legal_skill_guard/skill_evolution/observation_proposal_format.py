"""Recover two observed transport defects without completing a learned rule.

Keep paid proposals immutable. A complete schema object followed by the single
extra closing brace found in B5 has a unique first JSON value. A coverage record
for an ID with no resulting component cannot participate in execution. Recover
only these cases, with explicit receipts; all other validation remains strict.
"""
from copy import deepcopy
import json

import jsonschema

from .objects import digest


def recover_format(base, proposal):
    result = deepcopy(proposal)
    receipts = []
    for index, component in enumerate(result['component_edits']):
        original = component['schema_json']
        try:
            json.loads(original)
        except json.JSONDecodeError:
            # Do not accept a prefix followed by another value, a comment, a
            # partial rule, or arbitrary text. The actual B5 defect is one }.
            value, end = json.JSONDecoder().raw_decode(original)
            if not isinstance(value, dict) or original[end:] != '}':
                raise ValueError('Schema is not the observed single-extra-brace defect')
            jsonschema.Draft202012Validator.check_schema(value)
            component['schema_json'] = original[:end]
            receipts.append({'path': ['component_edits', index, 'schema_json'],
                'repair': 'remove_one_unmatched_trailing_closing_brace',
                'original_sha256': digest(original), 'recovered_sha256': digest(original[:end]),
                'complete_first_JSON_value_unchanged': True})
    actual_ids = {c['id'] for c in base['components']} | {c['id'] for c in result['component_edits']}
    retained = []
    for index, coverage in enumerate(result['coverage_updates']):
        if coverage['id'] in actual_ids:
            retained.append(coverage)
        else:
            receipts.append({'path': ['coverage_updates', index],
                'repair': 'discard_coverage_annotation_for_nonexistent_component',
                'original_record': deepcopy(coverage), 'no_component_created': True,
                'no_family_assigned_to_another_component': True})
    result['coverage_updates'] = retained
    return result, receipts
