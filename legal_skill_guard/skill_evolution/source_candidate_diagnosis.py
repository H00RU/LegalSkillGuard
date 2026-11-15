"""A finite typed, producing-query-bound envelope for acquired C candidates.

This diagnoses a frozen fragment/template interface, not English semantics or
all programs. No new literal, fragment, absence audit, renderer or query choice
is supplied. Relaxing body joins may expose a candidate, never certify its law.
"""
from copy import deepcopy
from itertools import product

from .relational_rules import canonical
from .scoped_grammar import constructors
from .source_composition import statement_fingerprint


def _variable(value):
    return value.get('var') if isinstance(value, dict) and set(value) == {'var'} else None


def _choice_guards(library, predicate):
    alternatives = []
    for rule in library['language']['rules']:
        if rule['head']['predicate'] != predicate:
            continue
        operations = {}
        for atom in rule['body']:
            if atom['predicate'] == 'reader_query' and atom['sign'] == 'positive':
                query, operation = atom['arguments']
                if _variable(query) and not isinstance(operation, dict):
                    operations[_variable(query)] = operation
        pairs = []
        for atom in rule['body']:
            if atom['predicate'] == 'query_choice' and atom['sign'] == 'positive':
                query, choice = atom['arguments']
                if _variable(query) in operations and not isinstance(choice, dict):
                    pairs.append((operations[_variable(query)], canonical(choice)))
        if pairs:
            alternatives.append(set(pairs))
    return alternatives


def missing_slot_demands(library, output):
    """Return type-level acquisition demands, without guessing their values."""
    shape = constructors(library['spec']); queries = {q['id']: q for q in output['queries']}
    groups = {q: [] for q, row in queries.items() if row['operation'] in ('source_clause_kind', 'source_retention_scope')}
    for fragment in output['fragments']:
        for group in set(fragment['query_ids']) & set(groups): groups[group].append(fragment)
    result = []
    for group, fragments in sorted(groups.items()):
        sorts = {shape[f['term'][0]]['sort'] for f in fragments}
        for renderer in library['renderers']:
            expected = set()
            def visit(value, sort=None):
                if isinstance(value, dict):
                    if 'term_argument' in value: expected.add(sort)
                    return
                for child, child_sort in zip(value[1:], shape[value[0]]['arguments']): visit(child, child_sort)
            visit(renderer['term'])
            if expected and expected - sorts:
                result.append({'producing_query': group, 'operation': queries[group]['operation'],
                    'source_units': queries[group]['unit_ids'], 'renderer': renderer['predicate'],
                    'missing_primitive_sorts': sorted(expected - sorts),
                    'available_primitive_sorts': sorted(sorts), 'no_required_legal_value_inferred': True})
    return result


def typed_envelope(library, output):
    shape = constructors(library['spec'])
    queries = {q['id']: q for q in output['queries']}
    answers = {a['id']: a for a in output['answers']}
    # These are the actual acquired producing-frame operations, not fresh
    # factual predicates. An unknown choice is never turned into an absence.
    group_ids = {q for q, value in queries.items()
                 if value['operation'] in ('source_clause_kind', 'source_retention_scope')}
    groups = {q: [] for q in group_ids}
    for index, fragment in enumerate(output['fragments']):
        for q in set(fragment['query_ids']) & group_ids:
            groups[q].append((index, fragment))
    result = []; seen = set()
    for renderer in library['renderers']:
        expected = {}
        def slots(value, sort=None):
            if isinstance(value, dict):
                if set(value) != {'term_argument'}:
                    raise ValueError('Diagnostic covers only term-bound frame renderers')
                index = value['term_argument']
                if index in expected and expected[index] != sort:
                    raise ValueError('One renderer slot has incompatible acquired types')
                expected[index] = sort
            else:
                for child, child_sort in zip(value[1:], shape[value[0]]['arguments']):
                    slots(child, child_sort)
        slots(renderer['term'])
        # Zero-term absence templates need actual complete-source audit guards;
        # only the actual G closure may produce them, never this relaxed kernel.
        if not expected:
            continue
        guards = _choice_guards(library, renderer['predicate'])
        if not guards:
            continue
        for group, fragments in sorted(groups.items()):
            qids = {group} | {q for _, f in fragments for q in f['query_ids']}
            present = {(queries[q]['operation'], canonical(answers[q]['choice']))
                       for q in qids if q in queries and q in answers and answers[q]['choice'] != 'unknown'}
            # Original neural query/choice pairs are supplied explicitly by the
            # caller below, never guessed from the native supervision.
            present |= {(a['operation'], canonical(a['choice'])) for a in output.get('actual_neural_answers', [])
                        if a['id'] in qids and a['choice'] != 'unknown'}
            if not any(required <= present for required in guards):
                continue
            indices = sorted(expected)
            choices = [[(i, f) for i, f in fragments if shape[f['term'][0]]['sort'] == expected[slot]]
                       for slot in indices]
            if any(not c for c in choices):
                continue
            for combination in product(*choices):
                joint = set(combination[0][1]['support_ids'])
                for _, fragment in combination[1:]:
                    joint &= set(fragment['support_ids'])
                if not joint:
                    continue
                bindings = {slot: f for slot, (_, f) in zip(indices, combination)}
                def instantiate(value):
                    if isinstance(value, dict):
                        return deepcopy(bindings[value['term_argument']]['term'])
                    return [value[0], *(instantiate(v) for v in value[1:])]
                row = {'term': instantiate(renderer['term']), 'support_ids': sorted({u for _, f in combination for u in f['support_ids']})}
                identity = statement_fingerprint(row)
                if identity in seen:
                    continue
                seen.add(identity)
                result.append({'statement': row, 'renderer': renderer['predicate'], 'producing_query': group,
                    'actual_fragment_indices': [i for i, _ in combination],
                    'only_existing_terms_templates_and_definite_choices': True,
                    'source_semantics_not_certified': True})
    return result
