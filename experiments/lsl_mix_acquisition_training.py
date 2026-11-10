"""One resumable epoch of actual native + acquisition-objective LoRA learning.

Four acquisition models supply seven systems. All start from exactly the same
common checkpoint; all use the same finite local alternatives and execution
tables. MML controls marginalize the same uniformly weighted completions.
M1 instead applies the stop-gradient minimum signed native-error preference.
"""
from pathlib import Path
import argparse
from collections import Counter
import fcntl
import hashlib
import importlib.metadata
import json
import math
import os
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.native_training import tokenize_record
from legal_skill_guard.lsl.packed_credit import tokenize_choices,log_scores
from legal_skill_guard.lsl.local_credit import robust_loss,weak_loss,prior_loss
from experiments.lsl_mix_native_initialization import weighted_loss,BASE_MODEL,append

MODES={'Base':'mml','M1':'robust','HardEM':'hard_em','ExecutionFilter':'execution_filter'}


def configuration(out,bank,arm,epoch):
    files=['experiments/lsl_mix_acquisition_training.py','legal_skill_guard/lsl/packed_credit.py',
           'legal_skill_guard/lsl/local_credit.py','legal_skill_guard/lsl/native_training.py',
           'legal_skill_guard/lsl/contract_wire.py',
           'legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/rr/public_horn.py',
           'experiments/lsl_mix_native_initialization.py']
    initial=out/'common_native_initialization/step_0032' if epoch==1 else Path(load_json(out/'acquisition'/arm/('epoch%d'%(epoch-1))/'complete.json')['checkpoint'])
    return {'run_id':'LSG-MIX256-acquisition-v1','arm':arm,'mode':MODES[arm],'epoch':epoch,
        'mixed_epochs':3,'thinking':False,'seed':45,'learning_rate':5e-5,'weight_decay':.01,
        'gradient_accumulation_sources':8,'gradient_clip':1.,'label_logits_chunk':64,
        'precision':'bfloat16','attention':'sdpa; exact block-isolated mask for local choices',
        'runtime_versions':{p:importlib.metadata.version(p) for p in ('torch','transformers','peft')},
        'lora_rank':16,'lora_alpha':32,'lora_dropout':.05,'prior_weight':.1,'weak_weight':1.,
        'weak_MML_in_M1':False,'completion_distribution':'uniform over the identical checked compatible completion table, held fixed for acquisition',
        'local_choice_score':'exact autoregressive sequence log probability conditional on public source and quote',
        'native_loss':'original source-normalized task + available structure + evidence',
        'prior':'same common native initialization conditional distribution; no pseudo gold',
        'prior_mask':'only records lacking native dense annotation and stable shared local credit; identical mask in all arms',
        'local_likelihood_dropout':False,'native_training_dropout':True,
        'weak_block_reduction':'sum of at most four local terms inside each source; one source update',
        'common_checkpoint_sha256':sha(out/'common_native_initialization/step_0032/adapter_model.safetensors'),
        'initial_checkpoint_sha256':sha(initial/'adapter_model.safetensors'),
        'manifest_sha256':sha(out/'manifest.json'),'open_dataset_sha256':sha(out/'open_dataset.json'),
        'candidate_tables_sha256':sha(bank/'local/tables.json'),
        'code':{f:sha(ROOT/f) for f in files},'TEST_loaded':False}


def binding(out,bank,cfg):
    for p,h in cfg['code'].items():
        if sha(ROOT/p)!=h:raise ValueError('Live acquisition binding changed: '+p)
    for p,k in [(out/'manifest.json','manifest_sha256'),(out/'open_dataset.json','open_dataset_sha256'),(bank/'local/tables.json','candidate_tables_sha256')]:
        if sha(p)!=cfg[k]:raise ValueError('Live acquisition data changed: '+str(p))
    if sha(out/'common_native_initialization/step_0032/adapter_model.safetensors')!=cfg['common_checkpoint_sha256']:raise ValueError('Common reference weights changed')


