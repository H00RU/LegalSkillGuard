"""Advertise a fixed grammar to the model without changing candidate semantics.

The server's response_format constrains decoding; it does not insert the schema
into Qwen's messages. This transport correction applies equally to every plan.
"""
from copy import deepcopy
import json

from legal_skill_guard.skill_evolution.objects import digest


def schema_visible_plan(original):
    plan = deepcopy(original)
    parent = plan.pop('version')
    plan['candidate_semantic_version'] = parent
    plan['transport_revision'] = 'explicit_output_schema_in_model_visible_system_v1'
    plan['system'] += (
        '\nThe following JSON Schema specifies the exact output keys, allowed tags and value types. '
        'It is a formatting contract, not evidence about the source. '
        'Use exactly these keys in their displayed order. Return compact JSON without indentation '
        'or repeated formatting whitespace. Use source unit IDs, never invented unit IDs.\n'
        + json.dumps(plan['schema'], ensure_ascii=False, separators=(',', ':')))
    plan['version'] = digest(plan)
    return plan
