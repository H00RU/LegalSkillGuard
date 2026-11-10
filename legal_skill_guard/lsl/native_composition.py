"""Shared native-forest scoring and directed four-cell interaction head.

Serialization adapters supply only acquired records and their connections.
The same nonlinear edge encoder and centered head serve every dataset; native
labels/errors are accepted exclusively by the training objective.
"""
import ast
from copy import deepcopy
import json

import torch
from torch import nn
from torch.nn import functional as F

from .composition import center
from .composition_data import node_text,valid_graph
from .native_semantics import norm_graph,decode_horn,predict
from .projection import compact
from .safe_program import validate,assignments


def source_text(record):return compact({'dataset':record['dataset'],'public':record['public']})


def edges(record,cell):
    """(content, immediate parent, up to three ancestor contexts)."""
    d=record['dataset'];out=[]
    if d=='NormBench':
        g=cell;valid_graph(g,raise_error=True)
        for i,n in enumerate(g['nodes']):
            p=g['parents'][i]
            if p<0:continue
            chain=[];a=p
            for _ in range(3):
                if a<0:break
                chain.append(node_text(g['nodes'][a]));a=g['parents'][a]
            out.append((node_text(n),node_text(g['nodes'][p]),compact(chain)))
    elif d=='ProofWriter_OWA_depth5':
        decode_horn(cell['program']);p=cell['program']
        for rule in p['rules']:
            head=compact(rule['head'])
            for atom in rule['body']:out.append((compact(atom),'RULE_HEAD '+head,'Horn implication AND -> '+head))
        # Fixed facts/query do not change across scope cells.
    elif d in ('SARA_v2_Binary','RuleArena_Airline'):
        tree=validate(cell['program']);bindings={n.targets[0].id:ast.unparse(n) for n in assignments(tree)}
        def visit(node,chain=(),inside_assignment=False):
            closed=inside_assignment or isinstance(node,(ast.Assign,ast.AnnAssign,ast.AugAssign))
            for field,value in ast.iter_fields(node):
                children=list(enumerate(value)) if isinstance(value,list) else [(None,value)]
                for index,child in children:
                    if not isinstance(child,ast.AST):continue
                    parent=type(node).__name__+':'+field+':'+str(index)
                    ancestry=(chain+(parent,))[-3:]
                    if isinstance(child,ast.Name) and isinstance(child.ctx,ast.Load) and not closed and field!='func':
                        out.append((bindings.get(child.id,child.id),parent,compact(ancestry)))
                    visit(child,ancestry,closed)
        visit(tree)
    elif d=='ContractNLI':
        # Evidence attachment is a representation/readout path, not an oracle
        # or a gold interaction target. No fabricated normative conditions.
        native=predict(record,cell)
        for key,label in native['answer'].items():
            for i in native['evidence'][key]:out.append((record['public']['document'][slice(*record['public']['sentence_spans'][i])],record['public']['queries'][key],label))
    else:raise ValueError(d)
    return out


def feature_texts(record,cells):
    strings=[source_text(record)]
    for c in cells:
        for edge in edges(record,c):strings.extend(edge)
        if record['dataset']=='NormBench':
            strings.extend(node_text(n) for n in c['nodes'] if n['kind']=='branch')
        elif record['dataset']!='ContractNLI':
            execution=predict(record,c)
            if not execution['valid']:raise ValueError('Cannot encode an invalid candidate as a semantic result')
            strings.append('native predicted result '+compact(execution['answer']))
    return strings


