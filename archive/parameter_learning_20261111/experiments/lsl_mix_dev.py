"""Fixed seven-system DEV80, with real acquisition and separate fallback.

Generation uses four independently trained acquisition adapters. Composition
heads are shared only where training dependencies are identical. TEST is never
loaded, and native grading is separated from candidate construction/selection.
"""
from pathlib import Path
import argparse
import fcntl
from collections import Counter
from copy import deepcopy
import json
import os
import sqlite3
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.native_semantics import predict
from legal_skill_guard.lsl.native_training import prompt
from legal_skill_guard.lsl.native_schema import obj,schema
from legal_skill_guard.lsl.physical import payload
from legal_skill_guard.lsl.streaming_physical import dispatch_stream
from legal_skill_guard.lsl.native_decoding import norm_feature_texts,norm_beam,norm_squares,select_norm,other_squares
from legal_skill_guard.lsl.native_composition import NativeComposer,feature_texts,select
from legal_skill_guard.lsl.composition_data import gold_graph
from legal_skill_guard.lsl.features import FeatureCache
from legal_skill_guard.lsl.dev_scoring import score,summarize
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.coverage import digest
from experiments.lsl_mix_native_initialization import BASE_MODEL
from experiments.lsl_mix_candidate_generation import generate

PYTHON='/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102/bin/python'
ARMS=('Base','M1','HardEM','ExecutionFilter')
SYSTEMS={'Base':('Base','ordinary'),'M1':('M1','ordinary'),'M2':('Base','directed'),'Joint':('M1','directed'),
         'HardEM':('HardEM','ordinary'),'ExecutionFilter':('ExecutionFilter','ordinary'),'PairContrast':('Base','contrast')}


def public_only(row):return {k:row[k]for k in ('key','dataset','family_id','public','runtime_public_sha256')}


def checkpoints(out,epoch):
    paths={}
    for arm in ARMS:
        done=load_json(out/'acquisition'/arm/('epoch%d'%epoch)/'complete.json')
        if done['sources']!=256 or done['epoch']!=epoch:raise ValueError('Acquisition epoch incomplete')
        paths[arm]=Path(done['checkpoint'])
    for mode in ('ordinary','directed','contrast'):
        if not (out/'composition'/mode/('epoch%d'%epoch)/'complete.json').exists():raise ValueError('Composition epoch incomplete')
    return paths


def stop_serving(out,epoch):
    import httpx
    unit='legal-lsl-mix256-serving-e'+str(epoch)
    active=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()
    if active!='active':return
    with sqlite3.connect(out.parent/'rr_v2_preflight/research_ledger.sqlite3')as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():raise RuntimeError('Pending physical request; preserve it before GPU handoff')
    metrics=httpx.get('http://127.0.0.1:8000/metrics',trust_env=False,timeout=10).text
    states=[x for x in metrics.splitlines()if x.startswith(('vllm:num_requests_running','vllm:num_requests_waiting'))]
    if not states or any(float(x.rsplit(' ',1)[1])!=0 for x in states):raise RuntimeError('Real serving requests still active')
    write_json(out/'dev'/('epoch%d'%epoch)/'serving_boundary.json',{'unit':unit,'metrics':states,'pending':0,'time':time.time()})
    subprocess.run(['systemctl','--user','stop',unit],check=True)


