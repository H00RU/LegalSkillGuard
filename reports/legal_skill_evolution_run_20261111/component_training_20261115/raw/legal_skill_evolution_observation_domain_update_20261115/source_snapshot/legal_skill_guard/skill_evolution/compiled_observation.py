"""Execute an acquired facts-only observer through its existing observation ABI.

The observer supplies its own factual reading logic. The host supplies no event
rule, fabricated observation, legal premise, native answer or implicit model
retry. All existing schema, conversion and source checks still apply.
"""
from copy import deepcopy
import time

import jsonschema

from .case_observation_contract import validate_adapter
from .objects import digest
from .span_compiler import execute_json


def execute(component, public, schema):
    program = component['observation_program']
    if not isinstance(program, str) or not program.strip():
        raise ValueError('An acquired observer must be a nonempty executable program')
    validate_adapter(program)
    # Deliberately no native query, question, statute, labels or source ID.
    inputs = {'facts': public['facts']}
    started = time.monotonic()
    component_value = execute_json(program, deepcopy(inputs), {}, allow_helpers=True)
    # A component-scoped observer returns its own acquired schema. Only the
    # batch reader's known component key is added by this transport operation.
    jsonschema.validate(component_value, schema['properties'][component['id']])
    value = {component['id']: component_value}
    jsonschema.validate(value, schema)
    return value, {'read_backend': 'learned_source_program',
        'program_sha256': digest(program), 'facts_sha256': digest(inputs),
        'observation_sha256': digest(value), 'elapsed_seconds': time.monotonic()-started,
        'new_physical_requests': 0, 'source_semantics_certified': False,
        'question_or_native_labels_supplied': False}
