"""Two fixed TRAIN source-program pilots; same common weights, thinking OFF."""
from pathlib import Path
import json
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.lsl.data import load_json,write_json,sha
from legal_skill_guard.lsl.physical import dispatch_many,payload
from legal_skill_guard.lsl.scalar_proposals import proposal_prompt,proposal_schema,analyze


def main():
    out=ROOT/'artifacts/lsl_mixed256_20261110';records=load_json(out/'open_dataset.json')['records'];manifest=load_json(out/'manifest.json')
    run='LSG-MIX256-scalar-source-pilot-v2'
    selected=[next(r for r in records if r['key']==manifest['datasets'][d]['train'][0]['key']) for d in ('SARA_v2_Binary','RuleArena_Airline')]
    files=['experiments/lsl_mix_scalar_prototype.py','legal_skill_guard/lsl/scalar_proposals.py','legal_skill_guard/lsl/safe_program.py','legal_skill_guard/lsl/local_credit.py','legal_skill_guard/lsl/physical.py']
    config={'run_id':run,'selection':'first fixed manifest TRAIN source in each scalar task, no outcome selection',
        'checkpoint_sha256':sha(out/'common_native_initialization/step_0032/adapter_model.safetensors'),
        'code':{f:sha(ROOT/f) for f in files},'manifest_sha256':manifest['runtime_sha256'],'thinking':False,
        'question':'After real combined-output failures, can unindexed source and program-only PAL-style generation produce a complete executable native program?',
        'changes':['Source identifiers/alternative fields removed from program generation','Only current-case relevant branches requested','Undefined-name rejection reproduced on actual v1 response before real retry'],
        'prior_failed_attempts_preserved':'scalar_source_pilot_v1_results.json'}
    write_json(out/'scalar_source_pilot_v2_config.json',config)
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,
       binding={'code_hash':digest(config['code']),'config_hash':digest(config)},
       sources={s:[r['key'] for r in records if r['split']==s] for s in ('train','dev')},
       authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),question=config['question'])
    requests=[]
    for r in selected:
        messages,source,index=proposal_prompt(r)
        requests.append({'call_id':run+':'+r['dataset'],'source':r['key'],'purpose':'method_primitive_observation',
                         'request':{'thinking':False,'checkpoint':config['checkpoint_sha256'],
                                    'payload':payload(messages,proposal_schema(index))}})
    results=dispatch_many(ledger,requests,out/'scalar_source_pilot_v2_raw',concurrency=2)
    checks=[]
    for r,result in zip(selected,results):
        if result.get('parsed') is None:checks.append({'dataset':r['dataset'],'source':r['key'],'program_valid':False,'error':result.get('error') or result.get('parse_error'),'finish':result.get('finish')});continue
        checks.append(analyze(r,result['parsed']))
    write_json(out/'scalar_source_pilot_v2_results.json',{'config':config,'results':checks,'actual_training_gradient_from_local_tables_yet':False,'goal_complete':False})
    print(json.dumps([{k:v for k,v in r.items() if k not in ('local_tables','M2_square')} for r in checks],ensure_ascii=False),flush=True)


if __name__=='__main__':main()