def serve(out,epoch,paths):
    import httpx
    location=out/'dev'/('epoch%d'%epoch);location.mkdir(parents=True,exist_ok=True)
    unit='legal-lsl-mix256-serving-e'+str(epoch)
    command=[PYTHON,str(Path(PYTHON).with_name('vllm')),'serve',BASE_MODEL,'--served-model-name','Qwen/Qwen3-8B',
        '--host','127.0.0.1','--port','8000','--dtype','bfloat16','--max-model-len','32768','--max-num-seqs','8',
        '--seed','45','--generation-config','vllm','--reasoning-parser','qwen3','--gpu-memory-utilization','0.84',
        '--no-enable-prefix-caching','--disable-uvicorn-access-log','--guided-decoding-backend','xgrammar',
        '--guided-decoding-disable-any-whitespace','--kv-cache-memory-bytes','10737418240',
        '--max-num-batched-tokens','8192','--enable-lora','--max-lora-rank','16','--max-loras','4',
        '--max-cpu-loras','4','--lora-modules',*[a+'='+str(paths[a])for a in ARMS]]
    cfg={'unit':unit,'command':command,'checkpoint_sha256':{a:sha(p/'adapter_model.safetensors')for a,p in paths.items()},'thinking':False}
    previous=location/'serving_config.json'
    if previous.exists() and load_json(previous)!=cfg:raise ValueError('Serving binding changed')
    write_json(previous,cfg)
    state=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()
    if state!='active':
        subprocess.run(['systemd-run','--user','--unit='+unit,'--property=WorkingDirectory='+str(ROOT),
            '--property=StandardOutput=append:'+str(location/'serving_stdout.log'),
            '--property=StandardError=append:'+str(location/'serving_stdout.log'),*command],check=True)
    start=time.monotonic()
    while time.monotonic()-start<600:
        try:
            models=httpx.get('http://127.0.0.1:8000/v1/models',trust_env=False,timeout=5).json()
            ids={x['id']for x in models['data']}
            if set(ARMS)<=ids:write_json(location/'serving_ready.json',{'models':sorted(ids),'seconds':time.monotonic()-start});return
        except Exception:pass
        state=subprocess.run(['systemctl','--user','is-active',unit],capture_output=True,text=True).stdout.strip()
        if state=='failed':raise RuntimeError('Serving failed; see bound service log')
        time.sleep(3)
    raise RuntimeError('Serving readiness failed; do not duplicate pending model requests')


def plan(row,result):
    public=public_only(row)
    try:
        if result.get('finish')!='stop' or result.get('parsed')is None:raise ValueError('incomplete_or_unparseable_generation')
        execution=predict(public,result['parsed'])
        if not execution['valid']:raise ValueError(execution.get('error',execution.get('status','native_execution_invalid')))
        if row['dataset']=='NormBench':return {'valid':True,'output':result['parsed'],'execution':execution,'graph':execution['graph']}
        primary,squares=other_squares(public,result['parsed'])
        return {'valid':True,'output':primary,'execution':execution,'squares':squares}
    except Exception as e:return {'valid':False,'output':result.get('parsed'),'execution':None,'error':type(e).__name__+': '+str(e)}


def fallback_request(row):
    d=row['dataset'];messages=prompt(public_only(row))
    if d=='ContractNLI':
        grammar=obj({'answers':obj({k:{'type':'string','enum':['Entailment','Contradiction','NotMentioned']}for k in row['public']['queries']})})
        instruction='Task readout fallback. Classify all17 public hypotheses. Output only {"answers":{hypothesis_id:native_label}}. Evidence and source IR are unavailable in this fallback; do not invent them.'
    else:
        labels=['True','False','Unknown']if d=='ProofWriter_OWA_depth5'else ['Entailment','Contradiction']
        grammar=obj({'answer':{'type':'integer'}})if d=='RuleArena_Airline'else obj({'answer':{'type':'string','enum':labels}})
        meaning={'ProofWriter_OWA_depth5':'Use OWA: True iff query is provable, False iff its explicit negation is provable, Unknown iff neither.',
                 'SARA_v2_Binary':'Entailment means the statutory claim holds in this case; Contradiction means it does not.',
                 'RuleArena_Airline':'Return the exact integer total of this current ticket plus fees for every current bag.'}[d]
        instruction='Task readout fallback. '+meaning+' Output only {"answer":the native task result}; do not output a program or claim source-rule acquisition.'
    # Same complete public source, explicit different task-only output protocol.
    messages[-1]['content']=instruction+'\nDATASET='+messages[-1]['content'].split('\nDATASET=',1)[1]
    return messages,grammar


