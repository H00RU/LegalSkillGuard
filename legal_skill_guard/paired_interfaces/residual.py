"""Synthesize serializable local interfaces and paired finite consumers.

The finite residual construction follows the user's pinned interface prototype.
The added layer builds actual field/relation read grammars, generates decoder
assets, and rejects projections using complete multi-output residuals. Its
certificate covers the declared finite semantic domain, never English parsing.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import product
import json
import re
from textwrap import dedent
from typing import Callable

from legal_skill_guard.skill_evolution.objects import digest

RESERVED = {'answer', 'final_answer', 'label', 'question', 'hypothesis'}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)


@dataclass(frozen=True)
class FiniteModule:
    name: str
    fields: tuple[str, ...]
    states: tuple[dict, ...]
    contexts: tuple[dict, ...]
    outcomes: tuple[tuple[dict, ...], ...]
    protected_status_fields: tuple[str, ...]
    consumer_sha256: str
    source_scope: dict
    program_source: str = ''

    @classmethod
    def build(cls, name: str, domains: dict, contexts: list[dict], consumer: Callable,
              *, consumer_sha256: str, source_scope: dict, protected_status_fields=(),
              valid_domain=lambda u, c: True, program_source=''):
        fields = tuple(domains)
        if not fields or set(fields) & RESERVED:
            raise ValueError('The interface must contain local source attributes, never task answers')
        if not re.fullmatch(r'[0-9a-f]{64}', consumer_sha256):
            raise ValueError('An immutable audited consumer binding is required')
        if not source_scope.get('source_fields') or not source_scope.get('local_unit'):
            raise ValueError('Declare source fields and one bounded local unit')
        if set(source_scope['source_fields']) & RESERVED:
            raise ValueError('Question and answer fields cannot be reader evidence')
        if not set(protected_status_fields) <= set(fields):
            raise ValueError('Protected semantic statuses must be local fields')
        if not contexts or any(not values for values in domains.values()):
            raise ValueError('Declare nonempty complete finite domains')
        states = tuple(dict(zip(fields, values)) for values in product(*domains.values()))
        if len({canonical(c) for c in contexts}) != len(contexts):
            raise ValueError('Context domain contains duplicates')
        if any(set(c) & set(fields) for c in contexts):
            raise ValueError('Local fields and remaining context must be distinct')
        rows = []
        for state in states:
            outcomes = []
            for context in contexts:
                if not valid_domain(dict(state), dict(context)):
                    outcomes.append({'valid': False})
                else:
                    value = consumer(dict(state), dict(context))
                    canonical(value)
                    outcomes.append({'valid': True, 'outputs': value,
                                     'semantic_obligations': {k: state[k] for k in protected_status_fields}})
            rows.append(tuple(outcomes))
        return cls(name, fields, states, tuple(contexts), tuple(rows),
                   tuple(protected_status_fields), consumer_sha256, source_scope, program_source)

    @property
    def binding(self):
        return digest({'name': self.name, 'states': self.states, 'contexts': self.contexts,
                       'outcomes': self.outcomes, 'consumer': self.consumer_sha256,
                       'scope': self.source_scope, 'statuses': self.protected_status_fields})


def feature_value(feature, state):
    if feature['operation'] == 'field':
        return state[feature['field']]
    if feature['operation'] == 'order':
        left, right = (state[k] for k in feature['fields'])
        if left is None or right is None:
            return 'unknown'
        return 'before' if left < right else 'after' if left > right else 'equal'
    if feature['operation'] == 'residual_bucket':
        value = canonical(state[feature['field']])
        for group in feature['groups']:
            if value in {canonical(v) for v in group['members']}:
                return group['code']
        raise ValueError('Value outside the declared residual partition')
    raise ValueError('Unsupported local interface operation')


def encode(features, state):
    return {f['name']: feature_value(f, state) for f in features}


def witness(module, features):
    groups = {}
    for index, state in enumerate(module.states):
        code = canonical(encode(features, state))
        signature = canonical(module.outcomes[index])
        if code in groups:
            previous, residual = groups[code]
            if residual != signature:
                context = next(i for i, (a, b) in enumerate(zip(module.outcomes[previous], module.outcomes[index])) if a != b)
                return {'left_local_state': module.states[previous], 'right_local_state': state,
                        'context': module.contexts[context],
                        'left_output': module.outcomes[previous][context],
                        'right_output': module.outcomes[index][context]}
        else:
            groups[code] = index, signature
    return None


def compile_pair(module, features, *, operation, layout='flat'):
    if layout not in ('flat', 'anchored'):
        raise ValueError('Unsupported reading layout')
    if not features or len({f['name'] for f in features}) != len(features):
        raise ValueError('Reader fields must be nonempty and distinct')
    collision = witness(module, features)
    if collision:
        raise ValueError('Interface deletes a necessary distinction: ' + canonical(collision))
    domains, decoder = {}, {}
    for state, outcomes in zip(module.states, module.outcomes):
        reading = encode(features, state)
        for key, value in reading.items():
            domains.setdefault(key, {})[canonical(value)] = value
        decoder[canonical(reading)] = {canonical(context): value
                                       for context, value in zip(module.contexts, outcomes)}
    asset = {'module': module.name, 'module_binding': module.binding,
             'fixed_consumer_sha256': module.consumer_sha256,
             'source_scope': module.source_scope, 'operation': operation, 'layout': layout,
             'features': features,
             'domains': {key: [values[k] for k in sorted(values)] for key, values in domains.items()},
             'decoder': decoder,
             'certificate': {'kind': 'exhaustive_finite_residual_pair',
                             'states': len(module.states), 'contexts': len(module.contexts),
                             'legal_domain_preserved': True, 'all_outputs_preserved': True,
                             'protected_status_fields': list(module.protected_status_fields),
                             'source_semantics_or_reader_accuracy_certified': False}}
    asset['version'] = digest(asset)
    return asset


def decode(asset, reading, context, *, module_binding):
    if module_binding != asset['module_binding']:
        raise ValueError('The consumer or its declared semantic domain changed')
    expected = {f['name'] for f in asset['features']}
    if set(reading) != expected:
        return {'valid': False, 'unresolved': 'reader field mismatch'}
    row = asset['decoder'].get(canonical(reading), {})
    return row.get(canonical(context), {'valid': False, 'unresolved': 'outside certified semantic domain'})


def comparison_pairs(module):
    """Recover candidate local order relations from the audited consumer AST.

    A syntactic match only proposes a pair. The residual checker still rejects
    deletion when a date also controls duration, another output, or validity.
    """
    if not module.program_source:
        return []
    tree = ast.parse(dedent(module.program_source))
    functions = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if not functions or not functions[0].args.args:
        return []
    local = functions[0].args.args[0].arg
    def field(node):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name) and node.value.id == local:
            if isinstance(node.slice, ast.Constant) and node.slice.value in module.fields:
                return node.slice.value
        return None
    pairs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = field(node.left), field(node.comparators[0])
            if left and right and left != right:
                pairs.add((left, right))
    return sorted(pairs)


def value_partition(module, field):
    """Compute a coordinate's residual across all other local fields/context.

    Membership is derived from the fixed program's complete output vector,
    never a current source's answer. The grammar supplies explicit finite
    member sets; a numeric interval is not silently extended beyond them.
    """
    signatures, values = {}, {}
    others = tuple(k for k in module.fields if k != field)
    for state, outcomes in zip(module.states, module.outcomes):
        key = canonical(state[field])
        values[key] = state[field]
        signatures.setdefault(key, {})[canonical({k: state[k] for k in others})] = outcomes
    classes = {}
    for key in sorted(values):
        signature = canonical(signatures[key])
        classes.setdefault(signature, []).append(values[key])
    return [{'code': field + '_group_' + str(i), 'members': members}
            for i, members in enumerate(classes.values())]


def propose(module, *, baseline_fields=None, max_new=2):
    if not 0 <= max_new <= 2:
        raise ValueError('The fixed pilot permits at most two new candidates per module')
    raw = [{'name': name, 'operation': 'field', 'field': name} for name in module.fields]
    initial = [f for f in raw if baseline_fields is None or f['field'] in baseline_fields]
    candidates, diagnostics = [], []
    collision = witness(module, initial)
    if collision:
        # Add the smallest declared source distinction that removes a collision;
        # there is no answer-derived feature and no test-case feedback here.
        for feature in raw:
            if feature not in initial:
                initial.append(feature)
                if witness(module, initial) is None:
                    break
        for feature in tuple(reversed(initial)):
            smaller = [f for f in initial if f != feature]
            if smaller and witness(module, smaller) is None:
                initial = smaller
        candidates.append(compile_pair(module, initial, operation='necessary_refinement'))
    else:
        for left, right in comparison_pairs(module):
            features = [f for f in raw if f['field'] not in (left, right)]
            features.append({'name': left + '__order__' + right, 'operation': 'order', 'fields': [left, right]})
            bad = witness(module, features)
            if bad:
                diagnostics.append({'operation': 'order_projection', 'fields': [left, right], 'rejected_by': bad})
            else:
                candidates.append(compile_pair(module, features, operation='order_projection'))
                break
        if not candidates:
            possibilities = []
            for field in module.fields:
                groups = value_partition(module, field)
                original_values = len({canonical(s[field]) for s in module.states})
                if 1 < len(groups) < original_values:
                    features = [f for f in initial if f['field'] != field]
                    features.append({'name': field + '__residual_code', 'operation': 'residual_bucket',
                                     'field': field, 'groups': groups})
                    if witness(module, features) is None:
                        possibilities.append((original_values - len(groups), field, features))
            if possibilities:
                _, _, features = max(possibilities, key=lambda x: (x[0], x[1]))
                candidates.append(compile_pair(module, features, operation='residual_value_partition'))
        if not candidates:
            features = list(initial)
            for feature in tuple(features):
                smaller = [f for f in features if f != feature]
                if smaller and witness(module, smaller) is None:
                    features = smaller
            if features != initial:
                candidates.append(compile_pair(module, features, operation='residual_projection'))
    if len(candidates) < max_new:
        # The anchor identifies a source unit, not a target question or label.
        features = candidates[0]['features'] if candidates else initial
        candidates.append(compile_pair(module, features, operation='binding_reification', layout='anchored'))
    return {'candidates': candidates[:max_new], 'rejected': diagnostics,
            'candidate_generation_uses_native_labels_or_model_outputs': False}


def reader_schema(asset):
    values = {'type': 'object', 'properties': {name: {'enum': domain}
                                             for name, domain in asset['domains'].items()},
              'required': list(asset['domains']), 'additionalProperties': False}
    observation = {'type': 'object', 'properties': {
        'source_anchor': {'type': 'string', 'minLength': 1}, 'relations': values},
        'required': ['source_anchor', 'relations'], 'additionalProperties': False}
    fields = {'status': {'type': 'string', 'enum': ['complete', 'unread']},
              'evidence': {'type': 'array', 'items': {'type': 'object', 'properties': {
                  'field': {'type': 'string', 'enum': asset['source_scope']['source_fields']},
                  'quote': {'type': 'string', 'minLength': 1}},
                  'required': ['field', 'quote'], 'additionalProperties': False}}}
    if asset['layout'] == 'anchored':
        fields['observation'] = {'anyOf': [observation, {'type': 'null'}]}
    else:
        fields['source_anchor'] = {'type': 'string', 'minLength': 1}
        fields['values'] = {'anyOf': [values, {'type': 'null'}]}
    return {'type': 'object', 'properties': fields, 'required': list(fields), 'additionalProperties': False}


def reader_prompt(asset):
    """Realize only source-local features; never ask for consumer decisions."""
    instructions = [
        'Read the identified local source unit and return the supplied JSON schema.',
        'Local unit: ' + asset['source_scope']['local_unit'] + '.',
        'Preserve the supplied source anchor and cite contiguous evidence from the permitted source fields.',
        'Use unread with a null observation when a required attribute is unstated or ambiguous.',
    ]
    meanings = asset['source_scope'].get('field_meanings', {})
    for feature in asset['features']:
        if feature['operation'] == 'field':
            meaning = meanings.get(feature['field'], feature['field'])
            instructions.append(feature['name'] + ': ' + meaning + '.')
        elif feature['operation'] == 'order':
            left, right = feature['fields']
            instructions.append(feature['name'] + ': compare ' + meanings.get(left, left) + ' with '
                                + meanings.get(right, right) + ' on this same source anchor; return before/equal/after/unknown.')
        elif feature['operation'] == 'residual_bucket':
            instructions.append(feature['name'] + ': read ' + meanings.get(feature['field'], feature['field'])
                                + ' and encode its source-stated value using these exact finite groups:')
            for group in feature['groups']:
                members = group['members']
                if (all(type(v) is int for v in members)
                        and len(members) == max(members) - min(members) + 1):
                    description = f'integers {min(members)} through {max(members)}, inclusive'
                else:
                    description = canonical(members)
                instructions.append(group['code'] + ' = ' + description + '.')
    return '\n'.join(instructions)


def validate_read(asset, reading, public_source):
    import jsonschema
    jsonschema.validate(reading, reader_schema(asset))
    values = (reading['observation']['relations'] if reading.get('observation') is not None
              else None) if asset['layout'] == 'anchored' else reading['values']
    if reading['status'] == 'unread':
        if values is not None:
            raise ValueError('Unread is not a populated or negative observation')
        return {'supported': False, 'reason': 'unread'}
    if values is None or not reading['evidence']:
        raise ValueError('A complete local observation requires values and source evidence')
    for item in reading['evidence']:
        if item['quote'] not in public_source[item['field']]:
            raise ValueError('Evidence must be a contiguous source span')
    return {'supported': True, 'values': values,
            'source_fidelity_verified': False, 'evidence_contiguity_checked': True}
