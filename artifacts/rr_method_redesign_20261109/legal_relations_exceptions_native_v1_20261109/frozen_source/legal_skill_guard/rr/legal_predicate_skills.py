"""Source learned legal relations and scoped defeasible terminal conclusions.

A small finite pilot, not a general legal framework. Signed facts are explicit;
missing facts are never converted to false. Ordinary joins and source-given
priorities are public components shared by every control.
"""
from copy import deepcopy
from itertools import product
import re
from .semantic_frames import obj

S={'type':'string'}
A={'type':'array','items':S}
ATOM=obj({'predicate':S,'arguments':A,'positive':{'type':'boolean'}})
PRED=obj({'name':S,'roles':A,'functional':{'type':'boolean'},'meaning':S})
RULE=obj({'id':S,'head':ATOM,'body':{'type':'array','items':ATOM},
          'different':{'type':'array','items':obj({'left':S,'right':S})},
          'guard_quote':S,'quote':S,'authority':S})
PRIORITY=obj({'higher':S,'lower':S,'quote':S})
PROGRAM=obj({'predicates':{'type':'array','items':PRED},'rules':{'type':'array','items':RULE},
             'priorities':{'type':'array','items':PRIORITY},'unresolved':A})
FACT=obj({'atom':ATOM,'quote':S})
CASE=obj({'ordinal':{'type':'integer'},'facts':{'type':'array','items':FACT},
          'query':ATOM,'unresolved':A})
CASES=obj({'cases':{'type':'array','items':CASE}})

def var(s):return isinstance(s,str) and re.fullmatch(r'\?[A-Za-z][A-Za-z0-9_]*',s) is not None

def key(atom):return (atom['predicate'],tuple(atom['arguments']),atom['positive'])

def validate(program, sources):
    """Check finite Horn input safety and provenance, not source fidelity."""
    predicates={}
    for p in program['predicates']:
        if p['name'] in predicates or not p['roles'] or len(set(p['roles']))!=len(p['roles']):
            raise ValueError('Duplicate/empty legal predicate signature')
        predicates[p['name']]=p
    def check(a):
        if a['predicate'] not in predicates or len(a['arguments'])!=len(predicates[a['predicate']]['roles']):
            raise ValueError('Predicate arity/signature mismatch: '+a['predicate'])
        if type(a['positive']) is not bool or any(not isinstance(t,str) or not t for t in a['arguments']):
            raise ValueError('Literal terms must be explicit nonempty strings')
    ids=set()
    for r in program['rules']:
        if r['id'] in ids:raise ValueError('Duplicate rule ID')
        ids.add(r['id']);check(r['head'])
        for a in r['body']:
            check(a)
            if predicates[a['predicate']]['functional']:
                raise ValueError('This finite pilot only permits terminal functional conclusions')
        bound={x for a in r['body'] for x in a['arguments'] if var(x)}
        used={x for x in r['head']['arguments'] if var(x)}
        used|={x for d in r['different'] for x in d.values() if var(x)}
        if used-bound:raise ValueError('Unsafe unbound head/distinct variable: '+r['id'])
        for field in ('guard_quote','quote'):
            if not r[field] or not any(r[field] in s for s in sources):
                raise ValueError('Rule quote absent from public source: '+r['id']+':'+field)
    graph={i:set() for i in ids}
    for p in program['priorities']:
        if p['higher'] not in ids or p['lower'] not in ids:raise ValueError('Unknown priority endpoint')
        if not p['quote'] or not any(p['quote'] in s for s in sources):raise ValueError('Priority quote missing')
        graph[p['higher']].add(p['lower'])
    for i in graph:
        frontier=list(graph[i]);seen=set()
        while frontier:
            j=frontier.pop()
            if j==i:raise ValueError('Cyclic legal priority')
            if j not in seen:seen.add(j);frontier.extend(graph[j])
        graph[i]=seen
    return {'predicates':predicates,'priority_closure':graph,'source_fidelity_proved':False}

def validate_case(case, facts, predicates):
    for row in case['facts']:
        a=row['atom'];p=predicates.get(a['predicate'])
        if p is None or len(a['arguments'])!=len(p['roles']) or any(var(x) for x in a['arguments']):
            raise ValueError('Non-ground or unknown factual relation')
        if not row['quote'] or row['quote'] not in facts:raise ValueError('Fact quote is absent')
        if type(a['positive']) is not bool:raise ValueError('Factual polarity must be explicit')
    q=case['query'];p=predicates.get(q['predicate'])
    if p is None or len(q['arguments'])!=len(p['roles']) or any(var(x) for x in q['arguments']):
        raise ValueError('Query must use a declared ground relation')
    return True

