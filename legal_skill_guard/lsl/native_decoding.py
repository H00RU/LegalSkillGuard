"""Label-free native inference, including a beam parser for given local nodes.

The NormBench parser never reads supplied parents. The same entry accepts
generated nodes or evaluator-separated gold local nodes for the predeclared
composition diagnostic. All neural features match the trained composer.
"""
from copy import deepcopy
import itertools

import torch

from .composition import _partial_valid
from .composition_data import node_text,valid_graph
from .projection import compact
from .semantic_witness import assignments,evaluate,square_candidates
from .native_scope import inference_square
from .native_semantics import norm_graph,predict,horn_scope_squares
from .horn_codec import normalize as normalize_horn
from .native_composition import source_text


def norm_feature_texts(record,graph):
    """All possible depth<=3 ancestor texts, independent of any parent gold."""
    texts=[source_text(record)]+[node_text(n)for n in graph['nodes']]
    operators=sorted({node_text(n)for n in graph['nodes'] if n['kind'] in ('AND','OR')})
    heads=sorted({node_text(n)for n in graph['nodes'] if n['kind']=='branch'})
    for length in range(1,4):
        texts.extend(compact(list(seq))for seq in itertools.product(operators,repeat=length))
    for length in range(3):
        for seq in itertools.product(operators,repeat=length):texts.extend(compact([*seq,h])for h in heads)
    return list(dict.fromkeys(texts))


@torch.inference_mode()
def norm_beam(model,record,local,cache,beam_size=8):
    """Infer a full forest from local records, with no initial/gold parent use."""
    model.eval();nodes=local['nodes'];device=next(model.parameters()).device
    if not any(n['kind']=='branch' for n in nodes):raise ValueError('No acquired normative head')
    order=[i for i,n in enumerate(nodes)if n['kind'] in ('AND','OR')]+[i for i,n in enumerate(nodes)if n['kind']=='leaf']
    choices=[i for i,n in enumerate(nodes)if n['kind'] in ('branch','AND','OR')]
    initial=[-1 if n['kind']=='branch' else -2 for n in nodes];beams=[(0.,initial)];scored={}
    source=cache.mean(source_text(record)).to(device)
    def keys(parents):
        result=[]
        for i,p in enumerate(parents):
            if p<0:continue
            chain=[];a=p
            for _ in range(3):
                if a<0:break
                chain.append(node_text(nodes[a]));a=parents[a]
            result.append((node_text(nodes[i]),node_text(nodes[p]),compact(chain)))
        return result
    def score_missing(needed):
        need=[k for k in set(needed)if k not in scored]
        for start in range(0,len(need),512):
            batch=need[start:start+512]
            child=torch.stack([cache.mean(k[0])for k in batch]).to(device)
            parent=torch.stack([cache.mean(k[1])for k in batch]).to(device)
            ancestor=torch.stack([cache.mean(k[2])for k in batch]).to(device)
            energy=model.local(model.edge(torch.cat([source.expand(len(batch),-1),child,parent,ancestor],-1))).flatten()
            for k,e in zip(batch,energy):scored[k]=float(e)
    for i in order:
        expanded=[];needed=[]
        for _,parents in beams:
            for p in choices:
                if not _partial_valid(nodes,parents,i,p):continue
                candidate=list(parents);candidate[i]=p;ek=keys(candidate)
                expanded.append((candidate,ek));needed.extend(ek)
        if not expanded:raise ValueError('No legal full-node beam continuation')
        score_missing(needed)
        beams=sorted([(sum(scored[k]for k in ek),parents)for parents,ek in expanded],key=lambda x:x[0],reverse=True)[:beam_size]
    graphs=[{**{k:deepcopy(v)for k,v in local.items()if k!='parents'},'parents':p}for _,p in beams]
    graphs=[g for g in graphs if valid_graph(g)]
    if not graphs:raise ValueError('No legal complete forest')
    return graphs,{'beam_size':beam_size,'complete_forests':len(graphs),'scored_edge_contexts':len(scored),'input_parents_read':False}


def norm_squares(graphs,maximum=16):
    if not graphs:return []
    keys,values,_=assignments(graphs[0],64);out=[];seen=set()
    for graph in graphs:
        for square in square_candidates(graph,maximum):
            identity=tuple(sorted(tuple(p)for p in square['parents']))
            if identity in seen:continue
            seen.add(identity);cells=[{**graph,'parents':p}for p in square['parents']]
            out.append({**square,'cells':cells,'predictions':[evaluate(c,keys,values).tolist()for c in cells]})
            if len(out)>=maximum:return out
    return out


def other_squares(record,output):
    """No grade/reference fields are accessed; native outputs are self-executed."""
    d=record['dataset']
    if d=='ProofWriter_OWA_depth5':
        program=normalize_horn(output['program']);primary={'program':program};out=[]
        for s in horn_scope_squares(program,record['key']):
            execution=[predict(record,c)for c in s['cells']]
            if all(e['valid']for e in execution):out.append({**s,'predictions':[e['answer']for e in execution]})
        return primary,out
    if d in ('SARA_v2_Binary','RuleArena_Airline'):
        s=inference_square(output['program'],record['public'],d,record['key'])
        return output,[s]if s is not None else []
    if d=='ContractNLI':return output,[]
    raise ValueError(d)


@torch.inference_mode()
def select_norm(model,record,forests,squares,cache,mode):
    pool={tuple(g['parents']):g for g in forests};energies={}
    for s in squares:
        local,q=model.square(record,s['cells'],cache,interactions=mode!='ordinary',behaviors=s['predictions'])
        for g,j in zip(s['cells'],q):
            key=tuple(g['parents']);pool[key]=g
            if mode!='ordinary':energies.setdefault(key,[]).append(float(j))
    scores={}
    for key,g in pool.items():
        local,_=model.square(record,[g],cache,interactions=False)
        scores[key]=float(local[0])+(sum(energies[key])/len(energies[key])if key in energies else 0.)
    selected=max(scores,key=scores.get)
    return pool[selected],{'candidate_forests':len(pool),'beam_forests':len(forests),'squares':len(squares),
        'directed_head_used':mode!='ordinary' and bool(squares),'mode':mode,'score':scores[selected]}
