"""Finite source-indexed wire for certified relational programs.

Encoding changes the wire only. The decoded relations and evidence go through
the same source-grounding and consumer checks as a quote-based read.
"""

from copy import deepcopy
import json
import re

from legal_skill_guard.paired_interfaces import relational_program, residual
from legal_skill_guard.skill_evolution.objects import digest

UNREAD = 'unread'


def source_spans(text):
    """Index exact line/sentence fragments without preferring any legal phrase."""
    boundaries = [0, *(match.end() for match in re.finditer(r'\n+|(?<=[.;!?])[ \t]+', text)), len(text)]
    spans = {}
    for start, end in zip(boundaries, boundaries[1:]):
        if text[start:end].strip():
            spans[f's{len(spans) + 1}'] = [start, end]
    return spans


def symbol(value):
    if value is None:
        return '?'
    if type(value) is bool:
        return 'true' if value else 'false'
    if type(value) is str and re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*', value):
        return 'str_' + value
    if type(value) is int:
        return str(value)
    raise ValueError('Unsupported finite indexed symbol')


def encoded_relations(asset):
    fields = [feature['name'] for feature in asset['features']]
    values = {}
    for encoded in asset['decoder']:
        reading = json.loads(encoded)
        code = '|'.join(symbol(reading[field]) for field in fields)
        if code in values:
            raise ValueError('Indexed wire collapsed distinct certified values')
        values[code] = reading
    return fields, values


def indexed_unit(program):
    if len(program['units']) != 1:
        raise ValueError('The scalar indexed wire requires one source-local unit')
    return next(iter(program['units'].items()))


def bind(program, source):
    text = source['source_text']
    spans = source_spans(text)
    if not spans:
        raise ValueError('An indexed read requires exact source text')
    _, unit = indexed_unit(program)
    asset = unit['asset']
    if asset['layout'] != 'anchored' or 'source_text' not in asset['source_scope']['source_fields']:
        raise ValueError('The indexed wire requires an anchored text consumer')
    return {'source_text_sha256': digest(text), 'spans': spans}


def reader_schema(program, binding):
    _, unit = indexed_unit(program)
    _, readings = encoded_relations(unit['asset'])
    return {'type': 'string', 'enum': [
        UNREAD, *(f'{anchor}|{reading}' for anchor in binding['spans'] for reading in readings)
    ]}


def instructions(program):
    lines = [
        'Read the named local unit using the indexed excerpts from the exact source.',
        'Return one quoted JSON string.',
        'Use "unread" when the unit is ungrounded. Otherwise use an evidence span ID followed by',
        'the values of the specified fields in order, using | as the only separator.',
        'Use ? for an unknown value. Attach evidence to the definition or action it qualifies.',
        'Do not answer the benchmark question directly.',
    ]
    name, unit = indexed_unit(program)
    asset = unit['asset']
    fields, values = encoded_relations(asset)
    options = zip(*(value.split('|') for value in values))
    lines.append('Local unit: ' + asset['source_scope']['local_unit'])
    lines.append(name + ' value order:')
    lines.extend(f'{field}: {", ".join(dict.fromkeys(allowed))}' for field, allowed in zip(fields, options))
    # Keep the original legal meanings and AST-derived relation instructions.
    lines.extend(residual.reader_prompt(asset, verbalize_relations=True).splitlines()[4:])
    return '\n'.join(lines)


def expand(program, binding, raw, source):
    if binding != bind(program, source):
        raise ValueError('Indexed evidence lost its source, span, or unit binding')
    name, unit = indexed_unit(program)
    if raw == UNREAD:
        return {name: {'status': 'unread', 'observation': None, 'evidence': []}}
    if type(raw) is not str:
        raise ValueError('Indexed evidence requires a single scalar')
    text = source['source_text']
    anchor, _, code = raw.partition('|')
    _, readings = encoded_relations(unit['asset'])
    if anchor not in binding['spans'] or code not in readings:
        raise ValueError('Unknown evidence ID or unreachable relation symbol')
    start, end = binding['spans'][anchor]
    return {name: {
        'status': 'complete',
        'observation': {'source_anchor': name, 'relations': readings[code]},
        'evidence': [{'field': 'source_text', 'quote': text[start:end]}],
    }}


def decode(program, binding, raw, source):
    return relational_program.decode(program, expand(program, binding, raw, source), source)


def reformat(view):
    """Build both matched reader wires from one existing public source view."""
    view = deepcopy(view)
    source = view['relational_public_source']
    text = source['source_text']
    for plan in view['plans']:
        program = plan['relational_program']
        binding = bind(program, source)
        plan['indexed_evidence_binding'] = binding
        plan['schema'] = reader_schema(program, binding)
        plan['system'] = instructions(program)
        plan['reader_template_sha256'] = relational_program.template_version(
            program, system=plan['system'], public_rules=plan['reader_template_sha256'],
            protocol='indexed_source_evidence_scalar_v1')
        plan['name'] += '_indexed'
        plan['version'] = digest({key: value for key, value in plan.items() if key != 'version'})
    view['read_input']['indexed_evidence'] = [
        {'id': anchor, 'text': text[start:end]} for anchor, (start, end) in source_spans(text).items()
    ]
    return view
