"""Source learned legal relations and scoped defeasible terminal conclusions.

A small finite pilot, not a general legal framework. Signed facts are explicit;
missing facts are never converted to false. Ordinary joins and source-given
priorities are public components shared by every control.
"""
from copy import deepcopy
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
          'query':obj({'predicate':S,'arguments':{'type':'array','items':{'anyOf':[S,{'type':'null'}]}},'positive':{'type':'boolean'}}),'unresolved':A})
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
    if p is None or len(q['arguments'])!=len(p['roles']) or any(x is not None and (not isinstance(x,str) or var(x)) for x in q['arguments']):
        raise ValueError('Query must use declared roles; null projects an unasked participant')
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
    """Finite supported models: explicit evidence, source priorities and projection.

    Positive support requires a finite derivation. Inconsistent body evidence
    cannot be used to prove a downstream claim. Open, unasked participants are
    existentially projected; absence of a witness never proves its negation.
    """
    import z3
    predicates={p['name']:p for p in program['predicates']}
    def canon(a):
        terms=list(a['arguments'])
        for i,x in enumerate(terms):
            if isinstance(x,str) and re.fullmatch(r'\$[0-9][0-9,]*',x):terms[i]=x[1:].replace(',','')
        if predicates[a['predicate']]['functional'] and terms[-1]=='zero':terms[-1]='0'
        return a['predicate'],tuple(terms),a['positive']
    known={canon(x['atom']):{'fact_quote':x['quote']} for x in case['facts']}
    hard=set(known);ground={}
    while True:
        changed=False
        for r in program['rules']:
            for env,_ in _join(r,known):
                def instantiate(a):return canon({**a,'arguments':[env.get(t,t) for t in a['arguments']]})
                h=instantiate(r['head']);b=[instantiate(a) for a in r['body']]
                identity=(r['id'],tuple(sorted(env.items())))
                ground[identity]={'rule':r['id'],'authority':r['authority'],'bindings':env,'head':h,'body_keys':b}
                if h not in known:known[h]={};changed=True
        if not changed:break
    atoms=list(known);ix={a:i for i,a in enumerate(atoms)}
    truth={a:z3.Bool('legal_atom_'+str(i)) for a,i in ix.items()}
    rank={a:z3.Int('legal_rank_'+str(i)) for a,i in ix.items()}
    def opposite(a):return a[0],a[1],not a[2]
    def opposed(a,b):
        if a[0]!=b[0]:return False
        if predicates[a[0]]['functional']:
            return (a[1]==b[1] and a[2]!=b[2]) or (a[1][:-1]==b[1][:-1] and a[1][-1]!=b[1][-1] and a[2]==b[2])
        return opposite(a)==b
    rows=list(ground.values());enabled=[];winning=[]
    for g in rows:
        body=[]
        for a in g['body_keys']:
            body.append(truth[a])
            if opposite(a) in truth:body.append(z3.Not(truth[opposite(a)]))
        enabled.append(z3.And(*body))
    higher={r['id']:set() for r in program['rules']}
    if use_priorities:
        for p in program['priorities']:higher[p['higher']].add(p['lower'])
        for _ in range(len(higher)):
            for h in higher:higher[h]|=set().union(*(higher[x] for x in list(higher[h]))) if higher[h] else set()
    for i,g in enumerate(rows):
        defeaters=[enabled[j] for j,o in enumerate(rows) if g['rule'] in higher[o['rule']] and opposed(g['head'],o['head'])]
        winning.append(z3.And(enabled[i],z3.Not(z3.Or(*defeaters))))
    solver=z3.Solver();solver.set(timeout=10000)
    for a in atoms:
        support=[]
        for i,g in enumerate(rows):
            if g['head']==a:support.append(z3.And(winning[i],*[rank[b]<rank[a] for b in g['body_keys']]))
        enabled_heads=[winning[i] for i,g in enumerate(rows) if g['head']==a]
        solver.add(rank[a]>=0,rank[a]<=len(atoms),truth[a]==z3.Or(a in hard,*enabled_heads),
                   z3.Implies(truth[a],z3.Or(a in hard,*support)))
    if solver.check()!=z3.sat:return {'answer':None,'state':'no_supported_model_or_solver_unknown','unresolved':program['unresolved']+case['unresolved']}
    model=solver.model();q=canon(case['query'])
    def matches(a):return a[0]==q[0] and a[2]==q[2] and all(w is None or w==v for w,v in zip(q[1],a[1]))
    matching=[a for a in atoms if matches(a)]
    support=z3.Or(*[z3.And(truth[a],z3.Not(truth.get(opposite(a),z3.BoolVal(False)))) for a in matching])
    if None in q[1]:refute=z3.BoolVal(False)
    elif predicates[q[0]]['functional']:
        refute=z3.Or(*[truth[a] for a in atoms if opposed(q,a)])
    else:refute=truth.get(opposite(q),z3.BoolVal(False))
    def always(f):
        solver.push();solver.add(z3.Not(f));status=solver.check();solver.pop();return status==z3.unsat
    yes,no=always(support),always(refute)
    answer='Entailment' if yes and not no else 'Contradiction' if no and not yes else None
    def plain(a):return [a[0],list(a[1]),a[2]]
    active=[{**g,'head':plain(g['head']),'body_keys':[plain(a) for a in g['body_keys']]} for i,g in enumerate(rows) if z3.is_true(model.eval(winning[i]))]
    suppressed=[{'loser':{**g,'head':plain(g['head']),'body_keys':[plain(a) for a in g['body_keys']]}} for i,g in enumerate(rows) if z3.is_true(model.eval(enabled[i])) and not z3.is_true(model.eval(winning[i]))]
    return {'answer':answer,'state':'supported' if answer=='Entailment' else 'refuted' if answer=='Contradiction' else 'unknown_or_conflict',
            'query_supported':yes,'query_refuted':no,'known_atoms':[plain(a) for a in atoms if z3.is_true(model.eval(truth[a]))],
            'rule_witnesses':active,'suppressed':suppressed,
            'query_witnesses':[plain(a) for a in matching if z3.is_true(model.eval(truth[a])) and not z3.is_true(model.eval(truth.get(opposite(a),z3.BoolVal(False))))],
            'unresolved':program['unresolved']+case['unresolved'],'missing_evidence_is_false':False,
            'source_fidelity_proved':False,'evidence':'supported model relative to the accepted local translation, not a proof of NL fidelity'}

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


