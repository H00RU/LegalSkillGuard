"""Paid response replays through the actual common build/DEV inference entry."""
from copy import deepcopy
import base64
import json
import sqlite3
from pathlib import Path

from legal_skill_guard.rr.coverage import digest
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
    assert run.paid_executor_response(executor,seal['source'],seal['initial_messages'],seal['schema'],False) is None
    schema=pal_schema()
    physical=json.loads(base64.b64decode(json.loads((stage/'calls'/digest(cid)/'wire_request.json').read_text())['body_b64']))
    messages=physical['messages']
    value=run.paid_executor_response(executor,seal['source'],messages,schema,False)
    assert value['content']==raw['content'] and value['physical_origin_call_id']==cid
    assert value['new_physical_requests']==0 and value['finish_reason']=='length'
    changed=deepcopy(messages);changed[-1]['content']+=' changed'
    assert run.paid_executor_response(executor,seal['source'],changed,schema,False) is None
    altered={**raw,'content':'invented replacement'}
    with sqlite3.connect(book) as db:db.execute('update calls set result=?',(json.dumps(altered),))
    with pytest.raises(ValueError,match='differs from physical ledger'):
        run.paid_executor_response(executor,seal['source'],messages,schema,False)
