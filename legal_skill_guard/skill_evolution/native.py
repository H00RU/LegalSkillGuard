"""Public answer codecs and original native grades, separate from learning."""
from copy import deepcopy
import json
import re
from functools import lru_cache
from pathlib import Path
import subprocess

import jsonschema

from legal_skill_guard.rr.source_structure import CITATION
from legal_skill_guard.rr.scoring import task_score


@lru_cache(maxsize=2048)
def official_grade(family, answer_json, target_json):
    result = subprocess.run(['/home/yndx/hhy/legal-skill-current/.venv/bin/python', '-m',
        'legal_skill_guard.skill_evolution.grade_worker'], cwd=Path(__file__).resolve().parents[2],
        input=json.dumps({'family': family, 'answer': json.loads(answer_json),
                          'target': json.loads(target_json)}, ensure_ascii=False),
        capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError('Pinned official grader failed: ' + result.stderr[-2000:])
    return json.loads(result.stdout)


def record_schema(fields):
    return {'type': 'object', 'properties': fields, 'required': list(fields),
            'additionalProperties': False}


def restore_enum_transport(value, schema):
    """Undo only an exact UTF-8-as-Latin-1 enum spelling seen on this backend.

    Values without a unique match in the supplied schema are untouched and
    must still pass the original validator. No labels, laws or amounts enter.
    """
    changes = []

    def visit(item, node, path):
        choices = node.get('enum', [])
        if isinstance(item, str) and choices and item not in choices:
            matched = [s for s in choices if isinstance(s, str) and
                       s.encode('utf-8').decode('latin-1') == item]
            if len(matched) == 1:
                changes.append({'path': list(path), 'raw': item, 'restored': matched[0],
                                'basis': 'unique exact public-schema UTF8-byte match'})
                return matched[0]
        if isinstance(item, dict):
            return {k: visit(v, node.get('properties', {}).get(k, {}), path + (k,))
                    for k, v in item.items()}
        if isinstance(item, list):
            return [visit(v, node.get('items', {}), path + (i,)) for i, v in enumerate(item)]
        return item

    return visit(value, schema, ()), changes


def answer_wire_schema(dataset, view):
    answer = deepcopy(view['answer_schema'])
    if dataset == 'OpenExempt':
        # Encode arbitrary asset keys as records. This is a lossless output
        # codec, not an asset/eligibility oracle or full-document IR.
        citations = sorted(set(CITATION.findall(view['public']['original_input'])))
        citation = {'type': 'string', 'enum': citations}
        claim = citation if view['id'] == 'EC' else record_schema({
            'citation': citation, 'claim_value': {'type': 'number', 'minimum': 0}})
        facts = view['public']['original_input'].split('\nFacts:\n', 1)[-1].split('\nOutput contract:', 1)[0]
        public_value_mentions = len(re.findall(r'\$\s*[0-9]', facts))
        if not public_value_mentions:
            raise ValueError('Public OE facts lack the expected asset-value statements')
        answer = {'type': 'array', 'maxItems': public_value_mentions, 'items': record_schema({
            'asset': {'type': 'string'}, 'claims': {'type': 'array', 'maxItems': len(citations), 'items': claim}})}
    count = len(view['public']['sentence_spans']) if dataset == 'ContractNLI' else 0
    evidence = {'type': 'array', 'maxItems': count,
                'items': {'type': 'integer', 'minimum': 0}}
    if count:evidence['items']['maximum'] = count - 1
    return record_schema({'answer': answer, 'evidence_sentence_ids': evidence})


def decode_answer(dataset, view, value):
    jsonschema.validate(value, answer_wire_schema(dataset, view))
    answer = value['answer']
    if dataset == 'OpenExempt':
        result = {}
        for row in answer:
            if row['asset'] in result:
                raise ValueError('Duplicate asset output; no last-write repair')
            result[row['asset']] = row['claims']
        answer = result
    jsonschema.validate(answer, view['answer_schema'])
    return answer, value['evidence_sentence_ids']


def grade_view(dataset, view, annotation, answer, evidence=()):
    try:
        jsonschema.validate(answer, view['answer_schema'])
        valid = True
    except jsonschema.ValidationError:
        valid = False
    target = annotation['answer']
    if dataset == 'OpenExempt':
        result = task_score(dataset, answer, target, family=view['id'])
        result['official_metrics'] = official_grade(view['id'], json.dumps(answer, sort_keys=True),
                                                   json.dumps(target, sort_keys=True))
        native = result['official_metrics']
        result['grade'] = (float(native['metrics']['f1']) if native['status'] == 'scored'
                           else 0.0 if native['status'] == 'native_format_rejection' else None)
    else:
        result = {'valid': valid, 'correct': valid and type(answer) is type(target) and answer == target,
                  'metric': 'native_exact_match'}
        result['grade'] = float(result['correct'])
    if dataset == 'ContractNLI' and annotation.get('evidence') is not None:
        expected, found = set(annotation['evidence']), set(evidence)
        result['evidence_f1'] = (2 * len(expected & found) / (len(expected) + len(found))
                                  if expected or found else 1.0)
    return result


def public_strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in public_strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in public_strings(v)]
    return []


def public_task(source, view):
    return {'dataset': source['dataset'], 'view_id': view['id'],
            'public': deepcopy(view['public'])}


def source_spans(public):
    """Use supplied sentence boundaries, otherwise exact public paragraphs.

    Public segmentation supplies positions, never evidence labels. Nonempty
    gaps are retained so segmentation cannot silently delete source material.
    """
    result = []
    for field, value in public.items():
        if field == 'sentence_spans':
            continue
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if field == 'source_text' and 'sentence_spans' in public:
            cursor = 0
            for index, pair in enumerate(public['sentence_spans']):
                if (not isinstance(pair, (list, tuple)) or len(pair) != 2
                        or any(type(x) is not int for x in pair)):
                    raise ValueError('Public sentence boundaries need integer start/end pairs')
                start, end = pair
                if not cursor <= start < end <= len(text):
                    raise ValueError('Public sentence boundaries overlap or leave the source range')
                for a, b, sentence in ((cursor, start, None), (start, end, index)):
                    if text[a:b].strip():
                        result.append({'id': len(result), 'field': field, 'start': a,
                            'end': b, 'text': text[a:b],
                            **({'public_sentence_id': sentence} if sentence is not None else {})})
                cursor = end
            if text[cursor:].strip():
                result.append({'id': len(result), 'field': field, 'start': cursor,
                    'end': len(text), 'text': text[cursor:]})
            continue
        for match in re.finditer(r'\S.*?(?=\n\s*\n|\Z)', text, re.S):
            result.append({'id': len(result), 'field': field, 'start': match.start(),
                           'end': match.end(), 'text': match.group(0)})
    if not result:
        raise ValueError('Current public source has no readable spans')
    return result


DIRECT_SYSTEM = (
    'Answer the supplied native legal/rule task using only its public source and facts. '
    'Return the requested JSON, without an explanation. Use the exact native labels. '
    'For ContractNLI include supporting sentence indices; use [] where no evidence is available. '
    'For OpenExempt the supplied answer schema supersedes the legacy output-contract sentence: '
    'emit records for the actual assets, use full public citation strings, never invented label IDs. '
    'Do not omit assets with no exemption; give them an empty claims array. '
    'List each actual asset once and each applicable citation once. Stop after the JSON object. '
    'Do not translate the source into a program or repeat the source text.')
