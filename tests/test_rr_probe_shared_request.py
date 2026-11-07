"""The probe prepares the production M11 request, including repair diagnostics."""
import hashlib
import json
from pathlib import Path
import sqlite3

import experiments.rr_v2_source_probe as probe
from legal_skill_guard.rr.controls import ARMS
from legal_skill_guard.rr.source_inference import _compiler_request
from legal_skill_guard.rr.source_program import program_schema


def test_executor_probe_prepares_exact_shared_repair_messages(tmp_path, monkeypatch):
    root=Path(__file__).resolve().parents[1]
    fixture=json.loads((root/'tests/fixtures/rr_actual_probe_v4_expressions.json').read_text())
    source=next(s for s in json.loads((root/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==fixture['source'])
    program=json.loads(fixture['raw_content']);before=json.dumps(program,sort_keys=True)
    config={'compiler_role':'executor','library':None,'executor':{
        'enable_thinking':False,'context_tokens':32768,'max_tokens':8192}}
    stage=tmp_path/'artifacts/rr_method_runtime_20261107/shared_request'
    for directory in ('reports/rr_method_runtime_20261107','docs/rr_v2'):
        (tmp_path/directory).mkdir(parents=True)
    (tmp_path/probe.OFFLINE_RECEIPT).write_text(json.dumps({'exit_code':0,'network_blocked':True,'files':{}}))
    (tmp_path/'docs/rr_v2/method_runtime_authorization_20261107.json').write_text('{}')
    with sqlite3.connect(tmp_path/'book.sqlite3') as db:db.execute('create table calls (status)')
    monkeypatch.setattr(probe,'science_files',lambda root:{})
    monkeypatch.setattr(probe,'load',lambda *a,**k:({'ledger_path':'book.sqlite3'},{},source,config,{},stage))
    monkeypatch.setattr(probe,'executor_candidate',lambda *a,**k: (
        {'system':'previous','user':'previous','schema':program_schema(source)},program,
        {'paid_call_id':fixture['call_id'],'program_hash':'unchanged fixture','new_model_calls':0}))
    class Readonly:
        def __init__(self,*args):pass
        def tokenize(self,*args,**kwargs):return {'count':100}
    monkeypatch.setattr(probe,'MethodExecutor',Readonly)
    prepared=probe.prepare(tmp_path,'shared_request',executor_repair_origin='actual_v4')
    assert prepared['new_model_calls']==0
    seal=json.loads((stage/'seal.json').read_text())
    messages,schema,_=_compiler_request(source,None,ARMS['M11'],program,None,
        Readonly().tokenize,config['executor'],False)
    assert (seal['system'],seal['user'])==(messages[0]['content'],messages[1]['content'])
    assert ' Compilation policy: ' in seal['system']
    assert seal['schema_order_sha256']==hashlib.sha256(json.dumps(schema,ensure_ascii=False).encode()).hexdigest()
    feedback=json.loads(seal['user'])['validation_feedback']
    assert not feedback['candidate_modified'] and not feedback['grading_information_used']
    assert all('cited_text' not in i.get('actual',{}) for i in feedback['issues'] if isinstance(i.get('actual'),dict))
    assert json.dumps(program,sort_keys=True)==before
