"""Native execution for acquired records; no reference substitutions.

TRAIN supervision is accepted only by explicitly named scoring functions.
All prediction functions depend on public input and acquired records alone.
"""
from collections import defaultdict
from copy import deepcopy
import itertools
import random

import numpy as np

from legal_skill_guard.rr.horn import Atom,Rule,closure,variables
from .composition_data import b0_to_graph,children_of,valid_graph,atom_keys
from .projection import compact
from .role_codec import decode_wire,encode_native
from .safe_program import execute as execute_python,validate as validate_python


def decode_horn(program):
    if not isinstance(program,dict) or set(program)!={'facts','rules','query'}:raise ValueError('Horn root fields')
    def atom(value):
        if not isinstance(value,list) or len(value)!=3 or not isinstance(value[0],str) or not isinstance(value[1],list) or not all(isinstance(t,str) for t in value[1]) or type(value[2]) is not bool:raise ValueError('Invalid native Horn atom tuple')
        return Atom(value[0],tuple(value[1]),value[2])
    facts={atom(t) for t in program['facts']}
    rules=[Rule(tuple(atom(t) for t in r['body']),atom(r['head']),'predicted_rule_'+str(i)) for i,r in enumerate(program['rules'])]
    query=atom(program['query'])
    if any(variables(a) for a in facts) or variables(query):raise ValueError('Non-ground fact/query')
    for rule in rules:
        if not variables(rule.head)<={v for a in rule.body for v in variables(a)}:raise ValueError('Unsafe Horn variables')
    return facts,rules,query


def norm_graph(record,result):
    return b0_to_graph(decode_wire(result),record['public']['rule_text'],record['key'],record['family_id'])


def norm_result(graph):
    """Lossless serialization of the selected forest, without gold lookup."""
    valid_graph(graph,raise_error=True);children=children_of(graph);units={}
    def condition(i):
        node=graph['nodes'][i]
        if node['kind']=='leaf':return {'tag':node['tag'],'text':node['text']}
        return {'op':node['kind'],'items':[condition(c) for c in children[i]]}
    for i,node in enumerate(graph['nodes']):
        if node['kind']!='branch':continue
        h=node['head'];root=children[i]
        units.setdefault(node['unit'],[]).append({'a':h['a'],'k':h['k'],'e':h['e'],'c':condition(root[0]) if root else None})
    return encode_native({'units':[{'text':u,'b':b} for u,b in units.items()]})


def predict(record,result):
    d=record['dataset']
    if d=='NormBench':
        graph=norm_graph(record,result)
        return {'valid':True,'graph':graph,'answer':None,'fallback':False}
    if d=='ProofWriter_OWA_depth5':
        execution=closure(*decode_horn(result['program']))
        return {'valid':execution['status']=='closure_complete','answer':execution['answer'],
                'status':execution['status'],'fallback':False}
    if d in ('SARA_v2_Binary','RuleArena_Airline'):
        return {**execute_python(result['program'],record['public'],d),'fallback':False}
    if d=='ContractNLI':
        from .contract_wire import decode_evidence
        answers=result.get('answers');ids=list(record['public']['queries'])
        if not isinstance(answers,list) or len(answers)!=17 or len({a['id'] for a in answers})!=17 or {a['id'] for a in answers}!=set(ids):raise ValueError('All17 distinct native ContractNLI hypotheses required')
        for a in answers:
            if a['label'] not in ('Entailment','Contradiction','NotMentioned'):raise ValueError('ContractNLI native label')
            fields={'id','label'} if a['label']=='NotMentioned' else {'id','label','evidence'}
            if set(a)!=fields:raise ValueError('Unexpected native ContractNLI answer fields')
            if 'evidence'in a:decode_evidence(a['evidence'],len(record['public']['sentence_spans']))
        return {'valid':True,'answer':{a['id']:a['label'] for a in answers},'evidence':{a['id']:decode_evidence(a['evidence'],len(record['public']['sentence_spans'])) if 'evidence'in a else [] for a in answers},'fallback':False,'core_symbolic_execution':False}
    raise ValueError(d)


