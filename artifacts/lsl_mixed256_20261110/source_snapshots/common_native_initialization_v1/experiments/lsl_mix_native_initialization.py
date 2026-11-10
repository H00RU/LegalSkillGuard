"""One common native-supervision pass on fixed MIX256, with durable recovery.

This is the common foundation for all seven systems, not a method comparison.
TEST is never loaded. The first16 TRAIN sources provide the engineering smoke;
successful finite updates continue the same pass rather than restarting it.
"""
from pathlib import Path
import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import sqlite3
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from legal_skill_guard.lsl.data import load_json,sha,write_json
from legal_skill_guard.lsl.projection import compact
from legal_skill_guard.lsl.native_training import common_source_order,prompt,tokenize_record

BASE_MODEL='/media/sangfor/vdb/legal-skill-runtime/models/Qwen3-8B/b968826d9c46dd6066d109eabc6255188de91218'
RUN_ID='LSG-MIX256-common-native-init-v1'
BOUND=['experiments/lsl_mix_native_initialization.py','legal_skill_guard/lsl/native_training.py',
       'legal_skill_guard/lsl/projection.py','legal_skill_guard/lsl/data.py',
       'legal_skill_guard/rr/method_ledger.py','legal_skill_guard/rr/ledger.py','legal_skill_guard/rr/coverage.py']


def append(path,row):
    with Path(path).open('a') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n');f.flush();os.fsync(f.fileno())


def configuration(out):
    return {'run_id':RUN_ID,'protocol':'LSG-MIX256-20261110','base_model':BASE_MODEL,
        'thinking':False,'lora_rank':16,'lora_alpha':32,'lora_dropout':.05,
        'target_modules':['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'],
        'epochs':1,'stage':'common_native_initialization','seed':45,'precision':'bfloat16',
        'attention':'torch_sdpa','gradient_checkpointing':True,'micro_batch_sources':1,
        'gradient_accumulation_sources':8,'learning_rate':5e-5,'weight_decay':.01,
        'gradient_clip':1.,'max_context':32768,'label_logits_chunk':64,
        'source_loss_normalization':'native_task/structure/evidence means per source, ContractNLI query means',
        'fixed_order':'two of each dataset in first ten, then remaining seed45 shuffle; each of256 once',
        'native_smoke_sources_after_common_pass':5,
        'generation':{'temperature':.6,'top_p':.95,'top_k':20,'max_output_tokens':8192,'do_sample':True},
        'mixed_manifest_sha256':load_json(out/'manifest.json')['runtime_sha256'],
        'open_dataset_sha256':sha(out/'open_dataset.json'),
        'base_model_manifest_sha256':sha(ROOT/'artifacts/lsl_first_empirical_20261110/base_model_manifest.json'),
        'code_sha256':{p:sha(ROOT/p) for p in BOUND}}


def prepare(out):
    from transformers import AutoTokenizer
    records=load_json(out/'open_dataset.json')['records'];train=common_source_order(records)
    tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,local_files_only=True)
    tokenized=[tokenize_record(r,tokenizer) for r in train]
    write_json(out/'common_train_tokens.json',tokenized)
    cfg=configuration(out);cfg['tokenized_train_sha256']=sha(out/'common_train_tokens.json')
    write_json(out/'common_init_config.json',cfg)
    stats={}
    for d in {r['dataset'] for r in tokenized}:
        rows=[r for r in tokenized if r['dataset']==d]
        stats[d]={'sources':len(rows),'input_tokens':sum(len(r['input_ids']) for r in rows),
                  'supervised_response_tokens':sum(r['response_tokens'] for r in rows),
                  'maximum_sequence':max(len(r['input_ids']) for r in rows)}
    write_json(out/'native_tokenization_audit.json',{'counts':stats,'all_sources':len(tokenized),
                'truncated_sources':0,'TEST_loaded':False,'thinking':False})
    print(json.dumps({'prepared':True,'datasets':stats,'config_sha256':sha(out/'common_init_config.json')},ensure_ascii=False),flush=True)


