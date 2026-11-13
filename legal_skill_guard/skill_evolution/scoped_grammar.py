"""Induce typed source-to-term productions from acquired, grounded examples.

Constructors, their meanings, source alignments and the decision program are
learned. The host supplies only typed factoring, chart parsing and execution.
It contains no legal vocabulary, role aliases or consequence rules.
"""
from collections import defaultdict
from copy import deepcopy
import json

import jsonschema

from .native import record_schema, source_spans
from .objects import digest
from .source_schema import LABELS
from .span_compiler import execute_json, occurrences as quote_occurrences, token_spans, validate_procedure


CONSTRUCTOR = record_schema({'name': {'type': 'string'}, 'meaning': {'type': 'string'},
    'sort': {'type': 'string'}, 'arguments': {'type': 'array', 'items': {'type': 'string'}}})
SEED = record_schema({'source': {'type': 'string'},
    'source_span_ids': {'type': 'array', 'minItems': 1, 'uniqueItems': True,
                        'items': {'type': 'integer', 'minimum': 0}},
    'occurrence': {'type': 'integer', 'minimum': 0}, 'quote': {'type': 'string'},
    'term_json': {'type': 'string'}})
GRAMMAR = record_schema({'rationale': {'type': 'string'},
    'constructors': {'type': 'array', 'minItems': 1, 'items': CONSTRUCTOR},
    'seeds': {'type': 'array', 'minItems': 1, 'items': SEED},
    'decision_program': {'type': 'string'}})
RESULT = record_schema({'handled': {'type': 'boolean'},
    'answer': {'type': ['string', 'null'], 'enum': [None, *LABELS]},
    'used_nodes': {'type': 'array', 'uniqueItems': True,
                   'items': {'type': 'integer', 'minimum': 0}}})


def tokens(text):
    return tuple(t[0] for t in token_spans(text))


def material_public(public):
    """Only source material supplies legal evidence; hypotheses are separate."""
    value = {'source_text': public['source_text']}
    if 'sentence_spans' in public:
        value['sentence_spans'] = public['sentence_spans']
    return value


def ground_quote(seed, public):
    spans = source_spans(material_public(public))
    ids = set(seed['source_span_ids'])
    if not ids <= {s['id'] for s in spans}:
        raise ValueError('Source example cites an absent current span')
    selected = [s for s in spans if s['id'] in ids]
    a, b = min(s['start'] for s in selected), max(s['end'] for s in selected)
    hits = quote_occurrences(public['source_text'][a:b], seed['quote'])
    if seed['occurrence'] >= len(hits):
        raise ValueError('Explicit source quote occurrence is absent')
    start, end = hits[seed['occurrence']]
    start, end = start + a, end + a
    if any(s['id'] not in ids and start < s['end'] and s['start'] < end for s in spans):
        raise ValueError('Source quote crosses an uncited span')
    return start, end


class ConstructorSchema(dict):
    """Structural constructors plus explicitly declared finite string sorts."""
    def __init__(self, values, scalar_sorts):
        super().__init__(values)
        self.scalar_sorts = scalar_sorts


def constructors(spec):
    values = {c['name']: c for c in spec['constructors']}
    if len(values) != len(spec['constructors']):
        raise ValueError('Duplicate acquired semantic constructor')
    if any(not c['name'].isidentifier() or c['name'] in {*LABELS, 'literal'}
           or not c['sort'].isidentifier() or c['sort'] in LABELS
           or not c['meaning'].strip() or any(not s.isidentifier() for s in c['arguments'])
           for c in values.values()):
        raise ValueError('Explicit constructor meanings and type identifiers required')
    scalar_sorts = spec.get('scalar_sorts', {})
    structural_sorts = {c['sort'] for c in values.values()}
    for name, domain in scalar_sorts.items():
        if (not isinstance(name, str) or not name.isidentifier() or name in {'text', *LABELS}
                or name in structural_sorts or not isinstance(domain, list) or not domain
                or any(not isinstance(v, str) or v in LABELS for v in domain)
                or len(domain) != len(set(domain))):
            raise ValueError('A nominal scalar sort needs a distinct declared finite string domain')
    return ConstructorSchema(values, scalar_sorts)


