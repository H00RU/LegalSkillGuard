"""Learned local graph parser and same-capacity scope interaction heads."""
from copy import deepcopy
import math

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from .composition_data import branch_of, node_text, valid_graph
from .projection import unit_span
from .semantic_witness import assignments, evaluate, square_candidates

NODE_KINDS=('branch','leaf','AND','OR')


def center(values):
    table=values.reshape(2,2)
    return (table-table.mean(0,keepdim=True)-table.mean(1,keepdim=True)+table.mean()).flatten()


class Composer(nn.Module):
    def __init__(self,dimension=256,ancestor_depth=3):
        super().__init__();self.dimension=dimension;self.ancestor_depth=ancestor_depth
        self.node_projection=nn.Linear(dimension,dimension)
        self.kind_embedding=nn.Embedding(len(NODE_KINDS),dimension)
        self.edge_features=nn.Sequential(nn.Linear(3*dimension+6,dimension),nn.GELU())
        self.parent_score=nn.Linear(dimension,1);self.membership_score=nn.Linear(dimension,1)
        self.context=nn.Sequential(nn.Linear(3*dimension,dimension),nn.GELU())
        self.joint=nn.Sequential(nn.Linear(5*dimension,dimension),nn.GELU(),nn.Linear(dimension,1))

    def prepare(self,graph,cache):
        device=next(self.parameters()).device
        texts=[node_text(n) for n in graph['nodes']];cache.encode(texts+[graph['source']])
        if not texts:raise ValueError('No acquired local nodes')
        vectors=torch.stack([cache.mean(t) for t in texts]).to(device)
        kinds=torch.tensor([NODE_KINDS.index(n['kind']) for n in graph['nodes']],device=device)
        nodes=self.node_projection(vectors)+self.kind_embedding(kinds)
        source=cache.mean(graph['source']).to(device)
        n=len(nodes);left=nodes[:,None,:].expand(n,n,-1);right=nodes[None,:,:].expand(n,n,-1)
        positions=torch.zeros(n,n,6,device=device)
        for i,child in enumerate(graph['nodes']):
            a=child['support']['candidates'];apos=a[0][0]/max(len(graph['source']),1) if len(a)==1 else 0
            for j,parent in enumerate(graph['nodes']):
                b=parent['support']['candidates'];bpos=b[0][0]/max(len(graph['source']),1) if len(b)==1 else 0
                positions[i,j]=torch.tensor([float(child['unit']==parent['unit']),float(len(a)==1),float(len(b)==1),apos-bpos,float(child['kind']=='leaf'),float(parent['kind']=='branch')],device=device)
        edges=self.edge_features(torch.cat([left,right,source.expand(n,n,-1),positions],-1))
        pointer=self.parent_score(edges).squeeze(-1);membership=self.membership_score(edges).squeeze(-1)
        allowed=torch.tensor([[i!=j and p['kind'] in ('branch','AND','OR') for j,p in enumerate(graph['nodes'])] for i in range(n)],device=device)
        pointer=pointer.masked_fill(~allowed,-1e9)
        return {'nodes':nodes,'source':source,'edges':edges,'pointer':pointer,'membership':membership}

    def graph_loss(self,graph,prepared):
        nodes=graph['nodes'];children=[i for i,n in enumerate(nodes) if n['kind']!='branch']
        branches=[i for i,n in enumerate(nodes) if n['kind']=='branch'];device=prepared['pointer'].device
        if not children:return prepared['nodes'].sum()*0
        labels=torch.tensor([graph['parents'][i] for i in children],device=device)
        parent_loss=F.cross_entropy(prepared['pointer'][children],labels)
        membership=torch.stack([prepared['membership'][i,branches] for i in children])
        targets=torch.tensor([branches.index(branch_of(graph,i)) for i in children],device=device)
        return parent_loss+F.cross_entropy(membership,targets)

    def local_score(self,graph,prepared,indices=None):
        indices=[i for i,n in enumerate(graph['nodes']) if n['kind']!='branch'] if indices is None else indices
        if not indices:return prepared['nodes'].sum()*0
        return torch.stack([prepared['pointer'][i,graph['parents'][i]]+
                            prepared['membership'][i,branch_of(graph,i)] for i in indices]).sum()

    def square_energy(self,graph,square,prepared,activation):
        """Cell-shared encoder: axis swaps/bit flips permute energies exactly.

        No candidate index, gold output, error or J enters this head.
        Double centering removes row/column (single-decision) components.
        """
        changed=sorted(set(square['pair_u']+square['pair_v']));branches=[i for i,n in enumerate(graph['nodes']) if n['kind']=='branch']
        features=[]
        for cell,parents in enumerate(square['parents']):
            edge_vectors=[];contexts=[]
            for i in changed:
                p=parents[i];edge_vectors.append(prepared['edges'][i,p]);chain=[];a=p
                for _ in range(self.ancestor_depth):
                    if a<0:break
                    chain.append(prepared['nodes'][a]);a=parents[a]
                ancestor=torch.stack(chain).mean(0) if chain else torch.zeros_like(prepared['source'])
                contexts.append(self.context(torch.cat([prepared['nodes'][i],prepared['nodes'][p],ancestor])))
            edge_mean=torch.stack(edge_vectors).mean(0)
            context_mean=torch.stack(contexts).mean(0)
            frequencies=torch.as_tensor(np.asarray(activation[cell],dtype=np.float32).mean(0),device=edge_mean.device)
            behavior=(prepared['nodes'][branches]*frequencies[:,None]).mean(0) if branches else torch.zeros_like(edge_mean)
            features.append(torch.cat([prepared['source'],edge_mean,context_mean,behavior]))
        features=torch.stack(features)
        joint_context=features[:,self.dimension:2*self.dimension].mean(0).expand(4,-1)
        raw=self.joint(torch.cat([features,joint_context],-1)).squeeze(-1)
        return center(raw)

    def semantic_loss(self,graph,squares,prepared,mode):
        if not squares:return prepared['nodes'].sum()*0,{'squares':0,'witnessed_squares':0}
        terms=[];critical_terms=[];equiv_terms=[];directed_terms=[];observed=0
        # Reference scores are supplied separately to avoid encoding labels.
        for ordinal,square in enumerate(squares):
            if not square['negative']:continue
            observed+=1
            q=self.square_energy(graph,square,prepared,square['activation'])
            indices=sorted(set(square['pair_u']+square['pair_v']))
            local=torch.stack([self.local_score({**graph,'parents':p},prepared,indices) for p in square['parents']])
            scores=local+q
            p=square['equivalent'];n=square['negative']
            if not p:raise ValueError('TRAIN square lost its gold reference')
            if mode=='contrast':
                ref=torch.tensor(square['reference_scores'],device=scores.device)
                reward=.1*(scores-ref)
                term=torch.logsumexp(reward[p+n],0)-torch.logsumexp(reward[p],0)
                terms.append(term)
            else:
                critical=torch.relu(1+scores[n]-scores[p].max()).mean()
                equivalent=(scores[p]-scores[p].mean()).square().mean()
                errors=torch.tensor(square['mean_errors'],device=scores.device)
                interaction=F.mse_loss(q,center(-errors))
                terms.append(.5*critical+.1*equivalent+interaction)
                critical_terms.append(critical.detach());equiv_terms.append(equivalent.detach());directed_terms.append(interaction.detach())
        result=torch.stack(terms).mean() if terms else prepared['nodes'].sum()*0
        return result,{'squares':len(squares),'witnessed_squares':observed,
                       'critical':float(torch.stack(critical_terms).mean()) if critical_terms else None,
                       'equivalence':float(torch.stack(equiv_terms).mean()) if equiv_terms else None,
                       'interaction':float(torch.stack(directed_terms).mean()) if directed_terms else None}


