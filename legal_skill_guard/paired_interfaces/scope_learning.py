"""Frozen-budget SCOPE adaptation contracts and source-derived variants."""
from copy import deepcopy
import json
import re

import jsonschema

from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.control_learning import proposal_schema
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


def strict_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON literal: ' + value)
    return json.loads(text, object_pairs_hook=pairs, parse_constant=constant)


def revision_schema():
    base = proposal_schema()
    return record_schema({**base['properties'],
        'seed_rationales': {'type': 'array', 'items': record_schema({
            'source': {'type': 'string'}, 'rationale': {'type': 'string'}})},
        'trace_attribution_and_clause_grounded_revisions': {'type': 'string'},
        'regression_contrasts_and_backtracking': {'type': 'string'}})


def adversary_schema():
    return record_schema({'variants': {'type': 'array', 'minItems': 2, 'maxItems': 2,
        'items': record_schema({'slot': {'type': 'string', 'enum': ['local', 'systemic']},
            'target_predicate': {'type': 'string'},
            'edits': {'type': 'array', 'minItems': 1, 'items': record_schema({
                'before': {'type': 'string', 'minLength': 1}, 'after': {'type': 'string'}})},
            'intended_answer_json': {'type': 'string'}, 'policy_justification': {'type': 'string'}})}})


def verification_schema():
    return record_schema({'verdicts': {'type': 'array', 'items': record_schema({
        'slot': {'type': 'string', 'enum': ['local', 'systemic']},
        'well_formed_and_policy_supported': {'type': 'boolean'},
        'answer_json': {'type': 'string'}, 'rationale': {'type': 'string'}})}})


def _substitute(text, before, after, spans=None):
    matches = list(re.finditer(re.escape(before), text))
    if not matches:
        return text, spans, 0
    def translate(point):
        if any(m.start() < point < m.end() for m in matches):
            raise ValueError('An edit crosses a public sentence boundary')
        return point + sum(len(after) - len(before) for m in matches if m.end() <= point)
    updated = [[translate(start), translate(end)] for start, end in spans] if spans is not None else None
    return text.replace(before, after), updated, len(matches)


def make_variant(source, specification, slot):
    """Edit visible task facts/contracts while preserving law, schemas and IDs."""
    if specification['slot'] != slot:
        raise ValueError('Adversary slot differs from its fixed identity')
    result, receipt = deepcopy(source), []
    dataset = source['dataset']
    for index, edit in enumerate(specification['edits']):
        before, after = edit['before'], edit['after']
        if not before or before == after:
            raise ValueError('An adversarial edit must change an explicit literal span')
        changed = []
        for view in result['views']:
            public = view['public']
            if dataset in ('SARA_v2_Binary', 'RuleArena_Airline'):
                field = 'facts'
                public[field], _, count = _substitute(public[field], before, after)
            elif dataset in ('ContractNLI', 'MAUD'):
                field = 'source_text'
                public[field], spans, count = _substitute(public[field], before, after, public.get('sentence_spans'))
                if spans is not None:
                    public['sentence_spans'] = spans
            elif dataset == 'OpenExempt':
                field = 'original_input'
                prefix, separator, tail = public[field].partition('\nFacts:\n')
                facts, suffix_separator, suffix = tail.partition('\n\nOutput contract:')
                if not separator or not suffix_separator:
                    raise ValueError('OpenExempt public fact boundary is not explicit')
                facts, _, count = _substitute(facts, before, after)
                public[field] = prefix + separator + facts + suffix_separator + suffix
            else:
                raise ValueError('Unregistered public variant domain')
            if count:
                changed.append({'native_view': view['id'], 'field': field, 'occurrences': count})
        if not changed:
            raise ValueError('An adversarial literal was absent from the editable public facts/contracts')
        receipt.append({'edit_index': index, 'before': before, 'after': after, 'changed': changed})
    intended = strict_json(specification['intended_answer_json'])
    jsonschema.validate(intended, source_bundle(result)['answer_schema'])
    return {'slot': slot, 'parent_source': source['key'], 'source': result,
            'public_variant_sha256': digest(result), 'intended_answer': intended,
            'policy_justification': specification['policy_justification'],
            'target_predicate': specification['target_predicate'], 'literal_edit_receipt': receipt,
            'new_independent_mother': False, 'reference_graph_or_calibration_truth': False}


def blind_verifier_payload(variants, shared_assets):
    return {'instruction': 'Independently apply the complete supplied public legal policy to every native task. Determine whether each edited task is well formed and sufficiently supported, then give the native answer dict and your rationale. No intended label or generator rationale is supplied. Do not label from an example identity.',
            'shared_legal_assets': shared_assets,
            'variants': [{'slot': v['slot'], 'input': source_bundle(v['source'])} for v in variants],
            'expected_output': 'answer_json encodes the native answer dict keyed by native view id'}


def admit_variants(variants, verification):
    verdicts = verification['verdicts']
    if len({v['slot'] for v in verdicts}) != len(verdicts):
        raise ValueError('Duplicate independent verification slot')
    if {v['slot'] for v in verdicts} != {v['slot'] for v in variants}:
        raise ValueError('Independent verification must address exactly the supplied variants')
    by_slot = {v['slot']: v for v in verdicts}
    results = []
    for variant in variants:
        verdict = by_slot[variant['slot']]
        try:
            answer = strict_json(verdict['answer_json'])
            jsonschema.validate(answer, source_bundle(variant['source'])['answer_schema'])
            agrees = digest(answer) == digest(variant['intended_answer'])
            reason = None
        except (ValueError, TypeError, jsonschema.ValidationError) as exc:
            answer, agrees, reason = None, False, type(exc).__name__ + ': ' + str(exc)
        results.append({**variant, 'independent_verification': verdict,
            'independent_answer': answer, 'label_agreement': agrees, 'verification_error': reason,
            'admitted': verdict['well_formed_and_policy_supported'] and agrees,
            'label_source': 'two separate teacher readings; not independent human annotation'})
    return results
