"""Source-scoped contract rule acquisition, execution and local revision.

The learned objects are source rules, qualified receiver domains and their
dependency links. Native questions have a public, fixed semantic interface.
No training label is an executable rule. No event condition is filled in.
This candidate still needs independent acquisition and cost evidence.
"""
from copy import deepcopy
from hashlib import sha256

from .semantic_frames import obj

S = {'type': 'string'}
A = lambda item: {'type': 'array', 'items': item}
DOMAINS = ['employees', 'third_parties', 'recipient', 'other']
EFFECTS = ['permission', 'obligation', 'prohibition']
ACTIONS = ['share', 'return_or_destroy', 'retain']
TRIGGERS = ['unconditional', 'termination', 'request', 'after_return_or_destruction', 'other']
ENUM = lambda xs: {'type': 'string', 'enum': xs}
SCOPE = obj({'id': S, 'domains': A(ENUM(DOMAINS)), 'source_quotes': A(S)})
RULE = obj({'id': S, 'effect': ENUM(EFFECTS), 'action': ENUM(ACTIONS),
            'scope_id': S, 'triggers': A(ENUM(TRIGGERS)), 'conditions': A(S),
            'source_quotes': A(S), 'overrides': A(S)})
GRAPH = obj({'policy_id': S, 'scopes': A(SCOPE), 'rules': A(RULE),
             'complete_query_ids': A(S), 'unresolved': A(S)})
SCHEMA = obj({'policies': A(GRAPH)})
QUERIES = {
    'nda-5': ('permission', 'share', 'employees', None),
    'nda-7': ('permission', 'share', 'third_parties', None),
    'nda-16': ('obligation', 'return_or_destroy', 'recipient', 'termination'),
    'nda-20': ('permission', 'retain', 'recipient', 'after_return_or_destruction'),
}


def validate(graph, document):
    scopes = {s['id']: s for s in graph['scopes']}
    rules = {r['id']: r for r in graph['rules']}
    if len(scopes) != len(graph['scopes']) or len(rules) != len(graph['rules']):
        raise ValueError('Duplicate source-local scope/rule ID')
    for value in [*scopes.values(), *rules.values()]:
        quotes = value['source_quotes']
        if not quotes or any(not q or q not in document for q in quotes):
            raise ValueError('Every object needs an exact quote from its own contract')
    for rule in rules.values():
        if rule['scope_id'] not in scopes:
            raise ValueError('A rule uses an undeclared receiver scope')
        if any(k not in rules or k == rule['id'] for k in rule['overrides']):
            raise ValueError('Invalid source-local exception link')
        if not rule['triggers']:
            raise ValueError('Do not silently supply a missing trigger')
    visiting, done = set(), set()
    def visit(k):
        if k in visiting:
            raise ValueError('Cyclic exception priority')
        if k in done:
            return
        visiting.add(k)
        for other in rules[k]['overrides']:
            visit(other)
        visiting.remove(k)
        done.add(k)
    for k in rules:
        visit(k)
    if any(q not in QUERIES for q in graph['complete_query_ids']):
        raise ValueError('Unsupported query cannot silently become a supported one')
    return scopes, rules


def execute(graph, document, query_id):
    scopes, rules = validate(graph, document)
    effect, action, domain, trigger = QUERIES[query_id]
    matching = [r for r in rules.values() if r['action'] == action
                and domain in scopes[r['scope_id']]['domains']
                and (trigger is None or trigger in r['triggers'])]
    suppressed = {k for r in matching for k in r['overrides']}
    active = [r for r in matching if r['id'] not in suppressed]
    positive = [r for r in active if r['effect'] == effect]
    negative = [r for r in active if r['effect'] == 'prohibition' and effect != 'prohibition']
    if positive and negative:
        answer, state = None, 'conflicting_source_claims'
    elif positive:
        answer, state = 'Entailment', 'source_rule_witness'
    elif negative:
        answer, state = 'Contradiction', 'explicit_source_prohibition'
    elif query_id in graph['complete_query_ids'] and not graph['unresolved']:
        answer, state = 'NotMentioned', 'acquired_query_coverage_without_matching_norm'
    else:
        answer, state = None, 'incomplete_acquisition'
    used = positive + negative
    evidence = list(dict.fromkeys(q for r in used for q in
                    scopes[r['scope_id']]['source_quotes'] + r['source_quotes']))
    return {'answer': answer, 'state': state, 'evidence': evidence,
            'rule_ids': [r['id'] for r in used],
            'preserved_conditions': {r['id']: r['conditions'] for r in used},
            'matching_rule_ids': [r['id'] for r in matching],
            'suppressed_rule_ids': sorted(suppressed), 'fallback': False}


class ScopeLibrary:
    def __init__(self, state=None):
        self.state = deepcopy(state or {})

    def update(self, graph, document):
        """Atomically accept a source graph; source identity owns all links.

        Revision replaces this source's graph, invalidates only its changed
        dependency component and reports affected queries. The caller must
        supply independent source/semantic review before treating an update
        as verified learning; exact quotes alone do not establish fidelity.
        """
        validate(graph, document)
        key = graph['policy_id']; old = self.state.get(key)
        if old and old['document_sha256'] != sha256(document.encode()).hexdigest():
            raise ValueError('A source update must not silently change its contract')
        old_items = {} if old is None else {('scope', x['id']): x for x in old['graph']['scopes']}
        if old:
            old_items.update({('rule', x['id']): x for x in old['graph']['rules']})
        items = {('scope', x['id']): x for x in graph['scopes']}
        items.update({('rule', x['id']): x for x in graph['rules']})
        changed = {k for k in old_items.keys() | items.keys() if old_items.get(k) != items.get(k)}
        affected = []
        for q in QUERIES:
            new = execute(graph, document, q)
            previous = None if old is None else execute(old['graph'], document, q)
            if new != previous:
                affected.append(q)
        self.state[key] = {'document_sha256': sha256(document.encode()).hexdigest(), 'graph': deepcopy(graph)}
        return {'policy_id': key, 'changed_objects': sorted([list(k) for k in changed]),
                'affected_queries': affected, 'independent_semantic_review_still_required': True}

    def export(self):
        return deepcopy(self.state)
