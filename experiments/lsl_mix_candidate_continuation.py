"""Continue a drained queue after the reproduced Contract evidence loop.

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
from legal_skill_guard.lsl.physical import dispatch_many,payload


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
    bound=['experiments/lsl_mix_candidate_continuation.py','legal_skill_guard/lsl/native_training.py',
           'legal_skill_guard/lsl/native_schema.py','legal_skill_guard/lsl/scalar_proposals.py',
           'legal_skill_guard/lsl/physical.py','legal_skill_guard/lsl/role_codec.py']
    config={'stage':stage,'split':split,'checkpoint_sha256':sha(checkpoint/'adapter_model.safetensors'),
            'manifest_sha256':load_json(out/'manifest.json')['runtime_sha256'],
            'open_dataset_sha256':sha(out/'open_dataset.json'),
            'code':{f:sha(ROOT/f) for f in bound},'thinking':False,'source_count':len(records),
            'generation':'unchanged temperature=.6 top_p=.95 top_k=20 seed=45 max_tokens=8192',
            'question':'Acquire own source records for the fixed mixed-training mechanism comparison',
            'teacher_calls':0,'gold_in_requests':False,'fallback_repair':False,
            'continuation_of':'common-v3/train','revision':'public evidence cardinality bound; evidence before native label',
            'previous_config_sha256':sha(out/'candidates/common-v3/train/config.json')}
    config_file=location/'config.json'
    run='LSG-MIX256-candidates-'+stage+'-'+split
    reused={}
    if stage=='common-v3' and split=='train':
        for previous,required in [('native_schema_v3',['native_training.py','native_schema.py','role_codec.py']),
                                  ('scalar_source_pilot_v2',['scalar_proposals.py','safe_program.py'])]:
            old=load_json(out/(previous+'_config.json'))
            old_checkpoint=old.get('common_checkpoint_sha256',old.get('checkpoint_sha256'))
            if old_checkpoint!=config['checkpoint_sha256']:continue
            paths=[f for f in old['code'] if Path(f).name in required]
            if len(paths)!=len(required) or any(sha(ROOT/f)!=old['code'][f] for f in paths):continue
            for f in (out/(previous+'_raw')).glob('*.json'):
                saved=load_json(f)
                if saved['status']=='completed':reused[saved['result']['source']]={**saved['result'],'reused_from':str(f.relative_to(ROOT))}
    config['reused_outputs']={k:v['reused_from'] for k,v in reused.items()}
    # Preserve completed source events from the drained queue. This is an
    # explicit continuation with mixed, recorded grammar provenance, not a
    # claim that changed requests have identical hashes. Only the reproduced
    # truncated Contract cases are retried under the revised configuration.
    oldbase=out/'candidates/common-v3/train';oldcfg=load_json(oldbase/'config.json')
    paths=list((oldbase/'raw').glob('*.json'))+[ROOT/v for v in oldcfg['reused_outputs'].values()]
    adaptations={}
    for p in paths:
        saved=load_json(p)
        if saved['status']!='completed':continue
        r=saved['result'];key=r['source']
        row=next((x for x in records if x['key']==key),None)
        if row is None:continue
        if row['dataset']=='ContractNLI' and r.get('finish')=='length':continue
        r={**r,'reused_from':str(p.relative_to(ROOT)),'continued_event_under_original_grammar':True}
        if row['dataset']=='ContractNLI' and r.get('parsed') is not None:
            from copy import deepcopy
            converted=deepcopy(r['parsed']);removed=0
            for a in converted.get('answers',[]):
                if 'evidence' in a:
                    dedup=list(dict.fromkeys(a['evidence']));removed+=len(a['evidence'])-len(dedup);a['evidence']=dedup
            if removed:
                r['parsed']=converted;r['deterministic_adaptation']='native evidence set duplicate removal; no labels/spans added'
                adaptations[key]={'duplicate_evidence_ids_removed':removed,'original_raw_preserved':str(p.relative_to(ROOT))}
        reused[key]=r
    config['reused_outputs']={k:v['reused_from'] for k,v in reused.items()}
    config['deterministic_set_adaptations']=adaptations
    # Reuse policy is part of the live binding as well.
    if config_file.exists() and load_json(config_file)!=config:raise ValueError('Candidate reuse binding differs')
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
    # Durable batches; do not reserve the entire queue ahead of dispatch.
    for start in range(0,len(requests),8):
        for f,h in config['code'].items():
            if sha(ROOT/f)!=h:raise ValueError('Live source binding changed: '+f)
        batch=requests[start:start+8]
        fresh=[r for r in batch if r['source'] not in reused]
        results=dispatch_many(ledger,fresh,location/'raw',concurrency=8) if fresh else []
        mapping={r['source']:v for r,v in zip(fresh,results)}
        for row in records[start:start+8]:
            result=reused.get(row['key'],mapping.get(row['key']))
            complete.append({'source':row['key'],'dataset':row['dataset'],'split':split,
                'public_sha256':row['runtime_public_sha256'],'result':result})
        write_json(location/'results.json',complete)
        write_json(location/'status.json',{'completed':len(complete),'total':len(records),'last_batch':start//8,
                     'finish_counts':{f:sum(x['result'].get('finish')==f for x in complete) for f in ('stop','length',None)}})
        print(json.dumps({'candidate_sources':len(complete),'total':len(records)},ensure_ascii=False),flush=True)
    write_json(location/'complete.json',{'sources':len(complete),'config_sha256':sha(config_file),
               'not_method_validation':True,'goal_complete':False})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stage',required=True);p.add_argument('--split',choices=('train','dev'),required=True)
    p.add_argument('--checkpoint',required=True);p.add_argument('--alias',default='common')
    p.add_argument('--out',default='artifacts/lsl_mixed256_20261110');a=p.parse_args()
    generate((ROOT/a.out).resolve(),Path(a.checkpoint).resolve(),a.stage,a.split,a.alias)
