"""Native source metrics. Gold is confined to this evaluation module.

Span F1 uses typed source spans with Hungarian IoU matching (threshold .5),
following NormBench's released evaluator. Inferred nodes are also evaluated
with typed-content and complete-graph metrics, never silently discarded.
"""
from collections import Counter, defaultdict
from copy import deepcopy
import json
import math

import numpy as np
from scipy.optimize import linear_sum_assignment

from .composition_data import (atom_keys,branch_of,canonical_graph,canonical_tree,
                               children_of,valid_graph)
from .data import nonspace, occurrences
from .projection import compact
from .semantic_witness import proven_equivalent


def f1(tp,pred,gold):
    return 2*tp/(pred+gold) if pred+gold else 1.


def branch_signature(n):
    anchor,kind,effects=json.loads(n['text'])
    return compact([nonspace(n['unit']),nonspace(anchor),kind,sorted(nonspace(e) for e in effects)])


def identity(node):
    if node['kind']=='branch':return 'branch',branch_signature(node)
    if node['kind']=='leaf':return 'leaf',node['tag'],nonspace(node['text'])
    return node['kind'],


def align_nodes(pred,gold):
    """Evaluation-only matching; structural context breaks lexical ties.

    The learned parser never receives this mapping or gold ancestry.
    """
    if not pred['nodes'] or not gold['nodes']:return {}
    cost=np.full((len(pred['nodes']),len(gold['nodes'])),1000.,dtype=np.float64)
    pc=children_of(pred);gc=children_of(gold)
    def context(g,i,children):
        root=branch_of(g,i);signature=branch_signature(g['nodes'][root]) if root>=0 else ''
        parent=g['parents'][i];kind=g['nodes'][parent]['kind'] if parent>=0 else ''
        child_types=Counter(identity(g['nodes'][c]) for c in children[i])
        return signature,kind,child_types
    for i,p in enumerate(pred['nodes']):
        for j,g in enumerate(gold['nodes']):
            if identity(p)!=identity(g):continue
            a=context(pred,i,pc);b=context(gold,j,gc)
            cost[i,j]=0.-.1*(a[0]==b[0])-.01*(a[1]==b[1])-.001*(a[2]==b[2])
            cost[i,j]-=.0001*(nonspace(p['unit'])==nonspace(g['unit']))
    rows,cols=linear_sum_assignment(cost)
    return {int(i):int(j) for i,j in zip(rows,cols) if cost[i,j]<1}


def span_records(graph):
    source=nonspace(graph['source']);records=[]
    for n in graph['nodes']:
        if n['kind']=='leaf':entries=[(n['tag'],n['text'])]
        elif n['kind']=='branch':
            a,k,e=json.loads(n['text']);entries=[('ANCH',a)]+[('EFFECT',t) for t in e]
        else:entries=[]
        for tag,text in entries:
            spans=occurrences(source,nonspace(text))
            # Matches the official first-occurrence convention for span F1.
            # The model inventory retains the whole ambiguity set separately.
            if spans:records.append((tag,spans[0]))
    return records


def span_score(pred,gold):
    a=span_records(pred) if pred else [];b=span_records(gold)
    if not a or not b:return {'tp':0,'pred':len(a),'gold':len(b),'f1':f1(0,len(a),len(b))}
    weights=np.zeros((len(a),len(b)),dtype=np.float64)
    for i,(ta,sa) in enumerate(a):
        for j,(tb,sb) in enumerate(b):
            if ta!=tb:continue
            intersection=max(0,min(sa[1],sb[1])-max(sa[0],sb[0]))
            union=max(sa[1],sb[1])-min(sa[0],sb[0])
            weights[i,j]=intersection/union if union else 0.
    rows,cols=linear_sum_assignment(-weights);tp=sum(weights[i,j]>=.5 for i,j in zip(rows,cols))
    return {'tp':int(tp),'pred':len(a),'gold':len(b),'f1':f1(tp,len(a),len(b))}


def content_set(graph):
    return Counter((n['tag'],nonspace(n['text'])) for n in graph['nodes'] if n['kind']=='leaf') if graph else Counter()


def role_sets(graph):
    out=defaultdict(set)
    if graph:
        for n in graph['nodes']:
            if n['kind']=='leaf':out[nonspace(n['text'])].add(n['tag'])
    return out


