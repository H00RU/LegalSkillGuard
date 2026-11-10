"""Frozen Qwen3 contextual features, with label-free shared caching.

The random projection is fixed at seed45; it is not fitted to any gold or DEV
metric. Cached token features permit the M1 slot-to-new-text attention head.
Encoder forwards are separately accounted from physical generation requests.
"""
from contextlib import nullcontext
from pathlib import Path
import hashlib
import json
import math
import time

import torch
from safetensors.torch import load_file, save_file


def key(text):return hashlib.sha256(text.encode()).hexdigest()


class FeatureCache:
    def __init__(self,path,model=None,tokenizer=None,dimension=256,seed=45):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.data=load_file(str(path)) if self.path.exists() else {}
        self.model=model;self.tokenizer=tokenizer;self.dimension=dimension;self.seed=seed
        self.events=[];self.projector=None

    def attach(self,model,tokenizer):self.model=model;self.tokenizer=tokenizer

    def has(self,text,tokens=False):return ('t_' if tokens else 'm_')+key(text) in self.data

    def encode(self,texts,token_texts=()):
        texts=list(dict.fromkeys(texts));need_tokens=set(token_texts)
        missing=[s for s in texts if not self.has(s) or (s in need_tokens and not self.has(s,True))]
        if not missing:return
        if self.model is None:raise ValueError('Missing frozen feature, no base encoder attached')
        if self.projector is None:
            generator=torch.Generator().manual_seed(self.seed)
            self.projector=(torch.randn(self.model.config.hidden_size,self.dimension,generator=generator)/math.sqrt(self.model.config.hidden_size)).to('cuda',dtype=torch.bfloat16)
        model=self.model;training=model.training;model.eval();started=time.monotonic();total_tokens=0;batches=0
        # Sort by length, batch under a conservative token budget; no truncation.
        missing.sort(key=len);groups=[];current=[];cost=0
        for s in missing:
            length=len(self.tokenizer.encode(s,add_special_tokens=False)) or 1
            if length>32768:raise ValueError('Frozen encoder context exceeds locked maximum')
            if current and (len(current)>=8 or max(cost,length)*(len(current)+1)>8192):groups.append(current);current=[];cost=0
            current.append(s);cost=max(cost,length)
        if current:groups.append(current)
        adapter_context=model.disable_adapter() if hasattr(model,'disable_adapter') else nullcontext()
        with adapter_context,torch.inference_mode():
            base=model.get_base_model() if hasattr(model,'get_base_model') else model
            for group in groups:
                batch=self.tokenizer([s or ' ' for s in group],return_tensors='pt',padding=True,add_special_tokens=False).to('cuda')
                outputs=base.model(**batch,use_cache=False,return_dict=True)
                hidden=outputs.last_hidden_state@self.projector
                for i,text in enumerate(group):
                    selected=hidden[i,batch['attention_mask'][i].bool()].float().cpu()
                    if not len(selected):raise ValueError('Empty encoder token sequence')
                    self.data['m_'+key(text)]=selected.mean(0).to(torch.float16).contiguous()
                    if text in need_tokens:self.data['t_'+key(text)]=selected.to(torch.float16).contiguous()
                total_tokens+=int(batch['attention_mask'].sum());batches+=1
                del outputs,hidden,batch
        if training:model.train()
        self.events.append({'kind':'frozen_base_encoder','strings':len(missing),'forward_batches':batches,
                            'input_tokens':total_tokens,'seconds':time.monotonic()-started,'physical_generations':0})

    def mean(self,text):return self.data['m_'+key(text)].float()
    def tokens(self,text):return self.data['t_'+key(text)].float()

    def save(self):
        temporary=self.path.with_suffix('.temporary.safetensors')
        save_file({k:v.contiguous() for k,v in self.data.items()},str(temporary))
        temporary.replace(self.path)
        if self.events:
            with self.path.with_suffix('.encoder_events.jsonl').open('a') as f:
                for event in self.events:f.write(json.dumps(event)+'\n')
            self.events=[]