def source_order(records,epoch):
    rng=random.Random(45);keys=sorted(records)
    for _ in range(epoch):rng.shuffle(keys)
    if len(keys)!=256:raise ValueError('Exactly256 fixed TRAIN sources required')
    return keys


def save(model,optimizer,location,step,position,cfg):
    import torch
    model.set_adapter('default');dest=location/('step_%04d'%step);dest.mkdir(exist_ok=True)
    model.save_pretrained(dest,selected_adapters=['default'])
    torch.save({'optimizer':optimizer.state_dict(),'step':step,'position':position,
                'torch_rng':torch.get_rng_state(),'cuda_rng':torch.cuda.get_rng_state_all(),'python_rng':random.getstate()},dest/'optimizer.temporary.pt')
    (dest/'optimizer.temporary.pt').replace(dest/'optimizer.pt')
    write_json(location/'latest.json',{'checkpoint':str(dest),'step':step,'position':position,'config_sha256':sha(location/'config.json')})
    return dest


def train(out,bank,arm,epoch):
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    from peft import PeftModel,set_peft_model_state_dict
    from safetensors.torch import load_file
    if epoch not in (1,2,3):raise ValueError('Fixed3 epochs only')
    location=out/'acquisition'/arm/('epoch%d'%epoch);location.mkdir(parents=True,exist_ok=True)
    lock=(out/'acquisition'/'gpu_train.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    cfg=configuration(out,bank,arm,epoch);config_file=location/'config.json'
    if config_file.exists() and load_json(config_file)!=cfg:raise ValueError('Existing acquisition run binding differs')
    write_json(config_file,cfg);binding(out,bank,cfg)
    if (location/'complete.json').exists():print('Acquisition epoch already complete; preserving result');return
    common=out/'common_native_initialization/step_0032'
    previous=common if epoch==1 else Path(load_json(out/'acquisition'/arm/('epoch%d'%(epoch-1))/'complete.json')['checkpoint'])
    rows={r['key']:r for r in load_json(out/'open_dataset.json')['records'] if r['split']=='train'}
    tables={r['source']:r for r in load_json(bank/'local/tables.json')}
    if set(rows)!=set(tables):raise ValueError('Fixed TRAIN table coverage differs')
    torch.set_num_threads(4);random.seed(45);torch.manual_seed(45);torch.cuda.manual_seed_all(45)
    tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,local_files_only=True)
    base=AutoModelForCausalLM.from_pretrained(BASE_MODEL,torch_dtype=torch.bfloat16,
        local_files_only=True,low_cpu_mem_usage=True,attn_implementation='sdpa').to('cuda')
    model=PeftModel.from_pretrained(base,previous,is_trainable=True,adapter_name='default')
    model.load_adapter(common,adapter_name='reference',is_trainable=False)
    model.set_adapter('default');model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
    model.enable_input_require_grads();model.config.use_cache=False
    parameters=[p for n,p in model.named_parameters() if '.default.' in n and p.requires_grad]
    optimizer=torch.optim.AdamW(parameters,lr=cfg['learning_rate'],weight_decay=cfg['weight_decay'])
    if epoch>1:
        optimizer.load_state_dict(torch.load(previous/'optimizer.pt',map_location='cpu',weights_only=False)['optimizer'])
    step=(epoch-1)*32;position=0
    if (location/'latest.json').exists():
        latest=load_json(location/'latest.json');saved=Path(latest['checkpoint'])
        if latest['config_sha256']!=sha(config_file):raise ValueError('Resume config mismatch')
        set_peft_model_state_dict(model,load_file(str(saved/'adapter_model.safetensors')),adapter_name='default')
        state=torch.load(saved/'optimizer.pt',map_location='cpu',weights_only=False)
        optimizer.load_state_dict(state['optimizer']);step=state['step'];position=state['position']
        torch.set_rng_state(state['torch_rng']);torch.cuda.set_rng_state_all(state['cuda_rng']);random.setstate(state['python_rng'])
    probe=next(p for n,p in reversed(list(model.named_parameters())) if 'lora_B.default' in n)
    order=source_order(rows,epoch);optimizer.zero_grad(set_to_none=True);started=time.monotonic()
    prior_path=out/'common_prior_scores.json';priors=load_json(prior_path) if prior_path.exists() else {}
    write_json(location/'process.json',{'pid':os.getpid(),'arm':arm,'epoch':epoch,'config_sha256':sha(config_file),'start_position':position})
    for index in range(position,256):
        key=order[index];record=rows[key];table=tables[key];begin=time.monotonic()
        proposed=[b for b in table.get('blocks',[]) if len(b.get('choices',[]))==2]
        unidentified=record['dataset'] not in ('NormBench','ProofWriter_OWA_depth5')
        blocks=[b for b in proposed if b.get('loss_table') or unidentified]
        prior_indices={i for i,b in enumerate(blocks) if unidentified and b.get('credit',{}).get('status')!='stable'}
        local=tokenize_choices(record,blocks,tokenizer) if blocks else None
        native_row=tokenize_record(record,tokenizer)
        append(location/'compute_events.jsonl',{'event':'source_forward_started','source':key,'dataset':record['dataset'],
            'position':index,'native_input_tokens':len(native_row['input_ids']),
            'native_supervised_tokens':native_row['response_tokens'],'packed_local_input_tokens':len(local['input_ids']) if local else 0,
            'time':time.time(),'physical_generations':0})
        prior=None
        if local is not None and prior_indices:
            cache_key=hashlib.sha256(json.dumps({'common':cfg['common_checkpoint_sha256'],'code':cfg['code']['legal_skill_guard/lsl/packed_credit.py'],
                'runtime':cfg['runtime_versions'],'precision':cfg['precision'],'row':local},sort_keys=True).encode()).hexdigest()
            if cache_key not in priors:
                t0=time.monotonic();model.set_adapter('reference');model.eval()
                with torch.no_grad():reference=log_scores(model,local)
                priors[cache_key]={str(i):v.cpu().tolist() for i,v in reference.items()};write_json(prior_path,priors)
                append(location/'compute_events.jsonl',{'event':'common_prior_forward','source':key,
                    'input_tokens':len(local['input_ids']),'seconds':time.monotonic()-t0,'physical_generations':0})
            prior=priors[cache_key];model.set_adapter('default')
        old_probe=probe.grad.detach().clone() if probe.grad is not None else None
        model.train();native=weighted_loss(model,native_row,cfg)
        if not bool(torch.isfinite(native)):raise ValueError('Non-finite native loss')
        native_value=float(native.detach());(native/8).backward();del native
        native_delta=probe.grad.detach()-(old_probe if old_probe is not None else 0)
        native_norm=float(native_delta.float().norm());del native_delta,old_probe
        core_value=prior_value=core_probe=0.;statuses=[]
        if local is not None:
            # Keep transformer checkpointing active for long packed sources,
            # while disabling stochastic adapter dropout for exact likelihoods.
            model.train()
            for module in model.modules():
                if isinstance(module,torch.nn.Dropout):module.eval()
            scores=log_scores(model,local);terms=[];pri=[]
            for i,b in enumerate(blocks):
                s=scores[i]
                if i in prior_indices:
                    ref=torch.tensor(prior[str(i)],device=s.device);pri.append(prior_loss(s,ref))
                loss_table=b.get('loss_table',[])
                if not loss_table:
                    statuses.append(b.get('credit',{}).get('status','no_usable_context'));continue
                if MODES[arm]=='robust':
                    term,info=robust_loss(s,loss_table,independently_fixed=b.get('independently_fixed',False),exhaustive=b.get('exhaustive',False))
                else:
                    # Factorized local-choice probability times the identical
                    # fixed completion distribution; no answer-based prior.
                    logs=s.repeat(len(loss_table));errors=[v for pair in loss_table for v in pair]
                    # A choice's execution signature spans ALL common
                    # completions. Using only the candidate's successful QA
                    # value would make this filtering control identically MML.
                    signatures=[[] for _ in range(2)]
                    for c in b['contexts']:
                        for j,v in enumerate(c['predictions']):signatures[j].extend(v if isinstance(v,list) else [v])
                    vectors=[signatures[j] for c in b['contexts'] for j in range(2)]
                    term,info=weak_loss(MODES[arm],logs,errors,vectors)
                terms.append(term);statuses.append(info['status'])
            zero=next(iter(scores.values())).sum()*0
            core=torch.stack(terms).sum() if terms else zero
            prior_term=torch.stack(pri).sum() if pri else zero
            core_value=float(core.detach());prior_value=float(prior_term.detach())
            if core_value:
                delta=torch.autograd.grad(core,probe,retain_graph=True,allow_unused=True)[0]
                if delta is not None:core_probe=float(delta.float().norm());del delta
            total=(core+.1*prior_term)/8
            if not bool(torch.isfinite(total)):raise ValueError('Non-finite acquisition weak/prior objective')
            total.backward();del total,core,prior_term,scores,terms,pri,zero
        append(location/'source_updates.jsonl',{'source':key,'dataset':record['dataset'],'position':index,
            'native_loss':native_value,'core_acquisition_loss':core_value,'prior_KL':prior_value,
            'core_probe_gradient_l2':core_probe,'native_source_probe_delta_l2':native_norm,
            'blocks':len(blocks),'proposed_blocks':len(proposed),'prior_mask_blocks':len(prior_indices),
            'native_input_tokens':len(native_row['input_ids']),'native_supervised_tokens':native_row['response_tokens'],
            'credit_statuses':statuses,'input_tokens_local':len(local['input_ids']) if local else 0,
            'seconds':time.monotonic()-begin,'cuda_peak_bytes':torch.cuda.max_memory_allocated(),'physical_generations':0})
        if (index+1)%8==0:
            norm=float(torch.nn.utils.clip_grad_norm_(parameters,1.))
            if not math.isfinite(norm):raise ValueError('Non-finite acquisition gradient')
            lr=cfg['learning_rate']*max(.02,(96-step)/96)
            for group in optimizer.param_groups:group['lr']=lr
            optimizer.step();optimizer.zero_grad(set_to_none=True);step+=1
            append(location/'optimizer_steps.jsonl',{'step':step,'sources':index+1,'lr':lr,'gradient_norm':norm,'elapsed_seconds':time.monotonic()-started})
            if step%4==0 or step==(epoch-1)*32+1 or index==255:binding(out,bank,cfg);save(model,optimizer,location,step,index+1,cfg)
            write_json(location/'status.json',{'arm':arm,'epoch':epoch,'sources_consumed':index+1,'optimizer_step':step,'last_native_loss':native_value,'last_core_loss':core_value})
            print(json.dumps({'arm':arm,'epoch':epoch,'sources':index+1,'step':step,'native':native_value,'core':core_value,'elapsed':time.monotonic()-started}),flush=True)
    dest=save(model,optimizer,location,step,256,cfg)
    write_json(location/'complete.json',{'checkpoint':str(dest),'sources':256,'epoch':epoch,'arm':arm,
        'seconds':time.monotonic()-started,'optimizer_step':step,'config_sha256':sha(config_file),'goal_complete':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--arm',choices=list(MODES),required=True);p.add_argument('--epoch',type=int,required=True)
    p.add_argument('--bank',required=True);p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');a=p.parse_args()
    train((ROOT/a.out).resolve(),Path(a.bank).resolve(),a.arm,a.epoch)
