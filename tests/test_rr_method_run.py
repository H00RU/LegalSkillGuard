"""Controller-only fixed128/8-batch recovery and six-arm DEV isolation.

All fixtures and responses are invented in tmp_path. These tests exercise the
real persistent ledger and controller; they are not research model evidence.
"""
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import sqlite3
import pytest

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_run import MethodRun


def setup(tmp_path,monkeypatch):
    import legal_skill_guard.rr.method_run as module
    banks=['OpenExempt','RuleArena_Airline','SARA_v2_Binary','ProofWriter_OWA_depth5','ContractNLI']
    sources={};grades={};packets={};hashes={}
    for partition in ('train','dev'):
        rows=[];labels={}
        for bank in banks:
            count=(32 if bank=='OpenExempt' else 24) if partition=='train' else 8
            for i in range(count):
                public={'offline_public_only':str(i)};key=f'{bank}:offline_{partition}_{i}'
                rows.append({'key':key,'dataset':bank,'public':public,'content_hash':digest(public)})
                labels[key]={'targets':{'EC':{},'EV':{}}} if bank=='OpenExempt' else {
                    'answer':0 if bank=='RuleArena_Airline' else 'True' if bank=='ProofWriter_OWA_depth5' else 'Entailment'}
                labels[key]['private_marker']='GRADING_NEVER_IN_PROMPTS'
        sources[partition]=rows;grades[partition]=labels
        for kind,value in [('public',{'split':partition,'contains_gold_or_reference_program':False,'sources':rows}),
                           ('grading',{'split':partition,'never_to_actor_or_teacher':True,'sources':labels})]:
            rel=f'data/packets/rr_v2/public_{partition}.json' if kind=='public' else f'data/packets/rr_v2/grading_only/{partition}.json'
            path=tmp_path/rel;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            hashes[kind+'_'+partition]=hashlib.sha256(path.read_bytes()).hexdigest()
    manifest={'packet_sha256':hashes};manifest_path=tmp_path/'manifest.json';manifest_path.write_text(json.dumps(manifest))
    book=tmp_path/'original.sqlite3'
    with sqlite3.connect(book) as db:
        db.execute('create table meta (key text primary key,value text)')
        db.execute('insert into meta values (?,?)',('spec',json.dumps({'origin':'preserved offline original ledger'})))
        db.execute('create table calls (id text primary key,role,purpose,bucket,source,request_hash,status,reserved_at,result)')
        db.execute('create table oracle_views (source,view_hash,reserved_at,primary key(source,view_hash))')
        db.execute('insert into calls values (?,?,?,?,?,?,?,?,?)',('old_failed','executor','old','old','old','old','failed',0,'{}'))
    stage=tmp_path/'artifacts/rr_method_runtime_20261107/controller_fixture';stage.mkdir(parents=True)
    config={'executor':{'enable_thinking':False,'model':'offline-fixture'},'teacher':{},'oracle_artifacts':'offline_oracles'}
    lock={'executor_config':config['executor'],'selected_thinking':False,'repeat_ON_OFF_sweep':False,
          'current_contract_main_path_passes':0,'does_not_override_original_engineering_block_or_claim_readiness':True}
    seal={'executor_configuration_lock':lock,'executor_configuration_lock_hash':digest(lock),
        'run_id':'controller_fixture','files':{},'code_hash':'offline_code','config':config,
        'source_manifest':'manifest.json','source_manifest_hash':digest(manifest),
        'ledger_path':'original.sqlite3','authorization_hash':'offline_current_authorization',
        'sources':{part:[s['key'] for s in rows] for part,rows in sources.items()},
        'thinking_sources':[s['key'] for bank in banks for s in [s for s in sources['train'] if s['dataset']==bank][:4]]}
    immutable_json(stage/'seal.json',seal)
    monkeypatch.setattr(module,'science_files',lambda root:{})
    class Executor:
        def __init__(self,ledger,stage,config):self.ledger,self.config=ledger,config
        def generate(self,call_id,*,source,purpose,messages,thinking,schema):
            assert 'GRADING_NEVER_IN_PROMPTS' not in json.dumps(messages)
            request={'messages':messages,'thinking':thinking,'schema':schema}
            reserved=self.ledger.reserve(call_id,role='executor',purpose=purpose,source=source,request=request)
            if not reserved['dispatch']:return reserved['result']
            result={'content':'{"offline":true}','request_hash':reserved['request_hash'],
                'usage':{'prompt_tokens':2 if thinking else 1,'completion_tokens':1},
                'elapsed_seconds':.02 if thinking else .01,'reasoning_content':'offline trace' if thinking else None}
            self.ledger.finish(call_id,status='completed',result=result);return result
        def tokenize(self,messages,*,thinking):return {'count':1,'tokens':[int(thinking)]}
    class Teacher:
        def __init__(self,ledger,stage,config):self.ledger=ledger
        def summarize(self,call_id,*,source_ids,system_prompt,user_prompt,output_schema):
            assert 'GRADING_NEVER_IN_PROMPTS' not in user_prompt
            request={'source_ids':source_ids,'system':system_prompt,'user':user_prompt,'schema':output_schema}
            reserved=self.ledger.reserve(call_id,role='teacher',purpose='method_train_compile',source=source_ids[0],request=request)
            if not reserved['dispatch']:return reserved['result']
            result={'value':{'patterns':[],'notes':'offline controller fixture'}}
            self.ledger.finish(call_id,status='completed',result=result);return result
    def predict(source,*,generate,**kwargs):
        raw=generate([{'role':'user','content':json.dumps(source['public'])}],purpose='parse',step=0,schema={'type':'object'})
        result={'answer':None,'certificate_status':'translation_unresolved','program_status':'offline_controller_fixture',
            'A_main_path_executed':False,'B_main_path_executed':False,'fallback_used':False,'structural_pass':True}
        return {'result':result,'program':None,'observation_rows':[],
            'history':[result],'calls':[{'raw_content':raw['content'],'request_hash':raw['request_hash'],'analysis':result,
                'usage':raw['usage'],'elapsed_seconds':raw['elapsed_seconds'],
                'reasoning_content_present':bool(raw['reasoning_content'])}]}
    pattern={'fields':['entity_equality'],'graphs':[{'op':'join_on','inputs':[{'slot':'slot0'},{'slot':'slot1'}],
        'params':{'keys':['column0']}}],'basis':'observed_source_collisions','universal_semantic_equivalence_claim':False}
    monkeypatch.setattr(module,'MethodExecutor',Executor);monkeypatch.setattr(module,'MethodTeacher',Teacher)
    monkeypatch.setattr(module,'predict_source',predict)
    monkeypatch.setattr(module,'learn_source_interfaces',lambda *args,**kwargs:{'status':'offline_fixture',
        'oracle_views':[],'learned_pattern':pattern,'candidate_checks':[]})
    monkeypatch.setattr(module,'_fit_horn_examples',lambda *args:([],0))
    run=MethodRun(tmp_path,'controller_fixture')
    assert run.selected() is False
    return run,sources,book


