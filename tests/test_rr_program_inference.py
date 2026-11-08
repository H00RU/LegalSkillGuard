"""Paid response replays through the actual common build/DEV inference entry."""
from copy import deepcopy
import base64
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.program_inference import predict_source
from legal_skill_guard.rr.method_run import MethodRun
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.pal_frontend import pal_schema,pal_prompt
import pytest

ROOT=Path(__file__).resolve().parents[1]


def replay(run_id,tmp_path,interrupt_before_dispatch=False):
    stage=ROOT/'artifacts/rr_method_runtime_20261107'/run_id
    seal=json.loads((stage/'seal.json').read_text());saved=json.loads((stage/'result.json').read_text())
    config=seal['config'];wires=[json.loads((stage/'calls'/digest(run_id+':parse:'+str(i))/'result.json').read_text()) for i in range(len(saved['attempts']))]
    count=[];captured=[]
    def generate(messages,*,purpose,step,schema):
        request=json.loads((stage/('request'+str(step)+'.json')).read_text())
        assert messages==request['messages'] and schema==request['schema']
        if interrupt_before_dispatch and step==0:
            body=json.dumps(MethodExecutor(None,tmp_path,config['executor']).payload(messages=messages,thinking=False,schema=schema),ensure_ascii=False)
            if not captured:captured.append(body);raise KeyboardInterrupt
            assert body==captured[0]
        count.append(step);return wires[step]
    kwargs=dict(arm='M11',library=config['library'],generate=generate,
        tokenize=lambda messages,thinking:{'count':len(json.dumps(messages))},request_config=config['executor'],
        thinking=False,partition='train',controlled_shortcut=False,journal=tmp_path/'journal')
    if interrupt_before_dispatch:
        with pytest.raises(KeyboardInterrupt):predict_source(seal['source'],**kwargs)
    out=predict_source(seal['source'],**kwargs)
    assert out['result']['answer']==saved['result']['answer']
    assert out['result']['fallback_used'] is False and out['result']['A_main_path_executed']
    assert predict_source(seal['source'],**kwargs)==out
    assert count==list(range(len(wires)))
    return out


def test_real_paid_logic_program_uses_common_entry_and_recovers_without_dispatch(tmp_path):
    out=replay('reference_atoms_pw9_v3_20261108',tmp_path,interrupt_before_dispatch=True)
    assert out['model_calls']==1 and out['program'] is None
    assert not out['model_horn_program']['missing_units']
    assert out['result']['independent_executor_compilation'] is True


def test_real_paid_legal_instance_and_selected_fact_request_replay_through_build_entry(tmp_path):
    out=replay('reference_instance_sara77_v11_20261108',tmp_path)
    assert out['model_calls']==2 and out['model_horn_code'] is None
    assert out['result']['actual_executor_template_instantiation'] is True
    assert out['translation_actions'][0]['selected']==['s52']


def test_actual_paid_template_is_added_only_at_its_own_source_and_frozen_exactly(tmp_path):
    path='artifacts/rr_method_runtime_20261107/reference_frontend_prior_sara3_template_v8_20261108/compiler_template.json'
    item=json.loads((ROOT/path).read_text());source=item['source']['key']
    run=MethodRun.__new__(MethodRun);run.root=ROOT;run.config={'paid_compiler_materials':[{'path':path,'source':source}]}
    assert run.compiler_learning('another_source')['templates']==[]
    update=run.compiler_learning(source);assert update['new_teacher_calls']==0 and update['templates']==[item]
    library=SkillLibrary(stage='formal_train');before=deepcopy(library.export())
    library.add_compiler_template(update['templates'][0]);assert before.get('compiler_templates') is None
    checkpoint=SkillLibrary(library.patterns,stage='formal_B1',compiler_templates=library.compiler_templates)
    checkpoint.freeze(tmp_path/'B1.json');restored=SkillLibrary.restore(tmp_path/'B1.json')
    assert restored.export()==checkpoint.export() and restored.compiler_templates==[item]


def test_identical_learned_statute_text_is_not_repeated_in_current_generation_context():
    path=ROOT/'artifacts/rr_method_runtime_20261107/reference_instance_sara79_v12_20261108/seal.json'
    seal=json.loads(path.read_text());messages=pal_prompt(seal['source'],seal['config']['library'])
    payload=json.loads(messages[1]['content']);example=payload['earlier_TRAIN_examples'][0]
    assert example['rule_text_and_contexts_are_identical_CURRENT_units_by_id'] is True
    assert len(example['shared_rule_source_ids'])==52 and not any(u['role']=='rule' for u in example['units'])
    assert len([u for u in payload['CURRENT']['units'] if u['role']=='rule'])==52


