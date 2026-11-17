"""Synthesize serializable local interfaces and paired finite consumers.

The finite residual construction follows the user's pinned interface prototype.
The added layer builds actual field/relation read grammars, generates decoder
assets, and rejects projections using complete multi-output residuals. Its
certificate covers the declared finite semantic domain, never English parsing.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
from itertools import combinations, product
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
    if feature['operation'] == 'relation':
        return expression_value(feature['expression'], state)
    if feature['operation'] == 'bound_relations':
        rows = []
        for group in feature['groups']:
            rows.append({'keys': [state[k] for k in group['keys']],
                         'relations': encode(group['features'], state)})
        if feature.get('binding') == 'unkeyed':
            return sorted([row['relations'] for row in rows], key=canonical)
        if feature.get('binding') == 'marginals':
            names = sorted({name for row in rows for name in row['relations']})
            return {name: sorted([row['relations'].get(name) for row in rows], key=canonical)
                    for name in names}
        return rows
    raise ValueError('Unsupported local interface operation')


def expression_value(expression, state):
    """Closed, data-only local expressions; an unknown is never a false fact."""
    op = expression['op']
    if op == 'field':
        return state[expression['field']]
    if op == 'constant':
        return expression['value']
    values = [expression_value(arg, state) for arg in expression['args']]
    if any(value is None for value in values):
        return None
    if op in ('add', 'subtract'):
        if any(type(v) not in (int, float) for v in values):
            raise ValueError('Local arithmetic requires known numeric source attributes')
        return sum(values) if op == 'add' else values[0] - values[1]
    if op in ('eq', 'ne', 'lt', 'le', 'gt', 'ge'):
        a, b = values
        return {'eq': lambda: a == b, 'ne': lambda: a != b,
                'lt': lambda: a < b, 'le': lambda: a <= b,
                'gt': lambda: a > b, 'ge': lambda: a >= b}[op]()
    raise ValueError('Unsupported local relation expression: ' + op)


def expression_fields(expression):
    if expression['op'] == 'field':
        return {expression['field']}
    return set().union(*(expression_fields(e) for e in expression.get('args', [])))


def consumer_relations(module):
    """Lift local comparisons/aggregates, rather than any whole-task decision.

    The AST supplies candidate dependencies only. Exhaustive multi-output
    collisions still decide whether a representation is legal for this module.
    No source answer, native score or current weak read enters generation.
    """
    if not module.program_source:
        return []
    tree = ast.parse(dedent(module.program_source))
    functions = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    if not functions or not functions[0].args.args:
        return []
    local = functions[0].args.args[0].arg
    def lift(node):
        if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Name)
                and node.value.id == local and isinstance(node.slice, ast.Constant)
                and node.slice.value in module.fields):
            return {'op': 'field', 'field': node.slice.value}
        if isinstance(node, ast.Constant) and type(node.value) in (str, int, float, bool):
            return {'op': 'constant', 'value': node.value}
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub)):
            args = [lift(node.left), lift(node.right)]
            if all(a is not None for a in args):
                return {'op': 'add' if isinstance(node.op, ast.Add) else 'subtract', 'args': args}
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'sum' and len(node.args) == 1 and not node.keywords
                and isinstance(node.args[0], (ast.List, ast.Tuple))):
            args = [lift(v) for v in node.args[0].elts]
            if args and all(a is not None for a in args):
                return {'op': 'add', 'args': args}
        return None
    operators = {ast.Eq:'eq', ast.NotEq:'ne', ast.Lt:'lt', ast.LtE:'le', ast.Gt:'gt', ast.GtE:'ge'}
    relations = {}
    for node in ast.walk(functions[0]):
        if not isinstance(node, ast.Compare):
            continue
        for left, op, right in zip([node.left, *node.comparators], node.ops, node.comparators):
            a, b = lift(left), lift(right)
            if type(op) not in operators or a is None or b is None:
                continue
            expression = {'op':operators[type(op)], 'args':[a,b]}
            dependencies = sorted(expression_fields(expression))
            if not dependencies or set(dependencies) & RESERVED:
                continue
            # A field-to-constant test is retained as an atomic baseline;
            # multi-field tests, joins and aggregates carry the new operation.
            relations[canonical(expression)] = {'name':'rel_'+digest(expression)[:12],
                'operation':'relation', 'expression':expression,
                'consumer_dependencies':dependencies,
                'semantic_change_kind':'joint_consumer_relation' if len(dependencies)>1 else 'atomic_comparison'}
    return [relations[k] for k in sorted(relations)]


def propose_relational(module, *, max_new, baseline_fields=None):
    """Compose consumer-derived relations with optional keyed local groups.

    Search is finite in the declared grammar. This candidate bound is not a
    research iteration/request cap. Invalid binding projections retain their
    concrete witnesses; only complete equivalence checks produce certificates.
    """
    if type(max_new) is not int or max_new < 1:
        raise ValueError('Declare a positive representation candidate budget')
    if set(module.fields)&{'parties_are_diverse','aic_is_met','final_classification'}:
        raise ValueError('Native annotation/decision fields cannot be relational reader inputs')
    raw = [{'name':f, 'operation':'field', 'field':f} for f in module.fields]
    relations = consumer_relations(module)
    accepted, rejected, seen = [], [], set()
    def consider(features, operation):
        identity = canonical(features)
        if identity in seen or not features:
            return
        seen.add(identity)
        collision = witness(module, features)
        if collision:
            rejected.append({'operation':operation, 'features':features, 'rejected_by':collision,
                             'legal_source_counterexample':witness(module,features,legal_worlds_only=True)})
        else:
            accepted.append(compile_pair(module, features, operation=operation, layout='anchored'))
    # Exhaustive combinations, with proof-based deletion of redundant raw
    # coordinates. Protected statuses remain first-class reader observations.
    for width in range(1, len(relations)+1):
        for selected in combinations(relations, width):
            touched = set().union(*(set(r['consumer_dependencies']) for r in selected))
            features = [f for f in raw if f['field'] not in touched or f['field'] in module.protected_status_fields] + list(selected)
            consider(features, 'consumer_relational_projection')
    groups = module.source_scope.get('entity_groups', [])
    if groups:
        for g in groups:
            if (not g.get('keys') or not set(g['keys']) <= set(module.fields)
                    or not set(g['fields']) <= set(module.fields)):
                raise ValueError('A relation group needs declared local keys and fields')
        # Each row combines actual consumer relations and its source identity.
        # Removing the identities/matching is a checked counterfactual, never
        # silently accepted because the JSON still has the same dimensions.
        bound = []
        for g in groups:
            own = [r for r in relations if set(r['consumer_dependencies']) <= set(g['fields'])]
            if not own:
                own = [f for f in raw if f['field'] in g['fields'] and f['field'] not in g['keys']]
            # Row-local names cannot leak the original slot identity into the
            # deliberately unkeyed/marginal counterfactual representation.
            own = [dict(f,name='relation_'+str(i)) for i,f in enumerate(own)]
            bound.append({'keys':list(g['keys']), 'features':own})
        covered = set().union(*(set(g['fields']) | set(g['keys']) for g in groups))
        rest = [f for f in raw if f['field'] not in covered or f['field'] in module.protected_status_fields]
        for binding in ('keyed', 'unkeyed', 'marginals'):
            consider(rest+[{'name':'bound_local_relations','operation':'bound_relations',
                'groups':bound,'binding':binding}], 'consumer_'+binding+'_binding')
    # Keep a correct raw interface in the diagnostic pool. It is a baseline,
    # never represented as a newly discovered relational contribution.
    baseline = compile_pair(module, raw, operation='correct_fixed_interface', layout='anchored')
    for asset in accepted:
        asset['candidate_origin'] = 'fixed_consumer_AST_and_declared_entity_structure'
        asset['version'] = digest({k:v for k,v in asset.items() if k!='version'})
    accepted.sort(key=lambda a:(sum(len(v) for v in a['domains'].values()),len(a['features']),a['version']))
    return {'candidates':accepted[:max_new], 'baseline':baseline, 'rejected':rejected,
            'consumer_relation_count':len(relations), 'legally_equivalent_candidates':len(accepted),
            'candidate_generation_uses_native_labels_or_model_outputs':False,
            'candidate_order_is_not_real_reader_selection':True}


def encode(features, state):
    return {f['name']: feature_value(f, state) for f in features}


def witness(module, features, *, legal_worlds_only=False):
    if legal_worlds_only:
        for context_index,context in enumerate(module.contexts):
            seen={}
            for state,outcomes in zip(module.states,module.outcomes):
                value=outcomes[context_index]
                if not value['valid']:
                    continue
                code=canonical(encode(features,state));signature=canonical(value)
                if code in seen and seen[code][1]!=signature:
                    old,_,old_value=seen[code]
                    return {'left_local_state':old,'right_local_state':state,'context':context,
                            'left_output':old_value,'right_output':value,'both_worlds_legal':True}
                seen.setdefault(code,(state,signature,value))
        return None
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


def propose(module, *, baseline_fields=None, max_new=2, relational=False):
    if relational:
        return propose_relational(module, max_new=max_new, baseline_fields=baseline_fields)
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
    values = {'type': 'object', 'properties': {name: finite_value_schema(domain)
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
        elif feature['operation'] == 'relation':
            instructions.append(feature['name'] + ': read only this local relation: '
                                + canonical(feature['expression']) + '. Source field meanings: '
                                + canonical({f:meanings.get(f,f) for f in feature['consumer_dependencies']}))
        elif feature['operation'] == 'bound_relations':
            instructions.append(feature['name'] + ': keep each declared source identity coupled to its own local relations: '
                                + canonical(feature['groups']) + '. Do not exchange relations between source identities.')
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


def finite_value_schema(domain):
    """Typed object/array grammar; decoder still enforces the exact finite set."""
    if all(not isinstance(v,(dict,list)) for v in domain):
        return {'enum':domain}
    if all(isinstance(v,dict) for v in domain):
        keys=list(domain[0])
        if any(set(v)!=set(keys) for v in domain):
            raise ValueError('Relational observations require one explicit object contract')
        return {'type':'object','properties':{k:finite_value_schema(list({canonical(v[k]):v[k] for v in domain}.values())) for k in keys},
                'required':keys,'additionalProperties':False}
    if all(isinstance(v,list) for v in domain) and len({len(v) for v in domain})==1:
        size=len(domain[0]); items=[x for v in domain for x in v]
        return {'type':'array','items':finite_value_schema(list({canonical(v):v for v in items}.values())) if items else {},
                'minItems':size,'maxItems':size}
    raise ValueError('Unsupported mixed relational observation domain')


def source_fidelity(module, asset, reading, *, admissible_states, provenance):
    """TRAIN audit gate independent of native scores and candidate predictions.

    Merely being compatible with one unknown completion is insufficient to
    certify an asserted reading. It must follow from every audited completion.
    This gate is not available as a hidden inference oracle on DEV/TEST.
    """
    permitted={'explicit_source','official_task_assumption','independent_source_audit'}
    if not provenance or any(p.get('kind') not in permitted or not p.get('evidence_sha256') for p in provenance):
        raise ValueError('Source fidelity needs independent source/assumption/audit provenance')
    if asset['module_binding']!=module.binding or not admissible_states:
        raise ValueError('The finite source constraint scope must match the consumer module')
    known={canonical(s) for s in module.states}
    if any(canonical(s) not in known for s in admissible_states):
        raise ValueError('A source constraint completion lies outside the declared domain')
    possibilities={canonical(encode(asset['features'],s)) for s in admissible_states}
    value=canonical(reading)
    status='entailed' if possibilities=={value} else 'underdetermined_assertion' if value in possibilities else 'violated'
    return {'status':status,'source_fidelity_verified':status=='entailed',
            'admissible_encodings':len(possibilities),'native_labels_used':False,
            'unknown_completion_not_selected_to_justify_prediction':True,'provenance':provenance}