def fallbacks(out,epoch,paths,rows,plans):
    location=out/'dev'/('epoch%d'%epoch);run='LSG-MIX256-fallback-e'+str(epoch)
    cfg={'stage':run,'checkpoint_sha256':{a:sha(p/'adapter_model.safetensors')for a,p in paths.items()},
        'rule':'only native parsing/execution failure, never semantic incorrectness; cached explicit PW readout may be reused',
        'thinking':False,'main_output_hashes':{a:sha(out/'candidates'/('epoch%d-'%epoch+a)/'dev/results.json')for a in ARMS}}
    write_json(location/'fallback_config.json',cfg)
    allrows=load_json(out/'open_dataset.json')['records']
    ledger=MethodLedger(out.parent/'rr_v2_preflight/research_ledger.sqlite3',run_id=run,
        binding={'code_hash':sha(Path(__file__)),'config_hash':digest(cfg)},
        sources={s:[r['key']for r in allrows if r['split']==s]for s in ('train','dev')},
        authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),question=cfg['rule'])
    requests=[];cached={}
    for arm in ARMS:
        for row in rows:
            p=plans[arm][row['key']]
            if p['valid']or row['dataset']=='NormBench':continue
            prior=(p.get('output')or{}).get('answer')
            if row['dataset']=='ProofWriter_OWA_depth5'and prior in ('True','False','Unknown'):
                cached[arm+':'+row['key']]={'parsed':{'answer':prior},'existing_explicit_neural_readout':True};continue
            messages,grammar=fallback_request(row);call_id=run+':'+arm+':'+digest(row['key'])
            requests.append({'call_id':call_id,'source':row['key'],'purpose':'method_dev',
                'request':{'thinking':False,'checkpoint_sha256':cfg['checkpoint_sha256'][arm],
                    'fallback_reason':p['error'],'payload':payload(messages,grammar,model=arm)}})
    def record(call_id,result):
        arm=call_id.split(':')[1];cached[arm+':'+result['source']]=result
        if len(cached)%8==0:write_json(location/'fallback_results.json',cached)
    if requests:dispatch_stream(ledger,requests,location/'fallback_raw',on_result=record)
    write_json(location/'fallback_results.json',cached)
    return cached


def fallback_execution(row,result):
    p=result.get('parsed')if result else None
    if not isinstance(p,dict):return None
    if row['dataset']=='ContractNLI':
        labels=p.get('answers',{})
        if set(labels)!=set(row['public']['queries'])or any(v not in ('Entailment','Contradiction','NotMentioned')for v in labels.values()):return None
        return {'valid':True,'answer':labels,'evidence':{},'evidence_available':False,'fallback':True}
    value=p.get('answer');d=row['dataset']
    if d=='RuleArena_Airline'and type(value)is not int:return None
    if d=='SARA_v2_Binary'and value not in ('Entailment','Contradiction'):return None
    if d=='ProofWriter_OWA_depth5'and value not in ('True','False','Unknown'):return None
    return {'valid':True,'answer':value,'fallback':True}


