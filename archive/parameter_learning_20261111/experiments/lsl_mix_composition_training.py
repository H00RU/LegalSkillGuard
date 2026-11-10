"""Shared composition initialization and fixed three-epoch objective arms.

NormBench's checked native square cache is reused only after exact node/source
binding. Other datasets use actual native predictions and label losses.
"""
from pathlib import Path
import argparse
from collections import Counter
from copy import deepcopy
import json
import os
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.projection import compact
from legal_skill_guard.lsl.native_training import target
from legal_skill_guard.lsl.native_semantics import horn_scope_squares,predict,norm_result
from legal_skill_guard.lsl.horn_codec import normalize as normalize_horn
from legal_skill_guard.lsl.composition_data import gold_graph,canonical_graph
from legal_skill_guard.lsl.native_composition import NativeComposer,objective,feature_texts
from legal_skill_guard.lsl.features import FeatureCache
from experiments.lsl_mix_native_initialization import append,BASE_MODEL


def prepare(out,bank):
    records={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']=='train'}
    local={t['source']:t for t in load_json(bank/'local/tables.json')}
    old=load_json(ROOT/'artifacts/lsl_first_empirical_20261110/dataset.json')
    old_graphs={g['item_id']:g for g in old['train_graphs']};examples=[];counts=Counter()
    for key,r in records.items():
        d=r['dataset'];squares=[]
        if d=='NormBench':
            g=gold_graph(r['native_record']);previous=old_graphs[g['item_id']]
            if any(g[k]!=previous[k] for k in ('nodes','parents','source')):raise ValueError('Native graph binding differs from old square cache: '+key)
            canonical=canonical_graph(g)
            for s in old['train_squares'][g['item_id']]:
                gs=[{**g,'parents':p} for p in s['parents']]
                squares.append({'cells':gs,'mean_errors':s['mean_errors'],
                    'predictions':s['activation'],'positive_cells':s['equivalent'],
                    'native_structure_cells':[i for i,c in enumerate(gs) if canonical_graph(c)==canonical],
                    'reused_native_square':True,'cache_graph_source':g['item_id']})
            counts['reused_norm_sources']+=1
        elif d=='ProofWriter_OWA_depth5':
            gold=normalize_horn(r['grade']['horn'])
            for s in horn_scope_squares(gold,key):
                ex=[predict(r,c) for c in s['cells']]
                if not all(e['valid'] for e in ex):continue
                squares.append({**s,'mean_errors':[int(e['answer']!=r['grade']['answer']) for e in ex],
                    'predictions':[e['answer'] for e in ex],
                    'native_structure_cells':[i for i,c in enumerate(s['cells']) if c['program']==gold]})
        elif d in ('SARA_v2_Binary','RuleArena_Airline'):
            squares=local[key].get('squares',[])
        # ContractNLI has native acquisition/evidence updates, no invented
        # directed interaction annotation. It remains in the source denominator.
        examples.append({'source':key,'dataset':d,'squares':squares})
        counts[d+':sources']+=1;counts[d+':squares']+=len(squares)
        for s in squares:
            a,b,c,e=s['mean_errors'];counts[d+':nonzero_interaction']+=int(abs(e-c-b+a)>1e-12)
    location=bank/'composition';location.mkdir(exist_ok=True)
    write_json(location/'examples.json',examples)
    write_json(location/'preparation.json',{'counts':dict(counts),'TRAIN_sources':256,'TEST':False,
        'old_cache_sha256':sha(ROOT/'artifacts/lsl_first_empirical_20261110/dataset.json'),
        'local_tables_sha256':sha(bank/'local/tables.json'),'examples_sha256':sha(location/'examples.json'),
        'old_out_of_manifest_sources_used':0,'finite_proof_repetition':False})
    print(json.dumps(dict(counts),ensure_ascii=False),flush=True)


def encode(out,bank):
    import torch
    from transformers import AutoTokenizer,AutoModelForCausalLM
    from peft import PeftModel
    rows={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']=='train'}
    examples=load_json(bank/'composition/examples.json');texts=[]
    for e in examples:
        cells=[c for s in e['squares'] for c in s['cells']]
        if cells:texts.extend(feature_texts(rows[e['source']],cells))
    cache=FeatureCache(out/'composition_base_features.safetensors');texts=list(dict.fromkeys(texts))
    missing=[t for t in texts if not cache.has(t)]
    if missing:
        torch.set_num_threads(4)
        tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,local_files_only=True)
        base=AutoModelForCausalLM.from_pretrained(BASE_MODEL,torch_dtype=torch.bfloat16,local_files_only=True,
            attn_implementation='sdpa',low_cpu_mem_usage=True).to('cuda')
        cache.attach(base,tokenizer);cache.encode(missing);cache.save()
    snapshot=bank/'composition/features.safetensors'
    if snapshot.exists():
        if sha(snapshot)!=sha(cache.path):raise ValueError('Preserve the existing feature snapshot; use a revised preparation path')
    else:os.link(cache.path,snapshot)
    write_json(bank/'composition/encoding.json',{'strings':len(texts),'new_strings':len(missing),
        'feature_cache_sha256':sha(cache.path),'encoder':'unchanged frozen original Qwen3-8B, fixed seed45 projection256',
        'physical_generations':0,'TEST':False})


def train(out,bank,epoch,mode):
    import torch
    torch.set_num_threads(4);random.seed(45);torch.manual_seed(45)
    rows={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']=='train'}
    examples=load_json(bank/'composition/examples.json');cache=FeatureCache(bank/'composition/features.safetensors')
    if len(examples)!=256 or {e['source'] for e in examples}!=set(rows):raise ValueError('Composer TRAIN source coverage differs')
    root=out/'composition';root.mkdir(exist_ok=True)
    destination=root/'common_initialization' if epoch==0 else root/mode/('epoch%d'%epoch)
    destination.mkdir(parents=True,exist_ok=True)
    if (destination/'complete.json').exists():print('Composer stage already complete');return
    code=['experiments/lsl_mix_composition_training.py','legal_skill_guard/lsl/native_composition.py','legal_skill_guard/lsl/features.py','legal_skill_guard/lsl/native_semantics.py','legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/rr/public_horn.py']
    cfg={'epoch':epoch,'mode':mode,'seed':45,'hidden':256,'ancestor_context':3,'learning_rate':.001,
         'weight_decay':.01,'source_accumulation':8,'sources':256,'examples_sha256':sha(bank/'composition/examples.json'),
         'base_feature_sha256':sha(bank/'composition/features.safetensors'),
         'code':{f:sha(ROOT/f) for f in code},'common_phase':'complete the native initialization of the previously uninitialized lightweight head; no extra Qwen weight update',
         'same_common_reference_and_capacity':True,'TEST':False}
    if (destination/'config.json').exists() and load_json(destination/'config.json')!=cfg:raise ValueError('Composer stage binding changed')
    write_json(destination/'config.json',cfg)
    model=NativeComposer();optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    if epoch>0:
        previous=root/'common_initialization'/'model.pt' if epoch==1 else root/mode/('epoch%d'%(epoch-1))/'model.pt'
        state=torch.load(previous,map_location='cpu',weights_only=False);model.load_state_dict(state['model'])
        if epoch>1:optimizer.load_state_dict(state['optimizer'])
    reference=None
    if mode=='contrast' and epoch>0:
        reference=NativeComposer().eval();reference.load_state_dict(torch.load(root/'common_initialization/model.pt',map_location='cpu',weights_only=False)['model'])
        for p in reference.parameters():p.requires_grad_(False)
    order=sorted(examples,key=lambda e:e['source']);rng=random.Random(45)
    for _ in range(max(1,epoch)):rng.shuffle(order)
    model.train();optimizer.zero_grad(set_to_none=True);started=time.monotonic();dataset_updates=Counter();coverage=Counter()
    for i,e in enumerate(order):
        probe=model.joint[-1].weight;old_probe=probe.grad.detach().clone() if probe.grad is not None else None
        supervised=e['squares'] if epoch>0 else [s for s in e['squares'] if s.get('native_structure_cells')]
        loss,stats=objective(model,rows[e['source']],supervised,cache,'ordinary' if epoch==0 else mode,reference)
        if not bool(torch.isfinite(loss)):raise ValueError('Non-finite native composer objective')
        (loss/8).backward();coverage.update({e['dataset']+':'+k:v for k,v in stats.items()})
        delta=probe.grad.detach()-(old_probe if old_probe is not None else 0) if probe.grad is not None else None
        qnorm=float(delta.norm()) if delta is not None else 0.
        append(destination/'source_updates.jsonl',{'source':e['source'],'dataset':e['dataset'],'loss':float(loss.detach()),**stats,'joint_head_source_gradient_l2':qnorm,'position':i,'physical_generations':0})
        if (i+1)%8==0:
            gradient=float(torch.nn.utils.clip_grad_norm_(model.parameters(),1.));optimizer.step();optimizer.zero_grad(set_to_none=True)
            append(destination/'optimizer_steps.jsonl',{'step':(i+1)//8,'gradient_norm':gradient,'elapsed_seconds':time.monotonic()-started})
    torch.save({'model':model.state_dict(),'optimizer':optimizer.state_dict(),'config':cfg},destination/'model.temporary.pt')
    (destination/'model.temporary.pt').replace(destination/'model.pt')
    write_json(destination/'complete.json',{'sources':256,'optimizer_steps':32,'seconds':time.monotonic()-started,
        'coverage':dict(coverage),'checkpoint_sha256':sha(destination/'model.pt'),'common_LoRA_restarted':False,'goal_complete':False})
    print(json.dumps({'composer':mode,'epoch':epoch,'seconds':time.monotonic()-started,'coverage':dict(coverage)},ensure_ascii=False),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');p.add_argument('--bank',required=True)
    p.add_argument('--prepare',action='store_true');p.add_argument('--encode',action='store_true');p.add_argument('--train',action='store_true')
    p.add_argument('--epoch',type=int,default=0);p.add_argument('--mode',choices=('ordinary','directed','contrast'),default='ordinary');a=p.parse_args()
    out=(ROOT/a.out).resolve();bank=Path(a.bank).resolve()
    if a.prepare:prepare(out,bank)
    if a.encode:encode(out,bank)
    if a.train:train(out,bank,a.epoch,a.mode)
