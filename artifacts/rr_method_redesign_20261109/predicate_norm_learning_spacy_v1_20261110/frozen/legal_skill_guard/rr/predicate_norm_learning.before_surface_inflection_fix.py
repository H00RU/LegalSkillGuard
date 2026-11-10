"""Learn a small typed semantic transducer from source predicate structures.

Predicate structures contain observed syntax, not normative effect labels.
The learned lexicon and type-guarded modal composition are explicit parameters.
This prototype is not a full contract parser or a claim of new type theory.
"""
from copy import deepcopy
import itertools
import json
import re

from .source_attachment_forests import information_reference

HEAD_OPS = ['P', 'O', 'F', 'BREACH', 'OTHER']
MODAL_OPS = ['IDENTITY', 'P', 'O', 'F']
# Conservative routing categories, retaining each actual predicate as the A
# witness. An earlier source-anchor menu is not a semantic alias dictionary:
# notably copying is not retention, and destroying is not a return predicate.
STEMS = {'share': ['disclos', 'share'], 'return_or_destroy': ['return'], 'retain': ['retain']}


def lexical(value):
    return ' '.join(value.casefold().split())


def action(predicate):
    matches = [k for k, stems in STEMS.items() if any(lexical(predicate).startswith(s) for s in stems)]
    return matches[0] if len(matches) == 1 else None


def validate(unit):
    graph = unit['syntax'];nodes = {n['id']: n for n in graph['nodes']}
    if len(nodes) != len(graph['nodes']):
        raise ValueError('Duplicate predicate ID')
    for n in nodes.values():
        if not n['predicate_quote']:
            raise ValueError('Missing source predicate')
        if len(n['predicate_quote'].split()) != 1:
            raise ValueError('Predicate head must be a single lexical source token')
        for k in ['predicate_quote', 'modal_quote', 'negation_quote', 'actor_quote', 'object_quote']:
            if n[k] and n[k] not in unit['text']:
                raise ValueError('Nonliteral predicate field: ' + n['id'] + ':' + k)
    signatures = {}
    for n in nodes.values():
        signature = tuple(n[k] for k in ['predicate_quote', 'modal_quote', 'negation_quote', 'actor_quote', 'object_quote'])
        if signature in signatures and unit.get('focus', unit['text']).count(n['predicate_quote']) == 1:
            raise ValueError('Duplicate description of one literal predicate occurrence')
        signatures[signature] = n['id']
    parents = {}
    for e in graph['edges']:
        if e['parent'] not in nodes or e['child'] not in nodes or e['parent'] == e['child']:
            raise ValueError('Invalid predicate edge')
        if e['quote'] and e['quote'] not in unit['text']:
            raise ValueError('Nonliteral relation quote')
        if e['relation'] in {'complement', 'condition'}:
            if e['child'] in parents:
                raise ValueError('Ambiguous governing parent')
            parents[e['child']] = e
    for node in nodes:
        seen = set();current = node
        while current in parents:
            if current in seen:
                raise ValueError('Cyclic governing predicates')
            seen.add(current);current = parents[current]['parent']
    return nodes, parents


def enrich(unit):
    """The existing unique-reference resolver is common to all controls."""
    value = deepcopy(unit);validate(value)
    for n in value['syntax']['nodes']:
        anchor, proof = information_reference({'source_quotes': [value['text']]}, n)
        n['information_anchor'] = anchor
        n['information_binding_proof'] = proof
    return value


def paths(unit):
    nodes, parents = validate(unit);out = []
    for n in nodes.values():
        if action(n['predicate_quote']) is None:
            continue
        path = [n['id']];links = []
        while path[-1] in parents:
            e = parents[path[-1]];links.append(e);path.append(e['parent'])
        out.append((n, path, links))
    return out