def evaluate(out,epoch,rows,plans,fallback):
    import torch
    from transformers import AutoModelForCausalLM,AutoTokenizer
    location=out/'dev'/('epoch%d'%epoch);texts=[];gold_local={}
    for row in rows:
        if row['dataset']=='NormBench':
            gold_local[row['key']]={k:v for k,v in gold_graph(row['native_record']).items()if k!='parents'}
            texts.extend(norm_feature_texts(public_only(row),gold_local[row['key']]))
        for arm in ARMS:
            p=plans[arm][row['key']]
            if not p['valid']:continue
            if row['dataset']=='NormBench':texts.extend(norm_feature_texts(public_only(row),p['graph']))
            elif p['squares']:texts.extend(feature_texts(public_only(row),[p['output']]+[c for s in p['squares']for c in s['cells']]))
    cache=FeatureCache(out/'composition_base_features.safetensors');missing=[t for t in dict.fromkeys(texts)if not cache.has(t)]
    if missing:
        torch.set_num_threads(4)
        tokenizer=AutoTokenizer.from_pretrained(BASE_MODEL,local_files_only=True)
        base=AutoModelForCausalLM.from_pretrained(BASE_MODEL,torch_dtype=torch.bfloat16,attn_implementation='sdpa',local_files_only=True,low_cpu_mem_usage=True).to('cuda')
        cache.attach(base,tokenizer);cache.encode(missing);cache.save();cache.model=None;del base;torch.cuda.empty_cache()
    snapshot=location/'features.safetensors'
    if not snapshot.exists():os.link(cache.path,snapshot)
    models={}
    for mode in ('ordinary','directed','contrast'):
        model=NativeComposer().eval();state=torch.load(out/'composition'/mode/('epoch%d'%epoch)/'model.pt',map_location='cpu',weights_only=False);model.load_state_dict(state['model'])
        for parameter in model.parameters():parameter.requires_grad_(False)
        models[mode]=model
    predictions=[];diagnostic=[];precomposition={}
    for arm in ARMS:
        precomposition[arm]={}
        for row in rows:
            p=plans[arm][row['key']]
            precomposition[arm][row['key']]=score(row,p.get('execution'),graph=p.get('graph'),output=p.get('output'),error=p.get('error'))
    for system,(arm,mode)in SYSTEMS.items():
        model=models[mode]
        for row in rows:
            public=public_only(row);p=plans[arm][row['key']];used=False;composition={'mode':mode,'directed_head_used':False};output=p.get('output');graph=None
            error=p.get('error');execution=p.get('execution')
            if not p['valid']:
                execution=fallback_execution(row,fallback.get(arm+':'+row['key'],{}));used=execution is not None
                composition['reason']='main_acquisition_or_execution_failed'
            elif row['dataset']=='NormBench':
                graph=p['graph']
                if any(n['kind']=='branch'for n in graph['nodes']):
                    try:
                        forests,beam=norm_beam(model,public,graph,cache);forests=[graph]+forests
                        unique={tuple(g['parents']):g for g in forests};rank=[]
                        for signature,g in unique.items():
                            local,_=model.square(public,[g],cache,interactions=False);rank.append((float(local[0]),g))
                        forests=[g for _,g in sorted(rank,key=lambda x:x[0],reverse=True)[:8]]
                        squares=norm_squares(forests);graph,composition=select_norm(model,public,forests,squares,cache,mode);composition.update(beam)
                    except Exception as e:used=True;composition={'directed_head_used':False,'reason':'composition_error_using_generated_forest','error':str(e)}
                execution={'valid':True,'graph':graph}
            elif p['squares']:
                try:
                    output,composition=select(model,public,p['output'],p['squares'],cache,mode)
                    composition['directed_head_used']=mode!='ordinary'and bool(p['squares']);execution=predict(public,output)
                except Exception as e:used=True;composition={'directed_head_used':False,'reason':'composition_error_using_generated_program','error':str(e)}
            else:composition['reason']='no_legal_scope_square_or_masked_contract_oracle'
            metric=score(row,execution,graph=graph,output=output,error=error)
            item={'source':row['key'],'dataset':row['dataset'],'system':system,'acquisition':arm,'epoch':epoch,
                'main_path_valid':p['valid'],'fallback_used':used,'fallback_reason':error if used else None,
                'composition':composition,'score':metric,'prediction':output,'selected_graph':graph}
            item['precomposition_score']=precomposition[arm][row['key']]
            predictions.append(item)
        # Gold-node inputs only enter this separate composition diagnostic.
        if system in ('Base','M2','PairContrast'):
            for row in rows:
                if row['dataset']!='NormBench':continue
                try:
                    forests,beam=norm_beam(model,public_only(row),gold_local[row['key']],cache)
                    graph,meta=select_norm(model,public_only(row),forests,norm_squares(forests),cache,mode)
                    metric=score(row,{'valid':True},graph=graph)
                    diagnostic.append({'source':row['key'],'system':system,'given_gold_local_nodes':True,'gold_parents_used_for_decoding':False,'beam':beam,'composition':meta,'score':metric})
                except Exception as e:diagnostic.append({'source':row['key'],'system':system,'given_gold_local_nodes':True,'error':str(e),'score':score(row,None,error=str(e))})
        write_json(location/'predictions.json',predictions);write_json(location/'gold_node_composition_diagnostic.json',diagnostic)
    summaries={}
    for system in SYSTEMS:
        summaries[system]={}
        for dataset in sorted({r['dataset']for r in rows}):
            selected=[r for r in predictions if r['system']==system and r['dataset']==dataset]
            if len(selected)!=16:raise ValueError('Incomplete fixed source denominator')
            summaries[system][dataset]=summarize(selected)
    write_json(location/'summary.json',summaries)
    write_json(location/'precomposition_scores.json',precomposition)
    write_json(location/'complete.json',{'systems':7,'DEV_sources_per_system':80,'predictions':len(predictions),
        'gold_node_diagnostic_rows':len(diagnostic),'feature_sha256':sha(snapshot),'TEST':False,'goal_complete':False})
    print(json.dumps({'DEV_epoch':epoch,'predictions':len(predictions),'summaries':summaries},ensure_ascii=False),flush=True)


