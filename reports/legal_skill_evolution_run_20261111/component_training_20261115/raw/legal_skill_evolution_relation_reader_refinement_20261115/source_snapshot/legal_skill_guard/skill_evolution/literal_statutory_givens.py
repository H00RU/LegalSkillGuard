"""Project the existing exact-citation premise contract into case schemas.

This restricts source-stated statutory givens, not derived applicability or
general event observations. Missing literal support never establishes a legal
negative. Null/unread channels retain their original meanings.
"""
from copy import deepcopy
import re

from .sara_statute_kernel import GIVENS
from .observation_status_schema import _refine


CITATIONS = {
    's151_b': '151(b)', 's151_b_applies': '151(b)',
    's151_c_applies': '151(c)', 's152_c_1': '152(c)(1)',
    's63_f_1_A': '63(f)(1)(A)', 's63_f_1_B': '63(f)(1)(B)',
}
assert set(CITATIONS) == set(GIVENS)


def _object_disjunction(node):
    """Distribute common object fields into actual acquired oneOf refinements.

    B AND exactly-one(C_i) equals exactly-one(B AND C_i). The observed
    refinements contain property constraints, with no competing closure rule.
    This preserves required fields which xgrammar otherwise ignores in siblings.
    """
    base = {key: deepcopy(value) for key, value in node.items() if key != 'oneOf'}
    branches = []
    for clause in node['oneOf']:
        if clause is False:
            continue
        if not isinstance(clause, dict) or set(clause) - {'properties', 'required'}:
            raise ValueError('Unsupported acquired object-discriminator refinement')
        branch = deepcopy(base)
        branch['required'] = list(dict.fromkeys(branch.get('required', []) + clause.get('required', [])))
        for name, rule in clause.get('properties', {}).items():
            if name not in branch['properties'] or not isinstance(rule, dict):
                raise ValueError('A discriminator refines a declared property')
            if set(rule) - {'type', 'minItems', 'maxItems', 'minLength', 'maxLength', 'enum', 'const', 'x-source-facts-token'}:
                raise ValueError('Unsupported acquired discriminator property constraint')
            old = branch['properties'][name]
            refined = _refine(old, {k: v for k, v in rule.items()
                if k in ('type', 'minItems', 'maxItems', 'minLength', 'maxLength')})
            if refined is not False:
                choices = [rule['const']] if 'const' in rule else rule.get('enum')
                if choices is not None:
                    original = [old['const']] if 'const' in old else old.get('enum')
                    choices = [v for v in choices if original is None or v in original]
                    if not choices:
                        refined = False
                    else:
                        refined.pop('const', None)
                        refined['enum'] = choices
                if refined is not False and 'x-source-facts-token' in rule:
                    refined['x-source-facts-token'] = rule['x-source-facts-token']
            branch['properties'][name] = refined
        branches.append(branch)
    return {'oneOf': branches} if branches else False


def compact(text):
    # The same normalization as the acquired literal-citation guard. Do not
    # infer a subsection from a general reference to its parent section.
    return text.lower().replace('section', '').replace('§', '').replace(' ', '')


def admissible(public, targets=()):
    facts = compact(public['facts'])
    return {name for name, citation in CITATIONS.items()
            if compact(citation) in facts and name not in targets}


def validate_givens(binding, public):
    permitted = admissible(public)
    for row in binding['facts'] + binding['negative_givens']:
        name = row['predicate']
        if name in GIVENS and name not in permitted:
            raise ValueError('Exact source-stated premise lacks its literal citation: '
                             + name + ' requires ' + CITATIONS[name])


def constrain(schema, public, kernel, *, source_tokens=True):
    """Restrict declared native-given predicates; preserve all other values.

    Both current observation formats declare native predicates in a record's
    ``predicate`` enum. Fields describing observations or boundary statements
    use different types, and are untouched. Empty arrays and null are distinct.
    """
    allowed = admissible(public, {c['predicate'] for c in kernel['native_query']})

    def visit(node):
        if isinstance(node, list):
            return [visit(item) for item in node]
        if not isinstance(node, dict):
            return node
        if node.get('type') == 'object' and 'properties' in node:
            # Actual acquired schemas also put the discriminator inside
            # allOf:[{oneOf:...}]. Lift that conjunction before distribution;
            # otherwise xgrammar discards the common required object fields.
            for index, clause in enumerate(node.get('allOf', [])):
                if isinstance(clause, dict) and set(clause) == {'oneOf'}:
                    if 'oneOf' in node:
                        raise ValueError('Two object discriminators require an explicit joint schema')
                    node = deepcopy(node)
                    node['oneOf'] = clause['oneOf']
                    node['allOf'].pop(index)
                    if not node['allOf']:
                        node.pop('allOf')
                    return visit(node)
        if node.get('type') == 'object' and 'properties' in node and 'oneOf' in node:
            return visit(_object_disjunction(node))
        value = {key: visit(item) for key, item in node.items()}
        if value.pop('x-source-facts-token', False):
            choices = value.get('enum')
            if not choices or not all(isinstance(v, str) and v for v in choices):
                raise ValueError('An acquired source-token guard requires a finite nonempty string enum')
            value['enum'] = [v for v in choices if not source_tokens or re.search(
                r'(?<!\w)' + re.escape(v) + r'(?!\w)', public['facts'], re.IGNORECASE)]
            if not value['enum']:
                return False
        properties = value.get('properties', {})
        if any(properties.get(name) is False for name in value.get('required', [])):
            return False
        predicate = properties.get('predicate', {})
        names = predicate.get('enum')
        if names and set(names) <= set(GIVENS):
            kept = [name for name in names if name in allowed]
            if not kept:
                return False
            predicate['enum'] = kept
            citation = properties.get('citation')
            if isinstance(citation, dict) and 'enum' in citation:
                citation['enum'] = [v for v in citation['enum']
                                    if v in {CITATIONS[name] for name in kept}]
        for combinator in ('oneOf', 'anyOf'):
            if combinator in value:
                value[combinator] = [v for v in value[combinator] if v is not False]
                if not value[combinator]:
                    return False
        if value.get('items') is False:
            # xgrammar and the strict host both recognize the exact empty
            # array language; a separately allowed null remains allowed.
            value['maxItems'] = 0
        return value

    return visit(deepcopy(schema))