def test_paid_train_reuse_requires_identical_literal_wire_and_untampered_raw_response(tmp_path):
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_airline2_v12_20261108'
    seal=json.loads((stage/'seal.json').read_text());cid=stage.name+':parse:0'
    raw=json.loads((stage/'calls'/digest(cid)/'result.json').read_text())
    book=tmp_path/'book.sqlite3'
    with sqlite3.connect(book) as db:
        db.execute('create table calls(id,role,source,status,purpose,reserved_at,request_hash,result)')
        db.execute('insert into calls values (?,?,?,?,?,?,?,?)',(cid,'executor',seal['source']['key'],'completed',
            'method_train_synthesis',0,raw['request_hash'],json.dumps(raw)))
    run=MethodRun.__new__(MethodRun);run.root=tmp_path;run.seal={'ledger_path':book.name}
    executor=MethodExecutor(None,tmp_path,seal['config']['executor'])
    # The saved seal is canonical JSON; physical dispatch reconstructs the
    # ordered runtime schema. Semantically equal objects are not literal bytes.
    assert run.paid_executor_response(executor,seal['source'],seal['initial_messages'],seal['schema'],False,dispatch_purpose='method_train_synthesis') is None
    schema=pal_schema()
    physical=json.loads(base64.b64decode(json.loads((stage/'calls'/digest(cid)/'wire_request.json').read_text())['body_b64']))
    messages=physical['messages']
    value=run.paid_executor_response(executor,seal['source'],messages,schema,False,dispatch_purpose='method_train_synthesis')
    assert value['content']==raw['content'] and value['physical_origin_call_id']==cid
    assert value['new_physical_requests']==0 and value['finish_reason']=='length'
    changed=deepcopy(messages);changed[-1]['content']+=' changed'
    assert run.paid_executor_response(executor,seal['source'],changed,schema,False,dispatch_purpose='method_train_synthesis') is None
    altered={**raw,'content':'invented replacement'}
    with sqlite3.connect(book) as db:db.execute('update calls set result=?',(json.dumps(altered),))
    with pytest.raises(ValueError,match='differs from physical ledger'):
        run.paid_executor_response(executor,seal['source'],messages,schema,False,dispatch_purpose='method_train_synthesis')


@pytest.mark.parametrize('reuse',[False,True])
@pytest.mark.parametrize('dispatch_purpose',['method_train_synthesis','method_dev'])
def test_actual_build_dispatch_accepts_direct_python_and_checks_paid_reuse_first(tmp_path,reuse,dispatch_purpose):
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_airline2_v12_20261108'
    seal=json.loads((stage/'seal.json').read_text());source=seal['source']
    executor=MethodExecutor(None,tmp_path,seal['config']['executor'])
    messages=pal_prompt(source,seal['config']['library']);physical=[];lookup=[]
    wire={'content':'unchanged response','finish_reason':'stop'}
    run=MethodRun.__new__(MethodRun);run.verify=lambda:None
    def paid(client,current,msgs,schema,thinking,*,dispatch_purpose):
        lookup.append((current['key'],schema,thinking,dispatch_purpose))
        return wire if reuse else None
    def generate(cid,**kwargs):
        body=executor.payload(messages=kwargs['messages'],thinking=kwargs['thinking'],schema=kwargs['schema'])
        assert 'response_format' not in body
        assert body['chat_template_kwargs']['enable_thinking'] is False
        physical.append((cid,kwargs['source'],kwargs['purpose']));return wire
    executor.generate=generate;run.paid_executor_response=paid
    dispatch=run.dispatcher(SimpleNamespace(),executor,source,'offline',dispatch_purpose,False)
    assert dispatch(messages,purpose='parse',step=0,schema=None)==wire
    assert lookup==[(source['key'],None,False,dispatch_purpose)]
    assert physical==([] if reuse else [('offline:0',source['key'],dispatch_purpose)])