def _partial_valid(nodes,parents,index,parent):
    if parent==index:return False
    if nodes[parent]['kind']=='branch' and any(p==parent for p in parents):return False
    seen={index};j=parent
    while j>=0:
        if j in seen:return False
        seen.add(j);j=parents[j]
    return True


@torch.inference_mode()
def decode(model,graph,cache,beam_size=8,interactions=False,maximum_squares=16,witness_limit=64):
    model.eval();prepared=model.prepare(graph,cache);nodes=graph['nodes'];n=len(nodes)
    roots=[i for i,node in enumerate(nodes) if node['kind']=='branch']
    if not roots:raise ValueError('No acquired branch; no default graph')
    parents=[-1 if node['kind']=='branch' else -2 for node in nodes]
    order=[i for i,node in enumerate(nodes) if node['kind'] in ('AND','OR')]+[i for i,node in enumerate(nodes) if node['kind']=='leaf']
    choices=[i for i,node in enumerate(nodes) if node['kind'] in ('branch','AND','OR')]
    beams=[(0.,parents)];pointer=prepared['pointer'].cpu().numpy()
    for i in order:
        expanded=[]
        for score,p in beams:
            for j in choices:
                if not _partial_valid(nodes,p,i,j):continue
                candidate=list(p);candidate[i]=j;expanded.append((score+float(pointer[i,j]),candidate))
        beams=sorted(expanded,key=lambda x:x[0],reverse=True)[:beam_size]
        if not beams:raise ValueError('Beam cannot retain every local node in a legal forest')
    candidates=[{**graph,'parents':p} for _,p in beams if valid_graph({**graph,'parents':p})]
    if not candidates:raise ValueError('No complete legal forest')
    # Interaction candidates use only the learned beam and its legal swaps;
    # neither gold relations nor gold directions are available here.
    squares=[]
    if interactions:
        keys,values,_=assignments(candidates[0],witness_limit)
        squares=square_candidates(candidates[0],maximum_squares)
        for square in squares:
            activation=[evaluate({**graph,'parents':p},keys,values).tolist() for p in square['parents']]
            square['energy']=model.square_energy(graph,square,prepared,activation).cpu().tolist()
            candidates.extend({**graph,'parents':p} for p in square['parents'])
    unique={tuple(g['parents']):g for g in candidates};scores={}
    for signature,g in unique.items():scores[signature]=float(model.local_score(g,prepared))
    energy_counts={};energy_sums={}
    for square in squares:
        for p,q in zip(square['parents'],square['energy']):
            signature=tuple(p);energy_counts[signature]=energy_counts.get(signature,0)+1
            energy_sums[signature]=energy_sums.get(signature,0)+q
    for signature,total in energy_sums.items():scores[signature]+=total/energy_counts[signature]
    selected=max(scores,key=scores.get)
    return unique[selected],{'beam_forests':len(beams),'scored_forests':len(unique),'interaction_squares':len(squares),'score':scores[selected]}
