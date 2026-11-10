"""Shared-content acquisition heads and executable source-role updates.

M1 predicts role additions/retractions and signed source-view multiplicities.
The same-capacity Edit head rewrites complete role/view sets. Both receive the
same lexical representation, source exposure and previous state. Duplicate
native instances are retained, rather than collapsing (text,tag) to one leaf.
"""
from collections import Counter
from copy import deepcopy
import math

import torch
from torch import nn
from torch.nn import functional as F

from .projection import TAGS, canonical_inventory, view_counts


class RoleSetHead(nn.Module):
    def __init__(self,dimension=256,maximum_count=8):
        super().__init__();self.dimension=dimension;self.maximum_count=maximum_count
        self.query=nn.Linear(dimension,dimension);self.key=nn.Linear(dimension,dimension)
        self.state=nn.Linear(len(TAGS),32)
        self.combine=nn.Sequential(nn.Linear(3*dimension+32,dimension),nn.GELU())
        self.roles=nn.Linear(dimension,2*len(TAGS))
        self.counts=nn.Linear(dimension,len(TAGS)*(2*maximum_count+1))

    def forward(self,slot,source_tokens,unit,old_roles):
        attention=torch.softmax((self.query(slot)@self.key(source_tokens).T)/math.sqrt(self.dimension),dim=-1)
        context=attention@source_tokens
        hidden=self.combine(torch.cat([slot,context,unit,self.state(old_roles)],dim=-1))
        roles=self.roles(hidden).reshape(-1,2,len(TAGS))
        counts=self.counts(hidden).reshape(-1,len(TAGS),2*self.maximum_count+1)
        return roles,counts


def role_labels(system,prior,current,payloads,units,maximum_count):
    old=view_counts(prior);gold=view_counts(current);tag_index={tag:i for i,tag in enumerate(TAGS)}
    role_targets=[];counts=[];old_features=[];keys=[]
    for text in payloads:
        previous={tag for p,tag,_ in old if p==text};target={tag for p,tag,_ in gold if p==text}
        added=target-previous if system=='m1' else target
        removed=previous-target if system=='m1' else set()
        role_targets.append([[float(t in added) for t in TAGS],[float(t in removed) for t in TAGS]])
        for unit in units:
            before=[old[(text,t,unit)] for t in TAGS];after=[gold[(text,t,unit)] for t in TAGS]
            label=[a-b if system=='m1' else a for a,b in zip(after,before)]
            if any(abs(n)>maximum_count for n in label):raise ValueError('Unrepresentable TRAIN view count; do not clip labels')
            counts.append([n+maximum_count for n in label]);old_features.append(before);keys.append((text,unit))
    return role_targets,counts,old_features,keys


def role_forward(head,cache,system,prior,current,new_source,*,supervised=True):
    """The labels never enter head features. Current supplies content/unit labels
    under teacher forcing, or generated content/units during inference.
    """
    device=next(head.parameters()).device;payloads=current['p'];units=current['u']
    if not payloads:return None
    cache.encode(payloads+units+[new_source],token_texts=[new_source])
    slot=torch.stack([cache.mean(p) for p in payloads]).to(device)
    source=cache.tokens(new_source).to(device)
    old=view_counts(prior)
    old_sets=torch.tensor([[float(any(p==text and t==tag for p,t,u in old)) for tag in TAGS] for text in payloads],device=device)
    global_logits,_=head(slot,source,torch.zeros_like(slot),old_sets)
    count_logits=None;keys=[]
    if units:
        pair_slots=slot.repeat_interleave(len(units),dim=0)
        unit_embeddings=torch.stack([cache.mean(u) for u in units]).to(device).repeat(len(payloads),1)
        old_counts=torch.tensor([[old[(p,t,u)] for t in TAGS] for p in payloads for u in units],device=device,dtype=torch.float32)
        _,count_logits=head(pair_slots,source,unit_embeddings,old_counts)
        keys=[(p,u) for p in payloads for u in units]
    output={'role_logits':global_logits,'count_logits':count_logits,'keys':keys}
    if supervised:
        rt,ct,_,_=role_labels(system,prior,current,payloads,units,head.maximum_count)
        role_loss=F.binary_cross_entropy_with_logits(global_logits,torch.tensor(rt,device=device))
        count_loss=F.cross_entropy(count_logits.flatten(0,1),torch.tensor(ct,device=device).flatten()) if keys else role_loss*0
        output.update(loss=role_loss+count_loss,role_loss=role_loss,count_loss=count_loss)
    return output


@torch.inference_mode()
def infer_views(head,cache,system,prior,current,new_source,source):
    head.eval();out=role_forward(head,cache,system,prior,current,new_source,supervised=False)
    if out is None:return current
    old=view_counts(prior);counts={};role_flags=out['role_logits'].sigmoid().cpu()>0.5
    if out['count_logits'] is not None:
        predictions=out['count_logits'].argmax(-1).cpu()-head.maximum_count
        payload_index={p:i for i,p in enumerate(current['p'])}
        for (p,u),values in zip(out['keys'],predictions.tolist()):
            pi=payload_index[p]
            for ti,(tag,value) in enumerate(zip(TAGS,values)):
                previous=old[(p,tag,u)] if system=='m1' else 0
                existing_any=any(pp==p and tt==tag for pp,tt,uu in old)
                if value>0 and not (system=='m1' and existing_any) and not role_flags[pi,0,ti]:value=0
                counts[(p,tag,u)]=max(0,previous+value)
    result=deepcopy(current);result['v']=[]
    for (p,t,u),n in counts.items():
        for _ in range(n):result['v'].append([result['p'].index(p),t,result['u'].index(u)])
    return canonical_inventory(result,source)
