"""Project the existing exact-citation premise contract into case schemas.

This restricts source-stated statutory givens, not derived applicability or
general event observations. Missing literal support never establishes a legal
negative. Null/unread channels retain their original meanings.
"""
from copy import deepcopy

from .sara_statute_kernel import GIVENS


CITATIONS = {
    's151_b': '151(b)', 's151_b_applies': '151(b)',
    's151_c_applies': '151(c)', 's152_c_1': '152(c)(1)',
    's63_f_1_A': '63(f)(1)(A)', 's63_f_1_B': '63(f)(1)(B)',
}
assert set(CITATIONS) == set(GIVENS)


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


def constrain(schema, public, kernel):
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
        value = {key: visit(item) for key, item in node.items()}
        properties = value.get('properties', {})
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
