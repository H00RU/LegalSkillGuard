"""Recover a structurally finished JSON response after a whitespace-only cutoff."""

import json


def _unique_object(pairs):
    keys = dict(pairs)
    if len(keys) != len(pairs):
        raise ValueError('A sealed response cannot contain duplicate JSON object keys')
    return keys


def _pending_objects(value):
    stack = []
    string = escaped = False
    for char in value:
        if string:
            if escaped:
                escaped = False
            elif char == '\\':
                escaped = True
            elif char == '"':
                string = False
        elif char == '"':
            string = True
        elif char in '{[':
            stack.append(char)
        elif char in '}]':
            if not stack or (stack.pop(), char) not in (('{', '}'), ('[', ']')):
                raise ValueError('A response has mismatched JSON delimiters')
    if string or '[' in stack:
        raise ValueError('A partial literal or array may still add answer content')
    return len(stack)


def recover_json(text, schema, *, finish_reason):
    """Decode a response and retain evidence of any unambiguous object closure.

    A premature stop inside whitespace can only insert closing braces on the
    rightmost path. Each such object must already have every permitted key.
    The existing production decoder remains responsible for answer validation.
    """
    if finish_reason == 'stop':
        return json.loads(text), None
    if finish_reason != 'length':
        raise ValueError('A nonstandard termination cannot recover a response')
    prefix = text.rstrip(' \t\r\n')
    if len(prefix) == len(text):
        raise ValueError('The response was not cut off inside JSON whitespace')
    closures = _pending_objects(prefix)
    result = json.loads(prefix + '}' * closures, object_pairs_hook=_unique_object)
    value, spec = result, schema
    for _ in range(closures):
        properties = spec.get('properties', {})
        if (spec.get('type') != 'object' or spec.get('additionalProperties') is not False
                or not isinstance(value, dict) or not value
                or set(properties) != set(spec.get('required', ())) or set(value) != set(properties)):
            raise ValueError('A truncated open object must contain every permitted schema key')
        last = next(reversed(value))
        value, spec = value[last], properties[last]
    return result, {'finish_reason': finish_reason, 'trailing_whitespace_chars': len(text) - len(prefix),
                    'object_closures': closures, 'model_values_changed': False}