def term_sort(term, schema, variables=()):
    if isinstance(term, dict) and set(term) == {'$'}:
        i = term['$']
        if type(i) is not int or i < 0 or i >= len(variables):
            raise ValueError('Unbound semantic variable')
        return variables[i]
    if isinstance(term, str):
        if term in LABELS:
            raise ValueError('Native answer in source semantics')
        return 'text'
    if not isinstance(term, list) or not term or not isinstance(term[0], str) or term[0] not in schema:
        raise ValueError('Unknown acquired semantic constructor')
    c = schema[term[0]]
    if len(term) - 1 != len(c['arguments']):
        raise ValueError('Semantic constructor arity mismatch')
    for child, expected in zip(term[1:], c['arguments']):
        actual = term_sort(child, schema, variables)
        if actual == expected:
            continue
        if (isinstance(child, str) and expected in schema.scalar_sorts
                and child in schema.scalar_sorts[expected]):
            continue
        raise ValueError('Semantic constructor argument sort mismatch')
    return c['sort']


def subterms(term, path=()):
    if isinstance(term, list):
        for i, value in enumerate(term[1:], 1):
            yield path + (i,), value
            yield from subterms(value, path + (i,))


def replace_paths(term, replacements, path=()):
    if path in replacements:
        return {'$': replacements[path]}
    if isinstance(term, list):
        return [term[0], *(replace_paths(v, replacements, path + (i,))
                           for i, v in enumerate(term[1:], 1))]
    return term


def instantiate(term, children):
    if isinstance(term, dict):
        return deepcopy(children[term['$']])
    if isinstance(term, list):
        return [term[0], *(instantiate(t, children) for t in term[1:])]
    return term


def occurrences(sequence, part):
    return [i for i in range(len(sequence) - len(part) + 1)
            if sequence[i:i + len(part)] == part]


def compatible(left, right):
    a, b, p = left['start'], left['end'], left['path']
    c, d, q = right['start'], right['end'], right['path']
    return not (a < d and c < b) and not (p[:len(q)] == q or q[:len(p)] == p)


def maximal_covers(candidates):
    """All maximal nonoverlapping source/semantic alignments, no nearest tie-break."""
    results = []
    def visit(index, chosen):
        if index == len(candidates):
            if chosen and not any(all(compatible(c, x) for x in chosen)
                                  for c in candidates if c not in chosen):
                results.append(sorted(chosen, key=lambda c: c['start']))
            return
        c = candidates[index]
        if all(compatible(c, x) for x in chosen):
            visit(index + 1, chosen + [c])
        visit(index + 1, chosen)
    visit(0, [])
    return results


def scope_patterns(pairs, schema):
    """Contrast identical surfaces with different acquired semantic bindings.

    Repeated difference vectors share one inherited variable. These variables
    remain open until the acquired source program supplies a current binding.
    """
    expanded = list(pairs)
    for anchor in pairs:
        if not isinstance(anchor['term'], list):
            continue
        head = anchor['term'][0]
        for parent in pairs:
            hits = occurrences(parent['source'], anchor['source'])
            children = [t for _,t in subterms(parent['term'])
                        if isinstance(t,list) and t[0] == head]
            if len(hits) != 1 or len(children) != 1:
                continue
            term = children[0]
            if term_sort(term, schema) != anchor['sort']:
                continue
            item = {'source': anchor['source'], 'term': term, 'sort': anchor['sort'],
                    'seed': parent['seed'], 'derived_from_unique_parent_alignment': True}
            if not any(p['source'] == item['source'] and p['term'] == term for p in expanded):
                expanded.append(item)
    groups = defaultdict(list)
    for p in expanded:
        groups[(p['source'], p['sort'])].append(p)
    patterns = []
    for (surface, sort), values in groups.items():
        terms = []
        for p in values:
            if p['term'] not in terms:
                terms.append(p['term'])
        if len(terms) < 2:
            continue
        slots, attributes, observed = {}, [], []
        def unify(items):
            if all(t == items[0] for t in items):
                return deepcopy(items[0])
            if (all(isinstance(t,list) for t in items)
                    and len({t[0] for t in items}) == 1
                    and len({len(t) for t in items}) == 1):
                return [items[0][0], *(unify([t[i] for t in items]) for i in range(1,len(items[0])))]
            sorts = [term_sort(t,schema) for t in items]
            if len(set(sorts)) != 1:
                raise ValueError('Incompatible contextual lexical sorts')
            key = digest(items)
            if key not in slots:
                slots[key] = len(attributes);attributes.append(sorts[0]);observed.append(deepcopy(items))
            return {'$scope': slots[key]}
        try:
            template = unify(terms)
        except ValueError:
            continue  # Keep the original alternatives; no coerced common type.
        if not attributes:
            continue
        body = {'source_tokens': list(surface), 'sort': sort, 'template': template,
                'inherited_sorts': attributes}
        patterns.append({'id':digest(body), **body,
            'observed_bindings': [[observed[i][j] for i in range(len(attributes))] for j in range(len(terms))],
            'seed_ids': sorted({p['seed'] for p in values}),
            'requires_current_source_binding': True})
    return patterns