def transduce(unit, state, *, discover_modal_guards=False):
    nodes, _ = validate(unit);frames = [];needed = set()
    for conduct, path, links in paths(unit):
        expr, typ, missing, used = 'A', 'Action', [], []
        for i, nid in enumerate(path):
            n = nodes[nid]
            if i:
                word = lexical(n['predicate_quote']);op = state['heads'].get(word)
                if op is None:
                    missing.append('head:' + word);expr = None;break
                expr = [op, expr];typ = 'Consequence' if op == 'BREACH' else 'Other' if op == 'OTHER' else 'Norm'
                used.append(['head', word, op])
            if n['negation_quote']:
                word = lexical(n['negation_quote']);op = state['negations'].get(word)
                if op is None:
                    missing.append('negation:' + word);expr = None;break
                if op == 'NOT':expr = ['NOT', expr]
                used.append(['negation', word, op])
            if n['modal_quote']:
                key = lexical(n['modal_quote']) + ':' + typ;needed.add(key)
                op = state['modals'].get(key)
                if op is None and discover_modal_guards:
                    op = 'IDENTITY'
                if op is None:
                    missing.append('modal:' + key);expr = None;break
                if op != 'IDENTITY':expr = [op, expr];typ = 'Norm'
                used.append(['modal', key, op])
        governor = nodes[path[-1]]
        qualifications = [e for e in unit['syntax']['edges'] if
            (e['parent'] in path and e['relation'] in {'condition', 'reference'}) or
            (e['child'] == conduct['id'] and e['relation'] == 'exception')]
        frame = {'predicate_id': conduct['id'], 'governor_id': governor['id'],
                 'action': action(conduct['predicate_quote']), 'formula': expr,
                 'actor_quote': governor['actor_quote'], 'object_quote': conduct['object_quote'],
                 'information_anchor': conduct.get('information_anchor', ''),
                 'conditions': list(dict.fromkeys(e['quote'] for e in qualifications if e['relation'] != 'reference' and e['quote'])),
                 'references': list(dict.fromkeys(e['quote'] for e in qualifications if e['relation'] == 'reference' and e['quote'])),
                 'exception_target': None, 'missing_parameters': missing,
                 'learned_parameters_used': used, 'source_path': path,
                 'source_predicate_quotes': [nodes[p]['predicate_quote'] for p in path],
                 'not_a_deterministic_format_adaptation': True}
        frames.append(frame)
    if state['bind_exceptions']:
        for e in unit['syntax']['edges']:
            if e['relation'] != 'exception':continue
            children = [f for f in frames if f['predicate_id'] == e['child']]
            parents = [f for f in frames if e['parent'] in {f['predicate_id'], f['governor_id']}]
            if len(children) != 1 or len(parents) != 1:continue
            c, p = children[0], parents[0]
            if c['actor_quote'] and lexical(c['actor_quote']) == lexical(p['actor_quote']) and c['information_anchor'] and lexical(c['information_anchor']) == lexical(p['information_anchor']):
                c['exception_target'] = p['predicate_id']
    return {'frames': frames, 'needed_modal_guards': sorted(needed),
            'fallback': False, 'whole_contract_correctness_not_claimed': True}


def feedback_checks(units, state):
    outputs = {u['key']: transduce(u, state) for u in units}
    return score_outputs(outputs)


def validate_outputs(unit, output):
    def formula(value, depth=0):
        if depth > 16:raise ValueError('Formula nesting exceeds the prototype')
        if value in [None, 'A']:return
        if not isinstance(value, list) or len(value) != 2 or value[0] not in HEAD_OPS + ['NOT']:
            raise ValueError('Unsupported semantic formula')
        formula(value[1], depth + 1)
    frames = output['frames'];ids = [f['predicate_id'] for f in frames]
    if len(set(ids)) != len(ids):raise ValueError('Duplicate source frame ID')
    for f in frames:
        if f['action'] not in STEMS:raise ValueError('Unsupported conduct category')
        formula(f['formula'])
        if not f['source_predicate_quotes']:raise ValueError('No source predicate evidence')
        for key in ['source_predicate_quotes', 'conditions', 'references']:
            if any(not q or q not in unit['text'] for q in f[key]):raise ValueError('Nonliteral frame evidence')
        for key in ['actor_quote', 'object_quote', 'information_anchor']:
            if f[key] and f[key] not in unit['text']:raise ValueError('Nonliteral role binding')
        if f['exception_target'] is not None and (f['exception_target'] not in ids or f['exception_target'] == f['predicate_id']):
            raise ValueError('Invalid source exception target')
    return output


