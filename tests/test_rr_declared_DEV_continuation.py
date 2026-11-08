"""Actual paid bytes may continue only an explicitly sealed compatible DEV."""
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_client import MethodExecutor
from legal_skill_guard.rr.method_run import MethodRun,dev_reuse_origin
from legal_skill_guard.rr.pal_frontend import pal_schema

ROOT=Path(__file__).resolve().parents[1]


def fixture(tmp_path):
    stage=ROOT/'artifacts/rr_method_runtime_20261107/reference_pal_airline2_v12_20261108'
    component=json.loads((stage/'seal.json').read_text());source=component['source']
    origin=stage/'calls'/digest(stage.name+':parse:0')
    paid=tmp_path/'paid';paid.mkdir()
    response=json.loads((origin/'result.json').read_text());response['artifact_directory']=str(paid)
    parent='declared_prior';cid=parent+':dev:M00:'+digest(source['key'])+':0'
    request=json.loads((origin/'request.json').read_text());request.update(id=cid,purpose='method_dev')
    (paid/'request.json').write_text(json.dumps(request));(paid/'result.json').write_text(json.dumps(response))
    (paid/'wire_request.json').write_bytes((origin/'wire_request.json').read_bytes())
    book=tmp_path/'ledger.sqlite3'
    with sqlite3.connect(book) as db:
        db.execute('create table calls(id,role,source,status,purpose,reserved_at,request_hash,result)')
        db.execute('insert into calls values(?,?,?,?,?,?,?,?)',(cid,'executor',source['key'],'completed',
            'method_dev',0,response['request_hash'],json.dumps(response)))
    seal={'run_id':parent,'sources':{'train':[],'dev':[source['key']]},
        'config':{'executor':component['config']['executor']},'source_manifest_hash':'fixed_manifest',
        'data_hash':'fixed_data','test_authorized':False}
    parent_path=tmp_path/'artifacts/rr_method_runtime_20261107'/parent/'seal.json'
    parent_path.parent.mkdir(parents=True);parent_path.write_text(json.dumps(seal))
    run=MethodRun.__new__(MethodRun);run.root=tmp_path;run.run_id='current_binding'
    run.seal={**deepcopy(seal),'run_id':run.run_id,'ledger_path':book.name}
    run.seal['dev_raw_reuse_from']=dev_reuse_origin(tmp_path,run.run_id,parent,sources=seal['sources'],
        config=seal['config'],manifest_hash=seal['source_manifest_hash'],data_hash=seal['data_hash'])
    executor=MethodExecutor(None,tmp_path,component['config']['executor'])
    messages=json.loads(base64.b64decode(json.loads((paid/'wire_request.json').read_text())['body_b64']))['messages']
    return run,executor,source,messages,pal_schema(),parent_path,cid,response


def test_declared_matching_parent_reuses_only_its_literal_paid_response(tmp_path):
    run,client,source,messages,schema,path,cid,response=fixture(tmp_path)
    raw=run.paid_executor_response(client,source,messages,schema,False,dispatch_purpose='method_dev')
    assert raw['physical_origin_call_id']==cid and raw['content']==response['content']
    assert raw['new_physical_requests']==0
    del run.seal['dev_raw_reuse_from']
    assert run.paid_executor_response(client,source,messages,schema,False,dispatch_purpose='method_dev') is None
    with sqlite3.connect(tmp_path/'ledger.sqlite3') as db:assert db.execute('select count(*) from calls').fetchone()[0]==1


@pytest.mark.parametrize('field',['sources','config','source_manifest_hash','data_hash','test_authorized'])
def test_declared_parent_scope_config_data_or_test_authorization_mismatch_fails_closed(tmp_path,field):
    run,client,source,messages,schema,path,cid,response=fixture(tmp_path)
    parent=json.loads(path.read_text());parent[field]='changed';path.write_text(json.dumps(parent))
    with pytest.raises(ValueError,match='differs'):
        run.paid_executor_response(client,source,messages,schema,False,dispatch_purpose='method_dev')


def test_changed_parent_seal_or_current_wire_cannot_supply_a_response(tmp_path):
    run,client,source,messages,schema,path,cid,response=fixture(tmp_path)
    client.config={**client.config,'seed':client.config['seed']+1}
    assert run.paid_executor_response(client,source,messages,schema,False,dispatch_purpose='method_dev') is None
    parent=json.loads(path.read_text());parent['extra']='tampered';path.write_text(json.dumps(parent))
    with pytest.raises(ValueError,match='seal changed'):
        run.paid_executor_response(client,source,messages,schema,False,dispatch_purpose='method_dev')
