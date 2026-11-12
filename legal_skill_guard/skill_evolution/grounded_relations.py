"""Select current-source occurrences of already acquired role vocabulary.

This shared codec cannot assign legal effect, recipient ownership or scope.
It only maps a uniquely learned lexical occurrence ID back to its concept.
"""
from copy import deepcopy
import re

import jsonschema

from .relational_compiler import bind_records, read_schema, spans_for


def role_mentions(source, spec, lexicons):
    spans = spans_for(source)
    text = source['views'][0]['public']['source_text']
    allowed = {c for f in spec['frames'] for field in f['fields']
        if field['type'] == 'array' for c in field['domain']}
    hits = set()
    for lexicon in lexicons:
        for entry in lexicon['entries']:
            if entry['symbol'] not in allowed:
                continue
            for form in entry['forms']:
                if not form.strip():
                    raise ValueError('Empty acquired lexical form')
                for match in re.finditer(r'(?<!\w)' + re.escape(form) + r'(?!\w)', text, re.I):
                    hits.add((match.start(), match.end(), entry['symbol']))
    ambiguous = {a for a in hits for b in hits
        if a[0] < b[1] and b[0] < a[1] and a[2] != b[2]}
    exact = sorted(a for a in hits if a not in ambiguous and not any(
        b[2] == a[2] and b[0] <= a[0] and a[1] <= b[1] and b != a for b in hits))
    mentions = []
    for start, end, symbol in exact:
        support = [s['id'] for s in spans if s['start'] < end and start < s['end']]
        if not support:
            raise ValueError('A lexical occurrence lacks public source coverage')
        mentions.append({'id': len(mentions), 'concept': symbol, 'quote': text[start:end],
            'start': start, 'end': end, 'source_span_ids': support})
    return spans, mentions, [{'start': a, 'end': b, 'concept': c} for a, b, c in sorted(ambiguous)]


def pointer_schema(spec, spans, mentions):
    schema = read_schema(spec, spans)
    for frame in spec['frames']:
        fields = schema['properties'][frame['name']]['items']['properties']['fields']['properties']
        for field in frame['fields']:
            if field['type'] != 'array':
                continue
            ids = [m['id'] for m in mentions if m['concept'] in field['domain']]
            fields[field['name']]['properties']['value'] = {
                'type': ['array', 'null'], 'maxItems': len(ids), 'uniqueItems': True,
                'items': ({'type': 'integer', 'enum': ids} if ids else {'type': 'integer'})}
    return schema


def bind_pointers(spec, spans, mentions, returned):
    jsonschema.validate(returned, pointer_schema(spec, spans, mentions))
    converted = deepcopy(returned)
    for frame in spec['frames']:
        for instance in converted[frame['name']]:
            for field in frame['fields']:
                value = instance['fields'][field['name']]
                if field['type'] != 'array' or value['value'] is None:
                    continue
                selected = [mentions[i] for i in value['value']]
                for mention in selected:
                    if not set(mention['source_span_ids']) <= set(value['support_ids']):
                        raise ValueError('Selected role occurrence lies outside field evidence')
                value['value'] = sorted({m['concept'] for m in selected})
    records = bind_records(spec, spans, converted)
    return records


def read_grounded_relations(reads, source, spec, lexicons):
    spans, mentions, ambiguous = role_mentions(source, spec, lexicons)
    returned, event = reads.generate(source, source['views'][0],
        system='Read instances of the acquired semantic relation frames from the CURRENT legal source. '
            'For ARRAY-valued fields select IDs of actual current-source lexical occurrences listed in current_role_mentions, '
            'rather than generating concept names. These occurrences are possible lexical meanings only, not legal facts or permissions. '
            'Select a role only if that occurrence belongs to the operative action and participant scope of this instance; '
            'roles in information descriptions, another owner, unrelated acts or nested qualifications are not direct recipients. '
            'A selected occurrence must lie in the field supporting source spans. Keep direct recipients separate from qualified access. '
            'If a role cannot be expressed with the acquired lexical occurrences, or its scope is unresolved, use null rather than '
            'an empty or partial exhaustive set. [] means a genuinely established empty set. STRING-valued fields retain their '
            'acquired semantic meanings and canonical concept values. Every known field needs current supporting span IDs. '
            'Use [] for a relation with no supported instance; do not infer a legal negative from extraction absence. '
            'Do not return native hypothesis answers or copy old source facts.',
        content={'acquired_relation_frames': spec['frames'], 'current_role_mentions': mentions,
            'current_source_spans': [{k: v for k, v in s.items() if k != 'public_sentence_id'} for s in spans]},
        schema=pointer_schema(spec, spans, mentions), purpose='skill_replay')
    records = bind_pointers(spec, spans, mentions, returned)
    return records, {**event, 'kind': 'READ_GROUNDED_RELATION_OCCURRENCES', 'returned': returned,
        'current_role_mentions': mentions, 'ambiguous_lexical_occurrences_excluded': ambiguous,
        'semantic_relation_and_ownership_verified': False,
        'conversion': 'Only selected unambiguous acquired lexical IDs map to concepts; no missing role forms or legal semantics inserted.'}