class NativeComposer(nn.Module):
    def __init__(self,dimension=256):
        super().__init__();self.dimension=dimension
        self.edge=nn.Sequential(nn.Linear(4*dimension,dimension),nn.GELU())
        self.local=nn.Linear(dimension,1)
        self.joint=nn.Sequential(nn.Linear(5*dimension,dimension),nn.GELU(),nn.Linear(dimension,1))

    def encode(self,record,cell,cache):
        device=next(self.parameters()).device;source=cache.mean(source_text(record)).to(device)
        es=edges(record,cell)
        if not es:return source,source.new_zeros((0,self.dimension)),source.new_zeros(self.dimension)
        child=torch.stack([cache.mean(e[0]) for e in es]).to(device)
        parent=torch.stack([cache.mean(e[1]) for e in es]).to(device)
        ancestor=torch.stack([cache.mean(e[2]) for e in es]).to(device)
        encoded=self.edge(torch.cat([source.expand(len(es),-1),child,parent,ancestor],-1))
        return source,encoded,ancestor.mean(0)

    def square(self,record,cells,cache,interactions=True,behaviors=None):
        encoded=[self.encode(record,c,cache) for c in cells]
        local=torch.stack([self.local(e).sum() if len(e) else s.sum()*0 for s,e,a in encoded])
        if not interactions:return local,local*0
        if len(cells)!=4:raise ValueError('Exactly four legal cells required for interaction')
        means=torch.stack([e.mean(0) if len(e) else s*0 for s,e,a in encoded]);common=means.mean(0)
        behavior_vectors=[]
        if record['dataset']=='NormBench':
            import numpy as np
            from .semantic_witness import assignments,evaluate
            graphs=cells
            if behaviors is None:
                keys,values,_=assignments(graphs[0],64)
                behaviors=[evaluate(g,keys,values).tolist() for g in graphs]
            for g,b,(source,e,a) in zip(graphs,behaviors,encoded):
                heads=[n for n in g['nodes'] if n['kind']=='branch']
                if not heads:behavior_vectors.append(source*0);continue
                branch_vectors=torch.stack([cache.mean(node_text(n)) for n in heads]).to(source.device)
                frequencies=torch.tensor(np.asarray(b,dtype='float32').mean(0),device=source.device)
                behavior_vectors.append((branch_vectors*frequencies[:,None]).mean(0))
        else:
            if behaviors is None:behaviors=[predict(record,c)['answer'] for c in cells]
            behavior_vectors=[cache.mean('native predicted result '+compact(b)).to(means.device) for b in behaviors]
        # Each cell uses the identical encoder; the common summary is invariant
        # to row/column permutations. Double centering removes unary effects.
        raw=torch.stack([self.joint(torch.cat([s,m,a,b,common])).squeeze(-1) for (s,e,a),m,b in zip(encoded,means,behavior_vectors)])
        q=center(raw)
        return local,q


def objective(model,record,squares,cache,mode,reference=None):
    terms=[];stats={'squares':0,'nonzero_interaction':0,'directed_terms':0,'contrast_terms':0}
    for square in squares:
        cells=square['cells'];local,q=model.square(record,cells,cache,interactions=mode!='ordinary',behaviors=square.get('predictions'))
        errors=torch.tensor(square['mean_errors'],dtype=local.dtype,device=local.device)
        positive=errors==0;negative=errors>0;native_indices=square.get('native_structure_cells')
        if 'positive_cells' in square:
            positive=torch.tensor([i in square['positive_cells'] for i in range(4)],device=local.device)
        term=local.sum()*0
        if native_indices:
            term=term+torch.logsumexp(local,0)-torch.logsumexp(local[native_indices],0)
        elif bool(positive.any()):term=term+torch.logsumexp(local,0)-torch.logsumexp(local[positive],0)
        if mode=='directed':
            scores=local+q;target=center(-errors)
            term=term+F.mse_loss(q,target);stats['directed_terms']+=1
            if bool(positive.any()) and bool(negative.any()):
                term=term+.5*torch.relu(1+scores[negative]-scores[positive].max()).mean()+.1*(scores[positive]-scores[positive].mean()).square().mean()
        elif mode=='contrast' and bool(positive.any()) and bool(negative.any()):
            if reference is None:raise ValueError('SQLoom needs the frozen common composer reference')
            with torch.no_grad():r0,q0=reference.square(record,cells,cache,interactions=True,behaviors=square.get('predictions'))
            reward=.1*(local+q-r0-q0)
            term=term+torch.logsumexp(reward,0)-torch.logsumexp(reward[positive],0);stats['contrast_terms']+=1
        elif mode not in ('ordinary','contrast'):raise ValueError(mode)
        terms.append(term);stats['squares']+=1
        stats['nonzero_interaction']+=int(bool(center(-errors).abs().max()>0))
    if not terms:return next(model.parameters()).sum()*0,stats
    return torch.stack(terms).mean(),stats


@torch.inference_mode()
def select(model,record,primary,squares,cache,mode,beam_size=8):
    model.eval();pool={compact(primary):primary};local_scores={};interactions={}
    for square in squares:
        local,q=model.square(record,square['cells'],cache,interactions=mode!='ordinary',behaviors=square.get('predictions'))
        for c,l,j in zip(square['cells'],local,q):
            key=compact(c);pool[key]=c;local_scores[key]=float(l)
            if mode!='ordinary':interactions.setdefault(key,[]).append(float(j))
    if compact(primary) not in local_scores:
        local,_=model.square(record,[primary],cache,interactions=False);local_scores[compact(primary)]=float(local[0])
    beam=sorted(pool,key=lambda k:local_scores[k],reverse=True)[:beam_size]
    scores={k:local_scores[k]+(sum(interactions[k])/len(interactions[k]) if k in interactions else 0) for k in beam}
    best=max(scores,key=scores.get)
    return pool[best],{'candidates':len(pool),'beam_retained':len(beam),'beam_size':beam_size,'squares':len(squares),'mode':mode,'score':scores[best],'chosen_primary':best==compact(primary)}