def norm_loss_domain(gold,candidates,identity,limit=64):
    """Independent native branch behavior on a common abstract truth domain.

    Role/source identity remains significant. A missing acquired head is an
    error; no predicted head is renamed using the reference to manufacture it.
    """
    from .semantic_witness import evaluate
    from .composition_data import canonical_graph
    from .data import nonspace
    # Anonymous native leaves are occurrence variables, not interchangeable
    # words. Normalize only a proved complete canonical identity, an already
    # preserved occurrence ID, or a unique content/unit match. Otherwise this
    # particular behavior table is unidentified; native structure learning is
    # still available. Never charge a wrong semantic loss for a serialization ID.
    def anonymous(g):
        groups=defaultdict(list)
        for n in g['nodes']:
            if n['kind']=='leaf' and len(n['support']['candidates'])!=1:
                groups[(nonspace(n['unit']),n['tag'],nonspace(n['text']))].append(n)
        return groups
    gg=anonymous(gold);normalized=[]
    for candidate in candidates:
        if canonical_graph(candidate)==canonical_graph(gold):normalized.append(gold);continue
        copy=deepcopy(candidate)
        for key,nodes in anonymous(copy).items():
            target=gg.get(key,[])
            if not target:continue
            if {n['id'] for n in nodes}<={n['id'] for n in target}:continue
            if len(nodes)==len(target)==1:nodes[0]['id']=target[0]['id']
            else:return {'errors':None,'signatures':None,'scorable':False,
                         'unscorable_reason':'ambiguous anonymous native occurrence alignment'}
        normalized.append(copy)
    candidates=normalized
    keys=sorted(set().union(*(set(atom_keys(g).values()) for g in [gold]+candidates)))
    rng=random.Random(identity+':native-loss-domain')
    exhaustive=len(keys)<=6
    bits=list(itertools.product((0,1),repeat=len(keys))) if exhaustive else [(0,)*len(keys),(1,)*len(keys)]+[tuple(rng.getrandbits(1) for _ in keys) for _ in range(limit-2)]
    values=np.asarray(bits,dtype=np.int8).reshape(len(bits),len(keys))
    def outputs(g):
        y=evaluate(g,keys,values);labels=[compact([n['unit'],n['head']['a'],n['head']['k'],n['head']['e']]) for n in g['nodes'] if n['kind']=='branch']
        # Distinct repeated heads retain occurrences, not one dictionary cell.
        counts=defaultdict(int);out={}
        for label,column in zip(labels,y.T):
            out[(label,counts[label])]=column;counts[label]+=1
        return out
    reference=outputs(gold);all_outputs=[outputs(g) for g in candidates]
    heads=sorted(set(reference).union(*(set(x) for x in all_outputs)))
    errors=[];signatures=[]
    for output in all_outputs:
        cells=[];signature=[]
        for h in heads:
            if h not in output or h not in reference:cells.extend([1]*len(values))
            else:cells.extend((output[h]!=reference[h]).astype(int).tolist())
            signature.extend(output[h].tolist() if h in output else [-1]*len(values))
        errors.append(float(np.mean(cells)) if cells else 0.);signatures.append(signature)
    return {'errors':errors,'signatures':signatures,'keys':keys,'assignments':values.tolist(),'exhaustive':exhaustive,'abstract_not_case_gold':True,'scorable':True}


def horn_scope_squares(program,identity,maximum=16):
    """Same atoms/heads/facts/query, only legal disjoint rule-body reattachment."""
    decode_horn(program)
    occurrences=[(i,j) for i,r in enumerate(program['rules']) for j,_ in enumerate(r['body'])]
    pairs=[(a,b) for a,b in itertools.combinations(occurrences,2) if a[0]!=b[0]]
    random.Random(identity+':horn-scope').shuffle(pairs);out=[];seen=set()
    for u,v in itertools.islice(itertools.combinations(pairs,2),512):
        if set(u)&set(v):continue
        cells=[]
        for a,b in ((0,0),(0,1),(1,0),(1,1)):
            p=deepcopy(program)
            for enabled,(x,y) in ((a,u),(b,v)):
                if enabled:p['rules'][x[0]]['body'][x[1]],p['rules'][y[0]]['body'][y[1]]=p['rules'][y[0]]['body'][y[1]],p['rules'][x[0]]['body'][x[1]]
            try:decode_horn(p)
            except ValueError:break
            cells.append({'program':p})
        if len(cells)!=4 or len({compact(p) for p in cells})!=4:continue
        key=tuple(sorted(compact(p) for p in cells))
        if key in seen:continue
        seen.add(key);out.append({'cells':cells,'axes':[u,v],'same_nodes_facts_query':True})
        if len(out)>=maximum:break
    return out
