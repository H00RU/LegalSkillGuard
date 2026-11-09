"""Bounded, separately recorded real validation of the selected static route."""
import os
os.environ['HF_HUB_OFFLINE']='1'
os.environ['TRANSFORMERS_OFFLINE']='1'
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from time import perf_counter

from transformers import AutoTokenizer
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_client import MethodExecutor, MethodTeacher
from legal_skill_guard.rr.method_ledger import MethodLedger
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_execution import prepare_followup, accept_followup, assess_source

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v10_20261109'
RUN='efficacy_static_v1_20261109'
STAGE=ROOT/'artifacts/rr_method_efficacy_20261109'/RUN


def inputs(ordinal,tokenizer,seal):
    source_id=seal['sources']['train'][ordinal-1]
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==source_id)
    prefix=SkillLibrary(stage='formal_train')
    for key in seal['sources']['train'][:ordinal-1]:
        r=json.loads((OLD/'build/sources'/(digest(key)+'.json')).read_text())
        if r['learning'].get('learned_pattern'):prefix.add(r['learning']['learned_pattern'],source=key)
        for t in r.get('compiler_learning',{}).get('templates',[]):prefix.add_compiler_template(t)
    library=prefix.export()
    record=json.loads((OLD/'build/sources'/(digest(source_id)+'.json')).read_text())
    assert digest(library)==record['library_before_hash']
    state=json.loads(json.loads((OLD/'build/journals'/digest(source_id)/'state0.json').read_text())['state_json'])
    assert state['compiled_valid']
    compiled=compile_source(source,state['program'],library=library)
    def count(messages,*,thinking):
        assert thinking is False
        return {'count':len(tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,enable_thinking=False))}
    before=perf_counter()
    prepared=prepare_followup(compiled,state['observed'],compilation='static_dependencies',tokenize=count,
        thinking=False,request_config=seal['config']['executor'],library=library,pal_fragments=True)
    return source,compiled,state,library,prepared,perf_counter()-before


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['executor','teacher_airline']);args=p.parse_args()
    old=json.loads((OLD/'seal.json').read_text());files=science_files(ROOT)
    binding={'code_hash':digest(files),'config_hash':digest(old['config'])}
    protocol=ROOT/'reports/method_efficacy_20261109/protocol.md'
    seal={'run_id':RUN,'files':files,'binding':binding,'config':old['config'],'sources':old['sources'],
        'protocol_sha256':__import__('hashlib').sha256(protocol.read_bytes()).hexdigest(),
        'new_goal_baseline_counts':{'executor':1334,'teacher':40},'previous_run_unchanged':OLD.name,
        'targets_TRAIN_ordinals':[79,7],'TEST_authorized':False,'library_updates_authorized_in_this_diagnostic':False}
    immutable_json(STAGE/'seal.json',seal)
    ledger=MethodLedger(ROOT/'artifacts/rr_v2_preflight/research_ledger.sqlite3',run_id=RUN,
        binding=binding,sources=old['sources'],authorization_hash=seal['protocol_sha256'],
        question='Does static scope-safe slicing preserve reliable legal completion and reduce Airline interface burden? Same-contract teacher control only on Airline if executor fails.')
    tokenizer=AutoTokenizer.from_pretrained(old['config']['executor']['model_root'],local_files_only=True)
    executor=MethodExecutor(ledger,STAGE,old['config']['executor'])
    teacher=MethodTeacher(ledger,STAGE,old['config']['teacher'])
    targets=[79,7] if args.action=='executor' else [7]
    for ordinal in targets:
        result_path=STAGE/f'{args.action}_train{ordinal}.json'
        if result_path.exists():
            print(json.dumps(json.loads(result_path.read_text()),ensure_ascii=False),flush=True);continue
        source,compiled,state,library,prepared,planning=inputs(ordinal,tokenizer,old)
        immutable_json(STAGE/f'prepared_train{ordinal}.json',prepared)
        if args.action=='executor':
            executor.readiness()
            wire=executor.generate(f'{RUN}:executor:train{ordinal}:0',source=source['key'],
                purpose='method_train_synthesis',messages=prepared['messages'],schema=prepared['schema'],thinking=False)
            response=wire['content']
        else:
            first=json.loads((STAGE/'executor_train7.json').read_text())
            assert first['status']!='completion_stable', 'Teacher capability control is conditional on the executor failure'
            wire=teacher.summarize(f'{RUN}:teacher:train7:0',source_ids=[source['key']],
                system_prompt=prepared['messages'][0]['content'],user_prompt=prepared['messages'][1]['content'],
                output_schema=prepared['schema'])
            response=wire['value']
        start=perf_counter()
        try:
            if isinstance(response,str):response=json.loads(response)
            updated,observed=accept_followup(compiled,prepared,response,state['observed'],library=library)
            assessed=assess_source(updated,observed,compilation='static_dependencies')
            result={'status':assessed['status'],'answer':assessed['answer'],'assessment':assessed,
                'accepted_program':updated['program'],'accepted_observations':updated['accepted_observation_rows']}
        except Exception as exc:
            result={'status':'rejected_response','answer':None,'error_type':type(exc).__name__,'error':str(exc)}
        result.update(captured_utc=datetime.now(timezone.utc).isoformat(),source=source['key'],
            current_stage_action=args.action,TRAIN_ordinal=ordinal,raw_response=response,
            request_input_tokens=prepared['input_tokens'],planning_seconds=planning,
            acceptance_execution_seconds=perf_counter()-start,physical_response=wire,
            previous_actual_response_not_imported=True,source_semantics_not_inferred_from_stability=True,
            original_labels_opened=False,frozen_libraries_not_updated=True)
        immutable_json(result_path,result)
        print(json.dumps({k:v for k,v in result.items() if k not in {'assessment','accepted_program','physical_response','raw_response'}},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
