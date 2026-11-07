"""JSON Schema validation with exact early rejection of impossible union arms.

The recursive DSL unions otherwise expand errors for every wrong operator at
every level. Pruning uses only necessary constraints; acceptance is unchanged.
"""
from __future__ import annotations

from jsonschema import Draft202012Validator, ValidationError, validators


def _possible(validator, schema, instance):
    if schema is False:
        return False
    if schema is True:
        return True
    if '$ref' in schema:
        resolved = validator._resolver.lookup(schema['$ref'])
        if not _possible(validator.evolve(schema=resolved.contents, _resolver=resolved.resolver), resolved.contents, instance):
            return False
    if 'type' in schema:
        kinds = schema['type'] if isinstance(schema['type'], list) else [schema['type']]
        if not any(validator.is_type(instance, kind) for kind in kinds):
            return False
    if 'anyOf' in schema and not any(_possible(validator, arm, instance) for arm in schema['anyOf']):
        return False
    if isinstance(instance, dict):
        if not set(schema.get('required', ())) <= instance.keys():
            return False
        for tag in ('op', 'kind', 'type', 'primitive'):
            prop = schema.get('properties', {}).get(tag, {})
            if tag in instance and 'enum' in prop and instance[tag] not in prop['enum']:
                return False
    return True


def _any_of(validator, choices, instance, schema):
    errors = []
    for index, choice in enumerate(choices):
        if not _possible(validator, choice, instance):
            continue
        branch_errors = list(validator.descend(instance, choice, schema_path=index))
        if not branch_errors:
            return
        errors.extend(branch_errors)
    yield ValidationError('No schema union alternative accepts this value', context=errors)


WireValidator = validators.extend(Draft202012Validator, {'anyOf': _any_of})


def validate_wire(value, schema):
    WireValidator(schema).validate(value)