def test_DEV_raw_reuse_excludes_other_runs_partitions_sources_and_changed_payloads(tmp_path):
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_airline2_v12_20261108'
    seal=json.loads((stage/'seal.json').read_text());source=seal['source'];oldcid=stage.name+':parse:0'
    origin=stage/'calls'/digest(oldcid);artifact=tmp_path/'paid';artifact.mkdir()
    raw=json.loads((origin/'result.json').read_text());raw['artifact_directory']=str(artifact)
    cid='offline_run:dev:M00:'+digest(source['key'])+':0'
    request=json.loads((origin/'request.json').read_text());request.update(id=cid,purpose='method_dev')
    (artifact/'request.json').write_text(json.dumps(request))
    (artifact/'result.json').write_text(json.dumps(raw))
    (artifact/'wire_request.json').write_bytes((origin/'wire_request.json').read_bytes())
    book=tmp_path/'book.sqlite3'
    with sqlite3.connect(book) as db:
        db.execute('create table calls(id,role,source,status,purpose,reserved_at,request_hash,result)')
        db.execute('insert into calls values (?,?,?,?,?,?,?,?)',(cid,'executor',source['key'],'completed',
            'method_dev',0,raw['request_hash'],json.dumps(raw)))
    run=MethodRun.__new__(MethodRun);run.root=tmp_path;run.run_id='offline_run'
    run.seal={'ledger_path':book.name,'sources':{'train':[],'dev':[source['key']]}}
    executor=MethodExecutor(None,tmp_path,seal['config']['executor'])
    physical=json.loads(base64.b64decode(json.loads((origin/'wire_request.json').read_text())['body_b64']))
    messages=physical['messages'];schema=pal_schema()
    def lookup():return run.paid_executor_response(executor,source,messages,schema,False,dispatch_purpose='method_dev')
    value=lookup();assert value['physical_origin_call_id']==cid and value['new_physical_requests']==0
    assert value['content']==raw['content'] and value['finish_reason']=='length'
    executor.config={**executor.config,'seed':executor.config['seed']+1}
    assert lookup() is None
    executor.config=seal['config']['executor']
    with sqlite3.connect(book) as db:db.execute('update calls set id=?',('offlineXrun:dev:M00:0',))
    assert lookup() is None  # An underscore must not become a SQL LIKE wildcard.
    with sqlite3.connect(book) as db:db.execute('update calls set id=?,purpose=?',(cid,'method_train_synthesis'))
    assert lookup() is None
    with pytest.raises(BudgetError,match='fixed DEV source'):
        run.paid_executor_response(executor,{'key':'outside'},messages,schema,False,dispatch_purpose='method_dev')
    with sqlite3.connect(book) as db:assert db.execute('select count(*) from calls').fetchone()[0]==1


def test_real_over_budget_repair_keeps_all_source_and_root_error_and_uses_no_extra_call(tmp_path):
    stage=ROOT/'artifacts/rr_method_runtime_20261107/method_runtime_reference_v6_20261109'
    seal=json.loads((stage/'seal.json').read_text());sid=seal['sources']['train'][15]
    record=json.loads((stage/'build/sources'/(digest(sid)+'.json')).read_text())
    source=next(s for s in json.loads((ROOT/'data/packets/rr_v2/public_train.json').read_text())['sources'] if s['key']==sid)
    checkpoint=json.loads((stage/'build/B1.frozen.json').read_text())['content']
    library=SkillLibrary(checkpoint['patterns'],stage='formal_train',compiler_templates=checkpoint['compiler_templates']).export()
    assert digest(library)==record['library_before_hash']
    original=record['prediction']['calls'][0];seen=[]
    def tokenizer(messages,thinking):
        feedback=json.loads(messages[1]['content'])['source_only_feedback']
        # Actual pinned-tokenizer witnesses: 24053 initial, 24595 full
        # diagnostics, 24133 identical source plus the complete root error.
        return {'count':24053 if feedback is None else 24595 if 'source_validation' in feedback else 24133}
    def generate(messages,*,purpose,step,schema):
        payload=json.loads(messages[1]['content']);seen.append(payload)
        if step:
            assert payload['CURRENT']==seen[0]['CURRENT']
            assert 'source_validation' not in payload['source_only_feedback']
            assert payload['source_only_feedback']['error']==original['analysis']['error']['error']
        return {'content':original['raw_content'],'finish_reason':'stop','request_hash':original['request_hash'],
            'usage':original['usage'],'elapsed_seconds':0}
    out=predict_source(source,arm='M11',library=library,generate=generate,tokenize=tokenizer,
        request_config=seal['config']['executor'],thinking=False,partition='train',controlled_shortcut=False)
    assert len(seen)==out['model_calls']==2
    assert out['result']['answer'] is None and not out['result']['A_main_path_executed']
    action=next(a for a in out['translation_actions'] if a.get('kind')=='duplicate_error_diagnostics_omitted_from_prompt_only')
    assert action['full_input_tokens']==24595 and action['dispatched_input_tokens']==24133