def score_outputs(outputs):
    """Existing visible TRAIN feedback; shared unchanged with the free learner."""
    out = {}
    f15 = outputs['p15']['frames'];f20 = outputs['p20']['frames'];f111 = outputs['p111']['frames']
    out['p15_source_head'] = any(f['formula'] in [['F', 'A'], ['O', ['NOT', 'A']], ['NOT', ['P', 'A']]] and
        any('prohibited' in lexical(q) for q in f['source_predicate_quotes']) and
        any('Except as provided herein' in q for q in f['references']) for f in f15)
    out['p20_source_head'] = any(f['formula'] == ['NOT', ['BREACH', 'A']] and
        any('breached' in lexical(q) for q in f['source_predicate_quotes']) and
        any('if the Confidential Information is disclosed' in q for q in f['conditions']) for f in f20)
    returns = [f for f in f111 if f['action'] == 'return_or_destroy' and f['formula'] == ['O', 'A']]
    retained = [f for f in f111 if f['action'] == 'retain' and f['formula'] == ['P', 'A']]
    # The two existing111 Entailment labels require these native query witnesses.
    # They do not make every source condition or every other source correct.
    out['p111_nda16_positive_witness'] = bool(returns)
    out['p111_nda20_positive_witness'] = bool(retained)
    out['p111_joint_source_binding'] = any(c['exception_target'] == p['predicate_id'] and
        c['actor_quote'] and lexical(c['actor_quote']) == lexical(p['actor_quote']) and
        c['information_anchor'] and lexical(c['information_anchor']) == lexical(p['information_anchor']) and
        any('archival' in lexical(q) for q in c['conditions']) for c in retained for p in returns)
    return {'checks': out, 'outputs': outputs, 'passed': all(out.values())}


def fit(units):
    """Exact finite typed-program induction from existing source feedback.

    No learned table is filled from DEV or unknown source predicates. Elementary
    logical operators and existing action categories are common machinery.
    """
    heads = sorted({lexical(validate(u)[0][p]['predicate_quote']) for u in units for _, path, _ in paths(u) for p in path[1:]})
    negations = sorted({lexical(n['negation_quote']) for u in units for n in u['syntax']['nodes'] if n['negation_quote']})
    if len(heads) > 4 or len(negations) > 2:
        raise ValueError('Actual syntax exceeds this explicitly finite prototype; preserve it before extending search')
    compatible, checked = [], 0
    for ops in itertools.product(HEAD_OPS, repeat=len(heads)):
        for negs in itertools.product(['IDENTITY', 'NOT'], repeat=len(negations)):
            prototype = {'heads': dict(zip(heads, ops)), 'negations': dict(zip(negations, negs)),
                         'modals': {}, 'bind_exceptions': False}
            guards = sorted({g for u in units for g in transduce(u, prototype, discover_modal_guards=True)['needed_modal_guards']})
            for modal_ops in itertools.product(MODAL_OPS, repeat=len(guards)):
                for binding in [False, True]:
                    state = {**prototype, 'modals': dict(zip(guards, modal_ops)), 'bind_exceptions': binding}
                    result = feedback_checks(units, state);checked += 1
                    if result['passed']:compatible.append(state)
    compatible.sort(key=lambda x: json.dumps(x, sort_keys=True))
    return {'states': compatible, 'programs_checked': checked,
            'accepted': bool(compatible), 'no_new_negation_or_modal_aliases_supplied': True,
            'mature_typed_synthesis_not_claimed_new_mathematics': True,
            'goal_complete': False}


def predict(unit, library):
    if not library['accepted']:
        raise ValueError('No compatible typed semantic program')
    results = [transduce(unit, state) for state in library['states']]
    first = results[0]
    for i, frame in enumerate(first['frames']):
        signatures = {json.dumps({k: value['frames'][i][k] for k in ['formula', 'conditions', 'references', 'exception_target']}, sort_keys=True) for value in results}
        if len(signatures) != 1:
            frame['formula'] = None;frame['exception_target'] = None
            frame['missing_parameters'].append('unresolved_version_space_disagreement')
    return {**first, 'compatible_programs': len(results), 'semantic_correctness_still_requires_source_review': True}