def assert_binding(out,cfg):
    for p,h in cfg['code_sha256'].items():
        if sha(ROOT/p)!=h:raise ValueError('Live training code binding changed: '+p)
    if sha(out/'common_train_tokens.json')!=cfg['tokenized_train_sha256']:raise ValueError('Training tokens changed')


def save_checkpoint(model,optimizer,out,step,position,losses,cfg):
    import torch
    location=out/'common_native_initialization'/('step_%04d'%step)
    location.mkdir(parents=True,exist_ok=True);model.save_pretrained(location)
    temporary=location/'optimizer.temporary.pt'
    torch.save({'optimizer':optimizer.state_dict(),'step':step,'position':position,
                'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),
                'python_rng':random.getstate(),'losses':losses,'config_sha256':sha(out/'common_init_config.json')},temporary)
    temporary.replace(location/'optimizer.pt')
    write_json(out/'common_native_initialization'/'latest.json',{'checkpoint':str(location.relative_to(out)),
               'step':step,'position':position,'config_sha256':sha(out/'common_init_config.json')})
    return location


def weighted_loss(model,row,cfg):
    import torch
    from torch.nn import functional as F
    ids=torch.tensor([row['input_ids'][:-1]],device='cuda');attention=torch.ones_like(ids)
    base=model.get_base_model()
    with torch.autocast('cuda',dtype=torch.bfloat16):
        hidden=base.model(input_ids=ids,attention_mask=attention,use_cache=False,return_dict=True).last_hidden_state[0]
        start=row['response_start']-1;response=row['response_ids'];weights=row['weights'];total=hidden.sum()*0
        for offset in range(0,len(response),cfg['label_logits_chunk']):
            count=min(cfg['label_logits_chunk'],len(response)-offset)
            logits=base.lm_head(hidden[start+offset:start+offset+count]).float()
            targets=torch.tensor(response[offset:offset+count],device='cuda')
            losses=F.cross_entropy(logits,targets,reduction='none')
            total=total+(losses*torch.tensor(weights[offset:offset+count],device='cuda')).sum()
    return total


def native_smoke(model,tokenizer,out,cfg,checkpoint):
    import torch
    from legal_skill_guard.rr.method_ledger import MethodLedger
    records=load_json(out/'open_dataset.json')['records'];train=common_source_order(records)
    selected=[];seen=set()
    for r in train:
        if r['dataset'] not in seen:selected.append(r);seen.add(r['dataset'])
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN_ID,
        binding={'code_hash':hashlib.sha256(compact(cfg['code_sha256']).encode()).hexdigest(),
                 'config_hash':sha(out/'common_init_config.json')},
        sources={s:[r['key'] for r in records if r['split']==s] for s in ('train','dev')},
        authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),
        question='Verify native generation after common TRAIN-only initialization, before fixed three-epoch method comparison')
    model.eval();results=[];torch.manual_seed(45)
    for record in selected:
        inputs=tokenizer.apply_chat_template(prompt(record),tokenize=True,add_generation_prompt=True,
                enable_thinking=False,return_tensors='pt').to('cuda')
        request={'thinking':False,'checkpoint_sha256':sha(checkpoint/'adapter_model.safetensors'),
                 'prompt_ids_sha256':hashlib.sha256(inputs.cpu().numpy().tobytes()).hexdigest(),
                 'generation':cfg['generation'],'source':record['key']}
        call_id=RUN_ID+':native_smoke:'+record['dataset'];reservation=ledger.reserve(call_id,role='executor',
            purpose='method_primitive_observation',source=record['key'],request=request)
        if not reservation['dispatch']:results.append(reservation['result']);continue
        started=time.monotonic();result={'dataset':record['dataset'],'source':record['key'],'thinking':False}
        try:
            with torch.inference_mode():
                generated=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                    do_sample=True,temperature=.6,top_p=.95,top_k=20,max_new_tokens=min(8192,32768-inputs.shape[-1]),
                    pad_token_id=tokenizer.eos_token_id,use_cache=True)
            response=generated[0,inputs.shape[-1]:];text=tokenizer.decode(response,skip_special_tokens=True)
            try:parsed=json.loads(text);parse_error=None
            except Exception as e:parsed=None;parse_error=str(e)
            result.update(text=text,parsed=parsed,parse_error=parse_error,
                          input_tokens=int(inputs.shape[-1]),output_tokens=int(len(response)),
                          finish='eos' if int(response[-1])==tokenizer.eos_token_id else 'length',
                          elapsed_seconds=time.monotonic()-started)
            ledger.finish(call_id,status='completed',result=result)
        except Exception as e:
            result.update(error=type(e).__name__+': '+str(e),elapsed_seconds=time.monotonic()-started)
            ledger.finish(call_id,status='failed',result=result);torch.cuda.empty_cache()
        results.append(result);write_json(out/'common_native_smoke.json',results)
        print(json.dumps({'native_smoke':record['dataset'],'parse_ok':result.get('parsed') is not None,
                         'finish':result.get('finish'),'error':result.get('error')},ensure_ascii=False),flush=True)
    return results