def test_fixed128_shared_build_freezes_prefix_and_resumes_without_a_new_physical_call(tmp_path,monkeypatch):
    run,sources,book=setup(tmp_path,monkeypatch)
    result=run.build();assert result['sources']==128 and result['batches']==8
    first=json.loads((run.stage/'build/B1.frozen.json').read_text())['content']
    last=json.loads((run.stage/'build/B8.frozen.json').read_text())['content']
    assert first['patterns'][0]['evidence_sources']==[s['key'] for s in sources['train'][:16]]
    assert last['patterns'][0]['evidence_sources']==[s['key'] for s in sources['train']]
    with sqlite3.connect(book) as db:
        before={t:db.execute('select * from '+t).fetchall() for t in ('calls','meta','oracle_views')}
        assert db.execute("select count(*) from calls where role='executor'").fetchone()[0]==129
        assert db.execute("select count(*) from calls where role='teacher'").fetchone()[0]==8
    assert run.build()==result
    with sqlite3.connect(book) as db:assert before=={t:db.execute('select * from '+t).fetchall() for t in before}
    assert json.loads((run.stage/'build/state.json').read_text())['complete_sources']==128
    material=json.loads(next((run.stage/'build/arm_shared_material').glob('*.json')).read_text())
    assert len({row['shared_material_hash'] for row in material.values()})==1
    path=run.stage/'build/B1.frozen.json';frozen=json.loads(path.read_text())
    frozen['content']['patterns'][0]['evidence_sources'].append(sources['train'][-1]['key'])
    frozen['sha256']=digest(frozen['content']);path.write_text(json.dumps(frozen))
    completion_path=run.stage/'build/completion.json';completion=json.loads(completion_path.read_text())
    completion['frozen_files']['B1.frozen.json']=hashlib.sha256(path.read_bytes()).hexdigest()
    completion_path.write_text(json.dumps(completion))
    with pytest.raises(ValueError,match='future source prefix'):run.verify_build()


def test_locked_OFF_does_not_repeat_the_comparison_or_promote_its_failures_to_readiness(tmp_path,monkeypatch):
    run,_,book=setup(tmp_path,monkeypatch)
    with sqlite3.connect(book) as db:before=db.execute('select * from calls').fetchall()
    assert run.selected() is False
    assert run.seal['executor_configuration_lock']['current_contract_main_path_passes']==0
    assert not (run.stage/'thinking').exists()
    with sqlite3.connect(book) as db:assert db.execute('select * from calls').fetchall()==before
    run.seal['executor_configuration_lock']['selected_thinking']=True
    with pytest.raises(ValueError,match='configuration lock'):run.selected()


def test_actual_configuration_lock_uses_preserved_c6_evidence_without_new_generation():
    from legal_skill_guard.rr.method_run import load_executor_lock
    root=Path(__file__).resolve().parents[1]
    config=json.loads((root/'configs/rr_v2_preflight.json').read_text())['executor']
    lock=load_executor_lock(root,config)
    assert lock['selected_thinking'] is False and lock['current_contract_main_path_passes']==0
    config={**config,'temperature':0.123}
    with pytest.raises(ValueError,match='configuration'):load_executor_lock(root,config)


def test_DEV_opens_labels_only_after_all_six_times40_predictions_are_saved(tmp_path,monkeypatch):
    run,sources,book=setup(tmp_path,monkeypatch);run.build()
    packet=run.packet;opened=[]
    def barrier(kind,partition):
        if kind=='grading' and partition=='dev':
            paths=list((run.stage/'dev/predictions').glob('*/*.json'))
            assert len(paths)==6*40;opened.append(len(paths))
        return packet(kind,partition)
    monkeypatch.setattr(run,'packet',barrier)
    result=run.dev()
    assert opened==[240] and result['outputs_per_arm']==48
    assert all(score['outputs']==48 for score in result['scores'].values())
    with sqlite3.connect(book) as db:before=db.execute('select * from calls').fetchall()
    assert run.dev()==result
    with sqlite3.connect(book) as db:assert db.execute('select * from calls').fetchall()==before