def main(epoch):
    out=ROOT/'artifacts/lsl_mixed256_20261110';location=out/'dev'/('epoch%d'%epoch)
    location.mkdir(parents=True,exist_ok=True)
    lock=(location/'run.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    if (location/'complete.json').exists():print('Fixed DEV epoch already complete; not regenerating');return
    paths=checkpoints(out,epoch);rows=[r for r in load_json(out/'open_dataset.json')['records']if r['split']=='dev']
    if len(rows)!=80 or any(n!=16 for n in Counter(r['dataset']for r in rows).values()):raise ValueError('DEV80 quotas differ')
    files=['experiments/lsl_mix_dev.py','legal_skill_guard/lsl/native_decoding.py','legal_skill_guard/lsl/native_composition.py',
        'legal_skill_guard/lsl/dev_scoring.py','legal_skill_guard/lsl/native_semantics.py','legal_skill_guard/lsl/native_scope.py',
        'legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/lsl/native_training.py','legal_skill_guard/lsl/native_schema.py',
        'legal_skill_guard/lsl/physical.py','legal_skill_guard/lsl/streaming_physical.py']
    cfg={'epoch':epoch,'sources':80,'systems':SYSTEMS,'thinking':False,'manifest_sha256':sha(out/'manifest.json'),
        'checkpoints':{a:sha(p/'adapter_model.safetensors')for a,p in paths.items()},'code':{f:sha(ROOT/f)for f in files},
        'fallback':'only native parse/execute failures; explicit cached/readout-only results marked separately; no semantic-error-triggered fallback',
        'gold_local_nodes':'separate NormBench composition diagnostic, no gold parents, never replaces primary source results',
        'precomposition':'same cached acquisition outputs; no new model, source or generation',
        'TEST':False}
    if (location/'config.json').exists()and load_json(location/'config.json')!=cfg:raise ValueError('DEV binding changed; preserve existing records')
    write_json(location/'config.json',cfg)
    serve(out,epoch,paths)
    for arm in ARMS:generate(out,paths[arm],'epoch%d-'%epoch+arm,'dev',arm)
    plans={}
    for arm in ARMS:
        results={r['source']:r['result']for r in load_json(out/'candidates'/('epoch%d-'%epoch+arm)/'dev/results.json')}
        plans[arm]={r['key']:plan(r,results[r['key']])for r in rows}
    fallback=fallbacks(out,epoch,paths,rows,plans);stop_serving(out,epoch)
    evaluate(out,epoch,rows,plans,fallback)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--epoch',type=int,choices=(1,2,3),required=True);a=p.parse_args();main(a.epoch)
