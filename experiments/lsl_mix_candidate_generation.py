"""Bound, resumable source generation; no reference data enters a request.

This stage only acquires candidates. Execution and training are separate, so a
correct native answer cannot silently repair a generated semantic record.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.native_training import prompt
from legal_skill_guard.lsl.native_schema import schema
from legal_skill_guard.lsl.scalar_proposals import proposal_prompt,proposal_schema
from legal_skill_guard.lsl.physical import payload
from legal_skill_guard.lsl.streaming_physical import dispatch_stream


def specification(row):
    if row['dataset'] in ('SARA_v2_Binary','RuleArena_Airline'):
        messages,_,index=proposal_prompt(row)
        return messages,proposal_schema(index)
    return prompt(row),schema(row['dataset'],row['public'])


def generate(out,checkpoint,stage,split,alias='common'):
    records=[r for r in load_json(out/'open_dataset.json')['records'] if r['split']==split]
    # Manifest order, independent of model outcomes. TEST has no loader here.
    if split not in ('train','dev'):raise ValueError('Only TRAIN/DEV authorized')
    location=out/'candidates'/stage/split;location.mkdir(parents=True,exist_ok=True)
    bound=['experiments/lsl_mix_candidate_generation.py','legal_skill_guard/lsl/native_training.py',
           'legal_skill_guard/lsl/native_schema.py','legal_skill_guard/lsl/scalar_proposals.py',
           'legal_skill_guard/lsl/physical.py','legal_skill_guard/lsl/streaming_physical.py','legal_skill_guard/lsl/role_codec.py','legal_skill_guard/lsl/contract_wire.py','legal_skill_guard/lsl/horn_codec.py','legal_skill_guard/rr/public_horn.py']
    config={'stage':stage,'split':split,'checkpoint_sha256':sha(checkpoint/'adapter_model.safetensors'),
            'manifest_sha256':load_json(out/'manifest.json')['runtime_sha256'],
            'open_dataset_sha256':sha(out/'open_dataset.json'),
            'code':{f:sha(ROOT/f) for f in bound},'thinking':False,'source_count':len(records),
            'generation':'unchanged temperature=.6 top_p=.95 top_k=20 seed=45 max_tokens=8192',
            'question':'Acquire own source records for the fixed mixed-training mechanism comparison',
            'teacher_calls':0,'gold_in_requests':False,'fallback_repair':False}
    config_file=location/'config.json'
    run='LSG-MIX256-candidates-'+stage+'-'+split
    config['model_alias']=alias
    config['dispatch']='continuous maximum8, reserve immediately before each physical HTTP, no retry'
    if config_file.exists() and load_json(config_file)!=config:raise ValueError('Candidate binding differs')
    write_json(config_file,config)
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,
        binding={'code_hash':digest(config['code']),'config_hash':digest(config)},
        sources={s:[r['key'] for r in load_json(out/'open_dataset.json')['records'] if r['split']==s] for s in ('train','dev')},
        authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),question=config['question'])
    requests=[];complete=[]
    for row in records:
        messages,grammar=specification(row)
        requests.append({'call_id':run+':'+digest(row['key']), 'source':row['key'],
            'purpose':'method_primitive_observation' if split=='train' else 'method_dev',
            'request':{'thinking':False,'checkpoint_sha256':config['checkpoint_sha256'],
                       'public_sha256':row['runtime_public_sha256'],
                       'payload':payload(messages,grammar,model=alias)}})
    completed={};by_id={r['call_id']:row for r,row in zip(requests,records)}
    def save_result(call_id,result):
        completed[by_id[call_id]['key']]=result
        if len(completed)%8==0 or len(completed)==len(records):
            for f,h in config['code'].items():
                if sha(ROOT/f)!=h:raise ValueError('Live source binding changed: '+f)
            output=[{'source':r['key'],'dataset':r['dataset'],'split':split,
                     'public_sha256':r['runtime_public_sha256'],'result':completed[r['key']]}
                    for r in records if r['key'] in completed]
            write_json(location/'results.json',output)
            write_json(location/'status.json',{'completed':len(output),'total':len(records),
                'finish_counts':{f:sum(x['result'].get('finish')==f for x in output) for f in ('stop','length',None)}})
            print(json.dumps({'candidate_sources':len(output),'total':len(records)},ensure_ascii=False),flush=True)
    dispatch_stream(ledger,requests,location/'raw',concurrency=8,on_result=save_result)
    complete=[completed[r['key']]for r in records]
    write_json(location/'complete.json',{'sources':len(complete),'config_sha256':sha(config_file),
               'not_method_validation':True,'goal_complete':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--split',choices=('train','dev'),required=True)
    p.add_argument('--checkpoint',required=True);p.add_argument('--alias',default='common')
    p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');a=p.parse_args()
    generate((ROOT/a.out).resolve(),Path(a.checkpoint).resolve(),a.stage,a.split,a.alias)
