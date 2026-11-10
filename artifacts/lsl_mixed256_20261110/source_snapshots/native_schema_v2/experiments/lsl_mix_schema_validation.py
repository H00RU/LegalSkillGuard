"""Two targeted TRAIN retries after real native-format failures.

Changes are the shared explicit native schema/prompt, with all TRAIN targets
and xgrammar compilations checked offline. No same-input unchanged retry.
"""
from pathlib import Path
import json
import sys
import time

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.lsl.data import load_json,sha,write_json
from legal_skill_guard.lsl.native_training import prompt
from legal_skill_guard.lsl.native_schema import schema
from legal_skill_guard.lsl.physical import dispatch_many,payload
from legal_skill_guard.lsl.composition_data import b0_to_graph
from legal_skill_guard.rr.horn import Atom,Rule,closure


def decode_horn(program):
    def atom(value):
        if not isinstance(value,list) or len(value)!=3 or not isinstance(value[0],str) or not isinstance(value[1],list) or not all(isinstance(t,str) for t in value[1]) or type(value[2]) is not bool:raise ValueError('Invalid native Horn atom tuple')
        return Atom(value[0],tuple(value[1]),value[2])
    facts={atom(t) for t in program['facts']}
    rules=[Rule(tuple(atom(t) for t in r['body']),atom(r['head']),'predicted_rule_'+str(i)) for i,r in enumerate(program['rules'])]
    return facts,rules,atom(program['query'])


def main():
    out=ROOT/'artifacts/lsl_mixed256_20261110';records=load_json(out/'open_dataset.json')['records']
    prior=load_json(out/'common_native_smoke.json');ids={r['dataset']:r['source'] for r in prior}
    selected=[next(r for r in records if r['key']==ids[d]) for d in ('NormBench','ProofWriter_OWA_depth5')]
    run='LSG-MIX256-native-schema-v2';files=['experiments/lsl_mix_schema_validation.py','legal_skill_guard/lsl/native_training.py','legal_skill_guard/lsl/native_schema.py','legal_skill_guard/lsl/physical.py']
    config={'run_id':run,'common_checkpoint_sha256':sha(out/'common_native_initialization/step_0032/adapter_model.safetensors'),
        'changes':['Explicit English norm-kind/Chinese tag enums','Exact native Horn tuple and variable examples','Shared native JSON grammar; format only, not semantic correction'],
        'offline_evidence':{'native_TRAIN_targets_schema_valid':256,'native_grammars_xgrammar_compiled':5},
        'code':{f:sha(ROOT/f) for f in files},'manifest_sha256':load_json(out/'manifest.json')['runtime_sha256']}
    write_json(out/'native_schema_v2_config.json',config)
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=run,
        binding={'code_hash':digest(config['code']),'config_hash':digest(config)},
        sources={s:[r['key'] for r in records if r['split']==s] for s in ('train','dev')},
        authorization_hash=sha(ROOT/'reports/legal_five_dataset_amendment_20261110/protocol.json'),
        question='Correct concrete native-format incompatibilities before fixed MIX256 comparison; no semantic labels used for output repair')
    requests=[]
    for r in selected:
        requests.append({'call_id':run+':'+r['dataset'],'source':r['key'],'purpose':'method_primitive_observation',
                         'request':{'thinking':False,'checkpoint':config['common_checkpoint_sha256'],
                                    'payload':payload(prompt(r),schema(r['dataset'],r['public']))}})
    results=dispatch_many(ledger,requests,out/'native_schema_v2_raw',concurrency=2)
    import jsonschema
    checks=[]
    for r,result in zip(selected,results):
        checked={'dataset':r['dataset'],'source':r['key'],'finish':result.get('finish'),'fallback':False}
        try:
            jsonschema.Draft202012Validator(schema(r['dataset'],r['public'])).validate(result['parsed'])
            checked['schema_valid']=True
            if r['dataset']=='NormBench':
                graph=b0_to_graph(result['parsed'],r['public']['rule_text'],r['key'],r['family_id'])
                from legal_skill_guard.lsl.composition_data import gold_graph
                from legal_skill_guard.lsl.evaluation import score_source
                checked['native_execution_valid']=True;checked['native_structure']=score_source(graph,gold_graph(r['native_record']))
            else:
                facts,rules,query=decode_horn(result['parsed']['program']);execution=closure(facts,rules,query)
                checked.update(native_execution_valid=execution['status']=='closure_complete',executed_answer=execution['answer'],
                               native_expected=r['grade']['answer'],executed_native_correct=execution['answer']==r['grade']['answer'],
                               neural_readout_answer=result['parsed'].get('answer'))
        except Exception as e:checked.update(schema_or_execution_error=type(e).__name__+': '+str(e))
        checks.append(checked)
    write_json(out/'native_schema_v2_results.json',{'config':config,'results':checks,'goal_complete':False})
    print(json.dumps(checks,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