def induce(spec, materials):
    """Factor demonstrated typed subterms into variable-bound productions.

    A new semantic node must come from acquisition; factoring can only combine
    witnessed constructors. This replaces the old fixed flat role interface.
    """
    jsonschema.validate(spec, GRAMMAR)
    schema = constructors(spec)
    validate_procedure(spec['decision_program'], allow_helpers=True)
    pairs = []
    for seed in spec['seeds']:
        if seed['source'] not in materials:
            raise ValueError('Non-TRAIN source example')
        ground_quote(seed, materials[seed['source']])
        term = json.loads(seed['term_json'])
        sort = term_sort(term, schema)
        source = tokens(seed['quote'])
        if not source:
            raise ValueError('Empty source production')
        pairs.append({'source': source, 'term': term, 'sort': sort, 'seed': digest(seed)})
    rules = {}
    def add(parts, sorts, target, origin, induced):
        # Unary zero-growth cycles cannot establish a new source distinction.
        if len(parts) == 1 and type(parts[0]) is int:
            return
        sort = term_sort(target, schema, sorts)
        body = {'parts': list(parts), 'child_sorts': list(sorts), 'target': target, 'sort': sort}
        key = digest(body)
        entry = rules.setdefault(key, {'id': key, **body, 'seeds': [], 'induced': induced})
        if origin not in entry['seeds']:
            entry['seeds'].append(origin)
        entry['induced'] = entry['induced'] or induced
        if len(rules) > 4096:
            raise ValueError('Production capacity exceeded; no partial grammar admitted')
    for pair in pairs:
        add(pair['source'], (), pair['term'], pair['seed'], False)
        candidates = []
        for path, term in subterms(pair['term']):
            for child in pairs:
                if child['term'] != term:
                    continue
                places = occurrences(pair['source'], child['source'])
                # Repeated mentions require acquired disambiguation, not a guess.
                if len(places) != 1:
                    continue
                a = places[0]
                c = {'start': a, 'end': a + len(child['source']), 'path': path,
                     'sort': child['sort']}
                if c not in candidates:
                    candidates.append(c)
        if len(candidates) > 18:
            raise ValueError('Alignment capacity exceeded; no silent selection')
        for cover in maximal_covers(candidates):
            parts, cursor = [], 0
            for i, child in enumerate(cover):
                parts.extend(pair['source'][cursor:child['start']])
                parts.append(i)
                cursor = child['end']
            parts.extend(pair['source'][cursor:])
            target = replace_paths(pair['term'], {c['path']: i for i, c in enumerate(cover)})
            add(parts, [c['sort'] for c in cover], target, pair['seed'], True)
    return {'constructors': deepcopy(spec['constructors']), 'rules': list(rules.values()),
            'acquired_pairs': pairs, 'scope_patterns': scope_patterns(pairs, schema),
            'disabled_rules': [], 'source_rejections': []}


def current_scope_nodes(grammar, text):
    lexical = token_spans(text);words=tuple(t[0] for t in lexical)
    out=[]
    for pattern in grammar.get('scope_patterns', []):
        for a in occurrences(words,tuple(pattern['source_tokens'])):
            b=a+len(pattern['source_tokens'])
            out.append({'id':len(out),'pattern_id':pattern['id'],'start':lexical[a][1],
                'end':lexical[b-1][2],'sort':pattern['sort'],'template':pattern['template'],
                'inherited_sorts':pattern['inherited_sorts'],'unresolved':True})
    return out


