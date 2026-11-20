"""Consumer-preserving interfaces for the ContractNLI retention hypothesis."""

from functools import lru_cache
from inspect import getsource
import json

import jsonschema

from legal_skill_guard.paired_interfaces import residual
from legal_skill_guard.skill_evolution.native import record_schema
from legal_skill_guard.skill_evolution.objects import digest


TASK = 'nda-20'
ENTAILMENT, CONTRADICTION, ABSENT = 'Entailment', 'Contradiction', 'NotMentioned'
MEANINGS = {
    'retention_grant': 'operative permission for the recipient to keep some protected information, including an express exemption from disposal',
    'grant_governs_retained_information': 'the permission governs the same information after the applicable return or destruction, for at least one recipient or form',
    'disposition_bar': 'an operative prohibition on retaining copies or a requirement to dispose of all information and all copies',
    'bar_covers_retention_scope': 'the bar governs the same receiving party and protected information at disposal, covering the proposition rather than only a separately specified class of records',
    'scope_checked': 'checked the complete contract for pertinent retention and disposition language, following exceptions outside the disposal paragraph',
}
RELATIONS = {
    'post_disposition_retention_grant': tuple(MEANINGS)[:2],
    'post_disposition_retention_bar': tuple(MEANINGS)[2:4],
}
COMMON = (
    'Determine whether the receiving party may retain some confidential information even after return or destruction. '
    'Bind a legal act to its own receiving party, information object, and governing event. A possibility of '
    'permission to make a reproduction while performing the agreement is not permission to keep it after '
    'disposition. A separate survival duty does not give permission to retain copies. A requirement to '
    'return or destroy all the information and all copies can rule out retention when no operative '
    'exception applies. Verify that a ban reaches the protected information of the hypothesis and not '
    'just one separately identified subset. A legal, archival, backup, legal-custody, or other explicit '
    'exception can permit some covered copies to be kept even if a different clause generally requires '
    'disposition. Check separate numbered clauses, cross-references, and different triggers, including '
    'request and ending the agreement or the covered relationship. If a condition, party, or information '
    'object is unresolved, do not guess. For a supported signed conclusion cite the shortest complete '
    'chain of original span IDs, including a prohibition or mandatory disposition, or the exception, and '
    'any lead-in or governing act that gives the wording its effect. Cite nothing for checked absence or '
    'unresolved scope. Return only the specified JSON.'
)


def consume(values, _context):
    if values['retention_grant'] == True and values['grant_governs_retained_information'] == True:
        return {'classification': ENTAILMENT}
    if values['retention_grant'] == False or values['grant_governs_retained_information'] == False:
        if values['scope_checked'] == True:
            if values['disposition_bar'] == True and values['bar_covers_retention_scope'] == True:
                return {'classification': CONTRADICTION}
            if values['disposition_bar'] == False or values['bar_covers_retention_scope'] == False:
                return {'classification': ABSENT}
    return {'classification': None}


@lru_cache(maxsize=1)
def layouts():
    procedure = getsource(consume)
    module = residual.FiniteModule.build(
        'post_disposition_retention', dict.fromkeys(MEANINGS, [True, False, None]), [{}], consume,
        consumer_sha256=digest(procedure), program_source=procedure,
        protected_status_fields=('scope_checked',),
        source_scope={'source_fields': ['source_text'],
                      'local_unit': 'permission or prohibition after disposal of the same protected information',
                      'field_meanings': MEANINGS},
    )
    fixed = [{'name': name, 'operation': 'field', 'field': name} for name in MEANINGS]
    expressions = residual.consumer_relations(module)
    synthesized = []
    for name, dependencies in RELATIONS.items():
        # Lift the conjunction's field dependencies from the actual consumer,
        # then retain false and unresolved values as distinct source states.
        lifted, = (r for r in expressions if r['expression']['op'] == 'and'
                   and set(r['consumer_dependencies']) == set(dependencies))
        synthesized.append({**lifted, 'name': name, 'expression': {
            'op': 'and', 'args': [{'op': 'field', 'field': dep} for dep in dependencies],
        }})
    synthesized.append(fixed[-1])
    assets = {
        'fixed': residual.compile_pair(module, fixed, operation='fixed_coordinates', layout='anchored'),
        'synthesized': residual.compile_pair(module, synthesized, operation='consumer_relational_projection',
                                              layout='anchored'),
    }
    for asset in assets.values():
        for state, outputs in zip(module.states, module.outcomes, strict=True):
            encoded = residual.encode(asset['features'], state)
            if residual.decode(asset, encoded, {}, module_binding=module.binding) != outputs[0]:
                raise ValueError('Projection must preserve the native classification and checked-scope state')
    return module, assets


def request(payload, role):
    shared_fields = '\n'.join(f'{name}. {meaning}.' for name, meaning in MEANINGS.items())
    if role == 'direct':
        fields = {'answer': {'enum': [ENTAILMENT, CONTRADICTION, ABSENT, None]}}
        instruction = (
            'Return Entailment for established post-disposal retention permission. Once the whole '
            'agreement is checked and a relevant permission is ruled out, return Contradiction for a '
            'bound, comprehensive retention bar, or NotMentioned when that bar is also ruled out. '
            'Use null when the relevant source effect remains unresolved.'
        )
    else:
        domains = layouts()[1][role]['domains']
        fields = {'observations': record_schema({name: {'enum': domain} for name, domain in domains.items()})}
        tri_state = 'Use true for verified, false for ruled out, and null for unresolved.'
        if role == 'fixed':
            instruction = 'Record each source field separately. ' + tri_state
        else:
            definitions = '\n'.join(f'{name}. The same provision satisfies both {left} and {right}.'
                                    for name, (left, right) in RELATIONS.items())
            instruction = (
                'Record the two binding relations and scope_checked. For each relation use true if both '
                'conditions hold together, false if at least one was ruled out, and null otherwise. '
                f'For scope_checked, {tri_state.lower()}\n{definitions}'
            )
    schema = record_schema({**fields, 'evidence': {
        'type': 'array', 'maxItems': 12,
        'items': {'type': 'integer', 'minimum': 0, 'maximum': len(payload['indexed_spans']) - 1},
    }})
    return [
        {'role': 'system', 'content': f'{COMMON}\n{shared_fields}\n{instruction}'},
        {'role': 'user', 'content': json.dumps(payload, ensure_ascii=False)},
    ], schema


def decode(payload, role, schema, response):
    if response['finish_reason'] != 'stop':
        return {'answer': None, 'evidence': []}, response['finish_reason']
    try:
        value = json.loads(response['content'])
        jsonschema.validate(value, schema)
        evidence = sorted(value['evidence'])
        if len(evidence) != len(set(evidence)) or any(
                not payload['indexed_spans'][index]['text'].strip() for index in evidence):
            raise ValueError('Evidence must point to a nonempty source span')
        if role == 'direct':
            answer = value['answer']
        else:
            module, assets = layouts()
            result = residual.decode(assets[role], value['observations'], {}, module_binding=module.binding)
            if not result['valid']:
                raise ValueError('Uncertified observation')
            answer = result['outputs']['classification']
        if answer in (ENTAILMENT, CONTRADICTION) and not evidence:
            raise ValueError('Signed source assertion needs an original citation')
        return {'answer': answer, 'evidence': evidence if answer in (ENTAILMENT, CONTRADICTION) else []}, None
    except (ValueError, jsonschema.ValidationError):
        return {'answer': None, 'evidence': []}, 'invalid_wire'