def evaluate_guard(program, case, rule_id, *, domains=None):
    """Evaluate an actual source antecedent, retaining negative call evidence.

    This is evaluation of the quoted condition, not contraposition of a Horn
    implication. The current reusable interface has one relation atom plus
    source-given distinctness constraints. Unknown input remains unknown.

    domains explicitly restricts the *formal question*. It does not assert
    that people found in a case exhaust the taxpayers in the native question.
    The caller must not silently replace an unbounded native question by one
    of these finite questions. No domain is inferred from missing evidence.
    """
    from itertools import product

    rules=[r for r in program['rules'] if r['id']==rule_id]
    if len(rules)!=1:raise ValueError('A unique learned source rule is required')
    rule=rules[0];query=case['query'];head=rule['head']
    if query['predicate']!=head['predicate'] or query['positive']!=head['positive']:
        raise ValueError('Call question does not name the learned source condition')
    if len(query['arguments'])!=len(head['arguments']):raise ValueError('Call arity differs')
    if len(rule['body'])!=1:raise ValueError('Only the actual one-atom legal guard interface is supported')
    head_variables={x for x in head['arguments'] if var(x)}
    body_variables={x for x in rule['body'][0]['arguments'] if var(x)}
    distinct_variables={x for row in rule['different'] for x in row.values() if var(x)}
    if not (body_variables|distinct_variables)<=head_variables:
        raise ValueError('Unbound local witness is not a closed call argument')
    projected=[i for i,x in enumerate(query['arguments']) if x is None]
    if domains is None and projected:
        result=run(program,case)
        return {'condition_value':True if result.get('query_supported',False) else None,
                'question':deepcopy(query),'scope':'unbounded_projection',
                'domains':None,'rule':rule_id,'source_guard':rule['guard_quote'],
                'branches':[], 'proof':result,
                'negative_evidence_is_not_universalized':True}
    if domains is not None:
        if set(domains)!=set(projected):raise ValueError('Declare exactly the projected formal-question roles')
        for values in domains.values():
            if not isinstance(values,(list,tuple)) or any(not isinstance(v,str) or not v or var(v) for v in values):
                raise ValueError('Finite query domains contain only explicit ground terms')
            if len(values)!=len(set(values)):raise ValueError('A query domain is a finite set, not repeated guesses')
    rows=[]
    assignments=product(*(domains[i] for i in projected)) if projected else [()]
    for values in assignments:
        arguments=list(query['arguments'])
        for index,value in zip(projected,values):arguments[index]=value
        env={};inconsistent=False
        for term,value in zip(head['arguments'],arguments):
            if var(term):
                if term in env and env[term]!=value:inconsistent=True
                env[term]=value
            elif term!=value:inconsistent=True
        def get(term):return env[term] if var(term) else term
        if inconsistent or any(get(d['left'])==get(d['right']) for d in rule['different']):
            rows.append({'arguments':arguments,'condition_value':False,'basis':'source role/distinctness constraint'})
            continue
        body=deepcopy(rule['body'][0]);body['arguments']=[get(t) for t in body['arguments']]
        subcase={**case,'query':body};result=run(program,subcase)
        value=True if result['answer']=='Entailment' else False if result['answer']=='Contradiction' else None
        rows.append({'arguments':arguments,'condition_value':value,'body_query':body,'proof':result})
    value=True if any(r['condition_value'] is True for r in rows) else False if all(r['condition_value'] is False for r in rows) else None
    return {'condition_value':value,'question':deepcopy(query),
            'scope':'declared_finite_projection' if projected else 'ground_call',
            'domains':deepcopy(domains),'rule':rule_id,'source_guard':rule['guard_quote'],
            'branches':rows,'negative_evidence_is_not_universalized':True}
