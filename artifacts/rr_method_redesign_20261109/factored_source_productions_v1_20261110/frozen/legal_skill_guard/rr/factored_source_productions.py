"""Factor paid source productions without inventing lexical or legal content.

This finite offline experiment is deliberately distinct from FUBL's full CCG
induction. It asks what recombination alone can acquire from the actual bank.
"""
from copy import deepcopy
import hashlib
import itertools
import json


def _id(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()[:16]


def named_body(pattern, name):
    """Find one named group's body, respecting escapes and character classes."""
    token = '(?P<' + name + '>'
    if pattern.count(token) != 1:
        raise ValueError('Exactly one named group required: ' + name)
    start = pattern.index(token) + len(token)
    depth, escaped, in_class = 1, False, False
    for i in range(start, len(pattern)):
        c = pattern[i]
        if escaped:
            escaped = False
        elif c == '\\':
            escaped = True
        elif c == '[' and not in_class:
            in_class = True
        elif c == ']' and in_class:
            in_class = False
        elif not in_class and c == '(':
            depth += 1
        elif not in_class and c == ')':
            depth -= 1
            if not depth:
                return start, i
    raise ValueError('Unclosed named group: ' + name)


def factor(productions):
    """Extract observed head/action lexemes and exact reconstruction templates.

    Norm kind travels with its acquired head. The action category travels with
    its acquired behavior. Conditions, references and rewrite policy stay with
    the surrounding template. Cross products are hypotheses, never certificates.
    """
    heads, actions, templates, originals = {}, {}, {}, []
    for p in productions:
        pattern = p['pattern']
        hs, he = named_body(pattern, 'head')
        bs, be = named_body(pattern, 'behavior')
        if not (he <= bs or be <= hs):
            raise ValueError('Overlapping lexical groups cannot be factored')
        h = {'pattern': pattern[hs:he], 'kind': p['kind']}
        a = {'pattern': pattern[bs:be], 'action': p['action']}
        skeleton = pattern
        for start, end, marker in sorted([(hs, he, '@HEAD@'), (bs, be, '@BEHAVIOR@')], reverse=True):
            skeleton = skeleton[:start] + marker + skeleton[end:]
        t = {'pattern': skeleton, 'condition_groups': p['condition_groups'],
             'reference_groups': p['reference_groups'], 'clear_overrides': p['clear_overrides']}
        hi, ai, ti = _id(h), _id(a), _id(t)
        for bank, key, item in [(heads, hi, h), (actions, ai, a), (templates, ti, t)]:
            bank.setdefault(key, {**item, 'origin_ids': []})['origin_ids'].append(p['id'])
        reconstructed = skeleton.replace('@HEAD@', h['pattern']).replace('@BEHAVIOR@', a['pattern'])
        if reconstructed != pattern:
            raise ValueError('Factorization changed the original production')
        originals.append({'id': p['id'], 'head': hi, 'action': ai, 'template': ti,
                          'exact_original_pattern_reconstructed': True})
    return {'heads': heads, 'actions': actions, 'templates': templates, 'originals': originals,
            'new_surface_lexemes_supplied': False, 'new_semantics_supplied': False}


def recombine(library):
    """Enumerate finite recombinations, with original provenance on every part."""
    out = []
    original = {(p['head'], p['action'], p['template']) for p in library['originals']}
    for (hi, h), (ai, a), (ti, t) in itertools.product(
            library['heads'].items(), library['actions'].items(), library['templates'].items()):
        p = {k: deepcopy(t[k]) for k in ['pattern', 'condition_groups', 'reference_groups', 'clear_overrides']}
        p['pattern'] = p['pattern'].replace('@HEAD@', h['pattern']).replace('@BEHAVIOR@', a['pattern'])
        p.update(id='factor-' + _id([hi, ai, ti]), kind=h['kind'], action=a['action'])
        out.append({'production': p, 'head_id': hi, 'action_id': ai, 'template_id': ti,
                    'observed_combination': (hi, ai, ti) in original,
                    'source_production_origins': {'head': h['origin_ids'], 'action': a['origin_ids'],
                                                  'template': t['origin_ids']},
                    'recombined_hypothesis_not_semantic_adaptation': True})
    return out


def learn_consistent_bank(library, documents, feedback):
    """Minimum consistent bank using cached real-source production executions.

    Finite enumeration minimizes production count, bytes and stable IDs. It is
    a synthesis baseline, not a new optimizer. Native TRAIN regression and
    source-head feedback have positive witnesses. Binding edges are outside
    this interface and must not be marked as learned.
    """
    from .contract_attachment_update import annotations, production_code, rewrite
    from .contract_compiler_runtime import scope_answer
    candidates = recombine(library)
    if len(candidates) > 12:
        raise ValueError('This finite diagnostic does not support a larger search')
    cached = {}
    for c in candidates:
        p = c['production']
        cached[p['id']] = {m['key']: annotations(production_code([p]), m['document']) for m in documents}
    ordered = []
    for n in range(len(candidates) + 1):
        for subset in itertools.combinations(candidates, n):
            ps = [c['production'] for c in subset]
            ordered.append(((n, len(json.dumps(ps, sort_keys=True).encode()), tuple(p['id'] for p in ps)), subset))
    trace = []
    for objective, subset in sorted(ordered, key=lambda x: x[0]):
        states, checks = {}, []
        for m in documents:
            records = []
            for c in subset:
                for record in cached[c['production']['id']][m['key']]:
                    if record not in records:
                        records.append(record)
            state = rewrite(m['graph'], records)
            states[m['key']] = state
            for e in m['examples']:
                answer = scope_answer(state['graph'], m['document'], e['id'])
                checks.append({'id': m['key'] + ':' + e['id'], 'passed': answer['answer'] == e['answer']})
        for f in feedback:
            s = states[f['key']]
            good = [a for a in s['attachments'] if f['anchor_contains'] in a['quote'] and a['kind'] == f['kind']
                    and a['action'] == f['action'] and f['head_contains'] in a['head']
                    and f['behavior_contains'] in a['behavior']
                    and (not f['reference_contains'] or any(f['reference_contains'] in q for q in a['references']))
                    and (not f['condition_contains'] or any(f['condition_contains'] in q for q in a['conditions']))]
            bad = [r for r in s['graph']['rules'] if r['action'] == f['action']
                   and r['effect'] in f['forbidden_effects_on_anchor']
                   and any(f['anchor_contains'] in q for q in r['source_quotes'])]
            checks.append({'id': f['id'], 'passed': bool(good) and not bad})
        passed = bool(checks) and all(c['passed'] for c in checks)
        trace.append({'objective': objective, 'passed': passed, 'checks': checks})
        if passed:
            return {'accepted_for_the_two_head_constraints_only': True,
                    'selected': list(subset), 'states': states, 'trace': trace,
                    'joint_exception_binding_expressible': False, 'goal_complete': False}
    return {'accepted_for_the_two_head_constraints_only': False, 'selected': [], 'trace': trace,
            'joint_exception_binding_expressible': False, 'goal_complete': False}