def train(out):
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import LoraConfig,get_peft_model,set_peft_model_state_dict
    from safetensors.torch import load_file
    cfg=load_json(out/'common_init_config.json');assert_binding(out,cfg)
    training_root=out/'common_native_initialization';training_root.mkdir(exist_ok=True)
    lock=(training_root/'run.lock').open('a')
    try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('The existing native initialization process is still running')
    if (training_root/'complete.json').exists():print('Common native pass already complete; no duplicate training');return
    random.seed(45);torch.manual_seed(45);torch.cuda.manual_seed_all(45);torch.set_num_threads(4)
    tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,local_files_only=True)
    print('Loading unchanged Qwen3-8B base for common native initialization',flush=True)
    base=AutoModelForCausalLM.from_pretrained(BASE_MODEL,torch_dtype=torch.bfloat16,local_files_only=True,
           attn_implementation='sdpa',low_cpu_mem_usage=True).to('cuda')
    model=get_peft_model(base,LoraConfig(r=16,lora_alpha=32,lora_dropout=.05,target_modules=cfg['target_modules'],task_type='CAUSAL_LM',bias='none'))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False});model.enable_input_require_grads();model.config.use_cache=False
    parameters=[p for p in model.parameters() if p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    position=step=0;losses=[]
    latest=training_root/'latest.json'
    if latest.exists():
        previous=load_json(latest);location=out/previous['checkpoint']
        if previous['config_sha256']!=sha(out/'common_init_config.json'):raise ValueError('Checkpoint configuration mismatch')
        set_peft_model_state_dict(model,load_file(str(location/'adapter_model.safetensors')))
        state=torch.load(location/'optimizer.pt',map_location='cpu',weights_only=False)
        optimizer.load_state_dict(state['optimizer']);position=state['position'];step=state['step'];losses=state['losses']
        torch.set_rng_state(state['torch_rng']);torch.cuda.set_rng_state_all(state['cuda_rng']);random.setstate(state['python_rng'])
    records=load_json(out/'common_train_tokens.json');accum=cfg['gradient_accumulation_sources'];steps=math.ceil(len(records)/accum)
    probe=next(p for n,p in reversed(list(model.named_parameters())) if 'lora_B' in n and p.requires_grad)
    optimizer.zero_grad(set_to_none=True);started=time.monotonic();updates={};model.train()
    write_json(training_root/'process.json',{'pid':os.getpid(),'run_id':RUN_ID,'config_sha256':sha(out/'common_init_config.json'),'position_at_start':position})
    for index in range(position,len(records)):
        row=records[index];begin=time.monotonic();old_probe=probe.grad.detach().clone() if probe.grad is not None else None
        append(training_root/'compute_events.jsonl',{'event':'forward_started','source':row['key'],'dataset':row['dataset'],
               'position':index,'input_tokens':len(row['input_ids']),'time':time.time(),'physical_generation':False})
        loss=weighted_loss(model,row,cfg)
        if not torch.isfinite(loss):raise ValueError('Non-finite native training loss')
        (loss/accum).backward()
        delta=probe.grad.detach()-(old_probe if old_probe is not None else 0)
        delta_norm=float(delta.float().norm());value=float(loss.detach());losses.append({'source':row['key'],'dataset':row['dataset'],'loss':value})
        if not math.isfinite(delta_norm):raise ValueError('Non-finite native gradient')
        updates[row['dataset']]=updates.get(row['dataset'],0)+int(delta_norm>0)
        append(training_root/'compute_events.jsonl',{'event':'source_backward_completed','source':row['key'],
               'dataset':row['dataset'],'position':index,'loss':value,'probe_gradient_delta_l2':delta_norm,
               'input_tokens':len(row['input_ids']),'supervised_tokens':row['response_tokens'],
               'seconds':time.monotonic()-begin,'cuda_peak_bytes':torch.cuda.max_memory_allocated()})
        del loss,delta,old_probe
        if (index+1)%accum==0 or index+1==len(records):
            norm=float(torch.nn.utils.clip_grad_norm_(parameters,cfg['gradient_clip']))
            if not math.isfinite(norm):raise ValueError('Non-finite optimizer gradient')
            lr=cfg['learning_rate']*max(0.02,(steps-step)/steps)
            for group in optimizer.param_groups:group['lr']=lr
            optimizer.step();optimizer.zero_grad(set_to_none=True);step+=1
            append(training_root/'optimizer_steps.jsonl',{'step':step,'sources_consumed':index+1,'learning_rate':lr,
                   'gradient_norm':norm,'mean_block_loss':sum(x['loss'] for x in losses[-accum:])/len(losses[-accum:]),'elapsed_seconds':time.monotonic()-started})
            if step%4==0 or step==2 or index+1==len(records):
                assert_binding(out,cfg);save_checkpoint(model,optimizer,out,step,index+1,losses,cfg)
            write_json(training_root/'status.json',{'status':'running','optimizer_steps':step,'sources_consumed':index+1,
                       'sources_total':len(records),'dataset_nonzero_probe_backward_counts':updates,'last_loss':value})
            print(json.dumps({'optimizer_step':step,'sources':index+1,'dataset':row['dataset'],'loss':value,
                              'elapsed_seconds':round(time.monotonic()-started,2)},ensure_ascii=False),flush=True)
    location=save_checkpoint(model,optimizer,out,step,len(records),losses,cfg)
    write_json(training_root/'native_pass_complete.json',{'checkpoint':str(location),'optimizer_steps':step,
               'sources':len(records),'dataset_nonzero_probe_backward_counts':updates,
               'seconds':time.monotonic()-started,'trainable_parameters':sum(p.numel() for p in parameters),
               'base_model_weights_updated':False,'all_adapters_share_this_initialization':True})
    native_smoke(model,tokenizer,out,cfg,location)
    write_json(training_root/'complete.json',{'native_pass':True,'native_smoke_recorded':True,'checkpoint':str(location),
               'config_sha256':sha(out/'common_init_config.json'),'goal_complete':False})


def main():
    p=argparse.ArgumentParser();p.add_argument('--prepare',action='store_true');p.add_argument('--train',action='store_true')
    p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');args=p.parse_args();out=(ROOT/args.out).resolve()
    if args.prepare:prepare(out)
    if args.train:
        try:train(out)
        except BaseException as e:
            write_json(out/'common_initialization_failure.json',{'error':type(e).__name__+': '+str(e),'traceback':traceback.format_exc(),'time':time.time(),'goal_complete':False})
            raise


if __name__=='__main__':main()