def score_source(pred,gold,error=None):
    valid=pred is not None and valid_graph(pred)
    if not valid:pred=None
    ps=content_set(pred);gs=content_set(gold);tp=sum((ps&gs).values())
    span=span_score(pred,gold);pc=sum(ps.values());gc=sum(gs.values())
    g_nonbranch=[i for i,n in enumerate(gold['nodes']) if n['kind']!='branch']
    p_nonbranch=[i for i,n in enumerate(pred['nodes']) if n['kind']!='branch'] if pred else []
    parent_tp=membership_tp=0;mapping=align_nodes(pred,gold) if pred else {}
    if pred:
        for i in p_nonbranch:
            if i not in mapping:continue
            gp=gold['parents'][mapping[i]];pp=pred['parents'][i]
            parent_tp+=mapping.get(pp,-999)==gp
            membership_tp+=mapping.get(branch_of(pred,i),-999)==branch_of(gold,mapping[i])
    pcount=len(p_nonbranch);gcount=len(g_nonbranch)
    canonical_exact=valid and canonical_graph(pred)==canonical_graph(gold)
    inventory_exact=bool(pred and len(mapping)==len(pred['nodes'])==len(gold['nodes']))
    equivalent=None
    if inventory_exact:
        mapped_parents=list(gold['parents'])
        for i,j in mapping.items():mapped_parents[j]=mapping[pred['parents'][i]] if pred['parents'][i]>=0 else -1
        mapped={**gold,'parents':mapped_parents}
        equivalent=proven_equivalent(gold,mapped)
    pr=role_sets(pred);gr=role_sets(gold)
    rtp=sum(len(pr.get(p,set())&tags) for p,tags in gr.items());rgold=sum(map(len,gr.values()))
    p_units={nonspace(n['unit']) for n in pred['nodes']} if pred else set()
    g_units={nonspace(n['unit']) for n in gold['nodes']}
    return {'item_id':gold['item_id'],'family_id':gold['family_id'],'valid':valid,'error':error,
            'node_span':span,'typed_content':{'tp':tp,'pred':pc,'gold':gc,'f1':f1(tp,pc,gc)},
            'parent_edges':{'tp':parent_tp,'pred':pcount,'gold':gcount,'f1':f1(parent_tp,pcount,gcount)},
            'membership_edges':{'tp':membership_tp,'pred':pcount,'gold':gcount,'f1':f1(membership_tp,pcount,gcount)},
            'canonical_whole_graph_exact':bool(canonical_exact),
            'branch_behavior_equivalent':equivalent,'inventory_exact_for_behavior_check':inventory_exact,
            'role_set_tp':rtp,'role_set_gold':rgold,'role_set_recall':rtp/rgold if rgold else 1.,
            'unit_f1':f1(len(p_units&g_units),len(p_units),len(g_units)),
            'gold_native_inferred_or_unresolved_leaves':sum(n['kind']=='leaf' and n['support']['kind']!='literal' for n in gold['nodes']),
            'fallback_used':False}


METRICS={'node_span_F1':lambda r:r['node_span']['f1'],
         'typed_content_F1':lambda r:r['typed_content']['f1'],
         'parent_scope_edge_F1':lambda r:r['parent_edges']['f1'],
         'membership_edge_F1':lambda r:r['membership_edges']['f1'],
         'whole_graph_exact':lambda r:float(r['canonical_whole_graph_exact']),
         'branch_behavior_proved_rate':lambda r:float(r['branch_behavior_equivalent'] is True),
         'valid_rate':lambda r:float(r['valid']),
         'role_set_recall':lambda r:r['role_set_recall'],'unit_F1':lambda r:r['unit_f1']}


def aggregate(rows,bootstrap=1000):
    if not rows:raise ValueError('No evaluation records')
    groups=defaultdict(list)
    for r in rows:groups[r['family_id']].append(r)
    result={'sources':len(rows),'families':len(groups),'missing_or_invalid':sum(not r['valid'] for r in rows),
            'behavior_check_unknown':sum(r['branch_behavior_equivalent'] is None for r in rows),'metrics':{}}
    rng=np.random.default_rng(45)
    indices=rng.integers(0,len(groups),size=(bootstrap,len(groups)))
    for name,fn in METRICS.items():
        values=[fn(r) for r in rows];family=np.asarray([np.mean([fn(r) for r in g]) for g in groups.values()])
        draws=family[indices].mean(1)
        result['metrics'][name]={'source_macro':float(np.mean(values)),'family_macro':float(family.mean()),
                                 'family_bootstrap_95':[float(np.quantile(draws,.025)),float(np.quantile(draws,.975))]}
    result['interval_note']='DEV diagnostic, fixed seed45 family resampling; not confirmatory TEST evidence'
    return result


def paired_comparison(left,right,bootstrap=1000):
    if {r['item_id'] for r in left}!={r['item_id'] for r in right}:raise ValueError('Comparison denominators differ')
    right={r['item_id']:r for r in right};groups=defaultdict(list)
    for r in left:groups[r['family_id']].append(r)
    result={};rng=np.random.default_rng(45);indices=rng.integers(0,len(groups),size=(bootstrap,len(groups)))
    for name,fn in METRICS.items():
        delta=np.asarray([np.mean([fn(r)-fn(right[r['item_id']]) for r in g]) for g in groups.values()])
        draws=delta[indices].mean(1)
        result[name]={'family_macro_delta':float(delta.mean()),'family_bootstrap_95':[float(np.quantile(draws,.025)),float(np.quantile(draws,.975))]}
    return result