def parse(grammar, text, *, capacity=8000):
    lexical = token_spans(text)
    words = tuple(t[0] for t in lexical)
    nodes, keys = [], {}
    by_start = defaultdict(list)
    disabled = set(grammar['disabled_rules'])
    rules = [r for r in grammar['rules'] if r['id'] not in disabled]
    def add(a, b, rule, children):
        if a == b or (children and b - a <= max(nodes[c]['token_end'] - nodes[c]['token_start'] for c in children)):
            return False
        term = instantiate(rule['target'], [nodes[c]['term'] for c in children])
        key = (a, b, rule['sort'], digest(term))
        derivation = {'rule': rule['id'], 'children': list(children)}
        if key in keys:
            node = nodes[keys[key]]
            if derivation not in node['derivations']:
                node['derivations'].append(derivation)
            return False
        if len(nodes) >= capacity:
            raise ValueError('Parse capacity exceeded; ambiguity is not silently truncated')
        node = {'id': len(nodes), 'token_start': a, 'token_end': b,
                'start': lexical[a][1], 'end': lexical[b - 1][2],
                'sort': rule['sort'], 'term': term, 'derivations': [derivation]}
        keys[key] = node['id']
        nodes.append(node)
        by_start[(a, rule['sort'])].append(node['id'])
        return True
    changed = True
    while changed:
        changed = False
        for rule in rules:
            def match(index, pos, children):
                if index == len(rule['parts']):
                    yield pos, children
                    return
                part = rule['parts'][index]
                if isinstance(part, str):
                    if pos < len(words) and words[pos] == part:
                        yield from match(index + 1, pos + 1, children)
                else:
                    for nid in list(by_start[(pos, rule['child_sorts'][part])]):
                        yield from match(index + 1, nodes[nid]['token_end'], children + [nid])
            for start in range(len(words)):
                for end, children in match(0, start, []):
                    changed = add(start, end, rule, children) or changed
    groups = defaultdict(list)
    for n in nodes:
        groups[(n['start'], n['end'], n['sort'])].append(n['id'])
    for n in nodes:
        n['ambiguous'] = len(groups[(n['start'], n['end'], n['sort'])]) > 1
    return nodes


def execute(spec, grammar, public, task_id, question):
    text = public['source_text']
    spans = source_spans(material_public(public))
    nodes = parse(grammar, text)
    for n in nodes:
        n['support_ids'] = [s['id'] for s in spans if n['start'] < s['end'] and s['start'] < n['end']]
    result = execute_json(spec['decision_program'], {'task_id': task_id, 'question': question},
                          {'nodes': nodes}, allow_helpers=True)
    jsonschema.validate(result, RESULT)
    if any(i >= len(nodes) for i in result['used_nodes']):
        raise ValueError('Missing source-node proof')
    if result['handled']:
        if result['answer'] is None or not result['used_nodes']:
            raise ValueError('Handled result needs an acquired source-node proof')
        if any(nodes[i]['ambiguous'] for i in result['used_nodes']):
            raise ValueError('Used source interpretation remains ambiguous')
    used_rules, visited = set(), set()
    def visit(nid):
        if nid in visited:
            return
        visited.add(nid)
        for d in nodes[nid]['derivations']:
            used_rules.add(d['rule'])
            for c in d['children']:
                visit(c)
    for i in result['used_nodes']:
        visit(i)
    return {'value': result, 'nodes': nodes, 'used_rule_ids': sorted(used_rules),
            'used_induced_rule_ids': sorted(used_rules & {r['id'] for r in grammar['rules'] if r['induced']})}


def reject_interpretation(grammar, text, *, start, end, sort, term, review_origin):
    """Remove generalizations refuted by an explicit source-semantic review.

    A refuted acquired seed requires reacquisition. No replacement legal term
    or negative fact is fabricated by this deterministic refinement.
    """
    if not review_origin:
        raise ValueError('Actual source-semantic review required')
    grammar = deepcopy(grammar)
    nodes = parse(grammar, text)
    disputed = [n for n in nodes if (n['start'], n['end'], n['sort'], n['term']) == (start, end, sort, term)]
    induced = {r['id'] for r in grammar['rules'] if r['induced']}
    remove = set()
    def visit(nid):
        for d in nodes[nid]['derivations']:
            if d['rule'] in induced:
                remove.add(d['rule'])
            for c in d['children']:
                visit(c)
    for n in disputed:
        visit(n['id'])
    grammar['disabled_rules'] = sorted(set(grammar['disabled_rules']) | remove)
    still = parse(grammar, text)
    remaining = any((n['start'], n['end'], n['sort'], n['term']) == (start, end, sort, term) for n in still)
    grammar['source_rejections'].append({'source_digest': digest(text), 'start': start, 'end': end,
        'sort': sort, 'term': term, 'review_origin': review_origin,
        'disabled': sorted(remove), 'requires_new_acquisition': remaining,
        'new_legal_semantics_invented': False})
    return grammar
