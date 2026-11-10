"""Exact independent local likelihoods with one shared source prefix.

Branches can attend to the same source and their own earlier tokens only.
Rotary positions reset at each branch. Packing changes compute, not the
conditional distribution; an independent-forward regression checks this.
"""
import json
from .projection import compact


def tokenize_choices(record,blocks,tokenizer):
    messages=[{'role':'system','content':'Read the public source. For a subsequent local source quote, output only the requested acquired record as JSON, or null for omission. No reasoning.'},
              {'role':'user','content':'DATASET='+record['dataset']+'\nPUBLIC_INPUT='+compact(record['public'])}]
    prefix=tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=False,enable_thinking=False)
    branches=[];ids=list(prefix);positions=list(range(len(prefix)))
    for index,b in enumerate(blocks):
        if len(b.get('choices',[]))!=2:continue
        question='LOCAL_SOURCE_QUOTE='+b['quote']+'\nReturn this one local semantic record; do not output a complete program or an answer.'
        full=tokenizer.apply_chat_template(messages+[{'role':'user','content':question}],tokenize=True,add_generation_prompt=True,enable_thinking=False)
        if full[:len(prefix)]!=prefix:raise ValueError('Tokenizer does not preserve the common chat prefix')
        query=full[len(prefix):]
        for choice_index,choice in enumerate(b['choices']):
            response=tokenizer.encode(compact(choice),add_special_tokens=False)+[tokenizer.eos_token_id]
            start=len(ids);ids+=query+response
            positions+=list(range(len(prefix),len(prefix)+len(query)+len(response)))
            branches.append({'block':index,'choice':choice_index,'start':start,'end':len(ids),
                             'response_start':start+len(query),'response_ids':response})
    if len(ids)>32768:raise ValueError('Packed local source exceeds context; use independent branches, never truncate')
    return {'key':record['key'],'input_ids':ids,'position_ids':positions,'prefix_length':len(prefix),'branches':branches}


def attention_mask(row,device,dtype):
    import torch
    n=len(row['input_ids']);prefix=row['prefix_length']
    # A supplied four-dimensional additive mask is used unchanged by Qwen3.
    mask=torch.full((n,n),torch.finfo(dtype).min,device=device,dtype=dtype)
    mask[:prefix,:prefix]=torch.triu(torch.full((prefix,prefix),torch.finfo(dtype).min,device=device,dtype=dtype),diagonal=1)
    for branch in row['branches']:
        a,b=branch['start'],branch['end'];length=b-a
        mask[a:b,:prefix]=0
        mask[a:b,a:b]=torch.triu(torch.full((length,length),torch.finfo(dtype).min,device=device,dtype=dtype),diagonal=1)
    return mask[None,None]


def log_scores(model,row,*,chunk=64,raw=False):
    import torch
    from torch.nn import functional as F
    if not row['branches']:return {}
    base=model.get_base_model() if hasattr(model,'get_base_model') else model
    device=next(base.parameters()).device;dtype=next(base.parameters()).dtype
    ids=torch.tensor([row['input_ids']],device=device);pos=torch.tensor([row['position_ids']],device=device)
    mask=attention_mask(row,device,dtype)
    with torch.autocast(device.type,dtype=torch.bfloat16,enabled=device.type=='cuda'):
        hidden=base.model(input_ids=ids,position_ids=pos,attention_mask=mask,use_cache=False,return_dict=True).last_hidden_state[0]
        result={}
        for branch in row['branches']:
            start=branch['response_start']-1;response=branch['response_ids'];value=hidden.sum()*0
            for offset in range(0,len(response),chunk):
                n=min(chunk,len(response)-offset)
                logits=base.lm_head(hidden[start+offset:start+offset+n]).float()
                labels=torch.tensor(response[offset:offset+n],device=device)
                value=value-F.cross_entropy(logits,labels,reduction='sum')
            result.setdefault(branch['block'],{})[branch['choice']]=value
    return result if raw else {i:torch.stack([s[0],s[1]]) for i,s in result.items()}


def independent_row(row,branch):
    p=row['prefix_length'];a=branch['start'];b=branch['end']
    return {'input_ids':row['input_ids'][:p]+row['input_ids'][a:b],
            'position_ids':list(range(p+b-a)),'prefix_length':p,
            'branches':[{**branch,'start':p,'end':p+b-a,'response_start':p+branch['response_start']-a}]}