def _join(rule, known):
    states=[({},[])]
    for a in rule['body']:
        after=[]
        for env,proof in states:
            for k,why in known.items():
                if k[0]!=a['predicate'] or k[2]!=a['positive']:continue
                e=dict(env)
                for t,v in zip(a['arguments'],k[1]):
                    if var(t):
                        if t in e and e[t]!=v:break
                        e[t]=v
                    elif t!=v:break
                else:after.append((e,proof+[{'atom':list(k),'support':why}]))
        states=after
    def get(t,e):return e[t] if var(t) else t
    return [(e,p) for e,p in states if all(get(d['left'],e)!=get(d['right'],e) for d in rule['different'])]

def run(program, case, *, use_priorities=True):
    """Actual rule witnesses plus conflict-preserving terminal priority resolution."""
    predicates={p['name']:p for p in program['predicates']}
    known={key(x['atom']):{'fact_quote':x['quote']} for x in case['facts']}
    active=[]
    for _ in range(len(program['rules'])+1):
        changed=False
        for r in program['rules']:
            for env,proof in _join(r,known):
                args=tuple(env[x] if var(x) else x for x in r['head']['arguments'])
                k=(r['head']['predicate'],args,r['head']['positive'])
                trace={'rule':r['id'],'authority':r['authority'],'bindings':env,
                       'head':[k[0],list(k[1]),k[2]],'body':proof}
                if not any(t['rule']==r['id'] and t['bindings']==env for t in active):active.append(trace)
                if not predicates[k[0]]['functional'] and k not in known:
                    known[k]=trace;changed=True
        if not changed:break
    higher={r['id']:set() for r in program['rules']}
    for p in program['priorities']:higher[p['higher']].add(p['lower'])
    for _ in range(len(higher)):
        for h in higher:higher[h]|=set().union(*(higher[x] for x in list(higher[h]))) if higher[h] else set()
    functional=[t for t in active if predicates[t['head'][0]]['functional']]
    suppressed=[];surviving=[]
    for t in functional:
        k=t['head'];group=(k[0],k[1][:-1])
        winners=[o for o in functional if (o['head'][0],o['head'][1][:-1])==group
                 and t['rule'] in higher[o['rule']] and o['head']!=k] if use_priorities else []
        if winners:suppressed.append({'loser':t,'winners':winners})
        else:surviving.append(t)
    for t in surviving:
        k=t['head'];known[(k[0],tuple(k[1]),k[2])]=t
    q=key(case['query']);opposite=(q[0],q[1],not q[2]);supported=q in known;refuted=opposite in known
    if predicates[q[0]]['functional']:
        alternatives=[k for k in known if k[0]==q[0] and k[1][:-1]==q[1][:-1] and k[1][-1]!=q[1][-1] and k[2]==q[2]]
        refuted|=bool(alternatives)
    if supported and not refuted:answer='Entailment'
    elif refuted and not supported:answer='Contradiction'
    else:answer=None
    return {'answer':answer,'query_supported':supported,'query_refuted':refuted,
            'state':'conflict' if supported and refuted else 'supported' if supported else 'refuted' if refuted else 'unknown',
            'known_atoms':[[p,list(a),v] for p,a,v in known],
            'rule_witnesses':active,'suppressed':suppressed,'functional_survivors':surviving,
            'unresolved':list(case['unresolved'])+list(program['unresolved']),
            'missing_evidence_is_false':False,'source_fidelity_proved':False}

def normalized_guard(text, own_section):
    # Explicit source cross-reference resolution is syntax, not a legal guess.
    text=text.replace('this section','section '+str(own_section))
    return ' '.join(text.lower().split())

def learned_guards(program, sources):
    out=[]
    for r in program['rules']:
        own=next((re.search(r'§([0-9]+)',s).group(1) for s in sources if r['guard_quote'] in s),None)
        if own is not None:
            out.append({'normalized_guard':normalized_guard(r['guard_quote'],own),
                        'body':deepcopy(r['body']),'different':deepcopy(r['different']),
                        'learned_from_rule':r['id'],'authority':r['authority'],
                        'guard_quote':r['guard_quote']})
    return out

def match_guard(library, text, own_section):
    normalized=normalized_guard(text,own_section)
    return [deepcopy(t) for t in library if t['normalized_guard'] in normalized]
