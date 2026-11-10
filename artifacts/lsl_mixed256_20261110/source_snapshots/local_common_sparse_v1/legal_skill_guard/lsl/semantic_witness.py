"""Legal same-node scope alternatives and declared Boolean semantics.

No exclusion keyword inversion: each atom is the satisfaction of its native
condition literal. Abstract witnesses are not factual legal case labels.
"""
from copy import deepcopy
import itertools
import random

import numpy as np

from .composition_data import atom_keys, children_of, valid_graph
from .projection import compact, neutral


def assignments(graph,limit=64):
    keys=sorted(set(atom_keys(graph).values()));rng=random.Random(graph['item_id']+':witness-domain')
    exhaustive=len(keys)<=6
    bits=list(itertools.product((0,1),repeat=len(keys))) if exhaustive else [
        (0,)*len(keys),(1,)*len(keys)]+[tuple(rng.getrandbits(1) for _ in keys) for _ in range(limit-2)]
    return keys,np.asarray(bits,dtype=np.int8).reshape(len(bits),len(keys)),exhaustive


def evaluate(graph,keys,values):
    valid_graph(graph,raise_error=True);atoms=atom_keys(graph);columns={k:i for i,k in enumerate(keys)}
    children=children_of(graph);memo={}
    def ev(i):
        if i in memo:return memo[i]
        n=graph['nodes'][i]
        if n['kind']=='leaf':out=values[:,columns[atoms[i]]].astype(bool)
        else:
            parts=[ev(c) for c in children[i]]
            if n['kind']=='OR':out=np.logical_or.reduce(parts) if parts else np.zeros(len(values),dtype=bool)
            else:out=np.logical_and.reduce(parts) if parts else np.ones(len(values),dtype=bool)
        memo[i]=out;return out
    bs=[i for i,n in enumerate(graph['nodes']) if n['kind']=='branch']
    return np.stack([ev(i) for i in bs],axis=-1).astype(np.int8) if bs else np.empty((len(values),0),dtype=np.int8)


def proven_equivalent(left,right,timeout_ms=1500):
    if left['parents']==right['parents']:return True
    import z3
    keys=sorted(set(atom_keys(left).values())|set(atom_keys(right).values()));variables={k:z3.Bool(k) for k in keys}
    def formulas(graph):
        atoms=atom_keys(graph);children=children_of(graph);memo={}
        def ev(i):
            if i in memo:return memo[i]
            n=graph['nodes'][i]
            if n['kind']=='leaf':v=variables[atoms[i]]
            else:
                parts=[ev(c) for c in children[i]]
                v=z3.Or(*parts) if n['kind']=='OR' else z3.And(*parts)
            memo[i]=v;return v
        return [ev(i) for i,n in enumerate(graph['nodes']) if n['kind']=='branch']
    a=formulas(left);b=formulas(right)
    solver=z3.Solver();solver.set(timeout=timeout_ms)
    solver.add(z3.Or(*[x!=y for x,y in zip(a,b)]))
    result=solver.check()
    return True if result==z3.unsat else False if result==z3.sat else None


def legal_square(graph,pair_u,pair_v):
    if set(pair_u)&set(pair_v):return None
    graphs=[]
    for a,b in ((0,0),(0,1),(1,0),(1,1)):
        candidate={**graph,'parents':list(graph['parents'])}
        for active,(i,j) in ((a,pair_u),(b,pair_v)):
            if active:candidate['parents'][i],candidate['parents'][j]=candidate['parents'][j],candidate['parents'][i]
        if not valid_graph(candidate):return None
        graphs.append(candidate)
    return graphs


def square_candidates(graph,maximum=16,search_max=256):
    """Bounded same-node independent swaps, shared by M2 and Contrast."""
    leaves=[i for i,n in enumerate(graph['nodes']) if n['kind']=='leaf']
    pairs=[(i,j) for i,j in itertools.combinations(leaves,2) if graph['parents'][i]!=graph['parents'][j]]
    rng=random.Random(graph['item_id']+':independent-swaps');rng.shuffle(pairs)
    out=[];seen=set();tries=0
    for u,v in itertools.combinations(pairs,2):
        if tries>=search_max:break
        if set(u)&set(v):continue
        tries+=1;graphs=legal_square(graph,u,v)
        if graphs is None:continue
        identity=tuple(sorted(tuple(g['parents']) for g in graphs))
        if identity in seen:continue
        seen.add(identity);out.append({'pair_u':list(u),'pair_v':list(v),'parents':[g['parents'] for g in graphs]})
        if len(out)>=maximum:break
    return out


def annotate_square(graph,square,limit=64):
    keys,values,exhaustive=assignments(graph,limit)
    graphs=[{**graph,'parents':p} for p in square['parents']]
    y=np.stack([evaluate(g,keys,values) for g in graphs])
    gold=evaluate(graph,keys,values)
    losses=np.abs(y-gold[None]).mean(axis=(1,2)) if gold.shape[1] else np.zeros(4)
    interaction=y[3]-y[2]-y[1]+y[0]
    errors=np.abs(y-gold[None]);directed=errors[3]-errors[2]-errors[1]+errors[0]
    if not np.array_equal(directed,(1-2*gold)*interaction):raise ValueError('Signed error identity failed')
    equivalent=[];negative=[];unknown=[]
    for i,g in enumerate(graphs):
        if np.any(y[i]!=gold):negative.append(i)
        elif exhaustive:equivalent.append(i)
        else:
            eq=proven_equivalent(graph,g)
            (equivalent if eq is True else negative if eq is False else unknown).append(i)
    # SAT false with a sampled miss must still carry a real witness. For the
    # bounded first run, leave such cells unlabelled rather than fabricate it.
    witnessed_negative=[i for i in negative if np.any(y[i]!=gold)]
    for i in set(negative)-set(witnessed_negative):unknown.append(i)
    return {**square,'keys':keys,'assignments':values.tolist(),'exhaustive':exhaustive,
            'activation':y.tolist(), 'mean_errors':losses.tolist(),
            'nonzero_interaction_observed':bool(np.any(interaction)),
            'interaction_zero_proven':bool(exhaustive and not np.any(interaction)),
            'equivalent':equivalent,'negative':witnessed_negative,'unknown':sorted(set(unknown)),
            'truth_policy':'same unique source occurrence + role; ambiguous/inferred instances separate; native literal satisfaction, no keyword negation'}


def mine_training(graph,maximum=16,limit=64):
    return [annotate_square(graph,s,limit) for s in square_candidates(graph,maximum)]
