"""Actual paid teacher material may be replayed only with exact request identity."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import pytest

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.method_run import MethodRun


def fixture(tmp_path):
    value=json.loads((Path(__file__).parent/'fixtures/rr_actual_teacher_B1_reuse.json').read_text())
    assert hashlib.sha256(value['request_json'].encode()).hexdigest()==value['request_sha256']
    assert hashlib.sha256(value['result_json'].encode()).hexdigest()==value['result_sha256']
    cid=value['call_id'];origin=cid.split(':build:teacher:',1)[0]
    run=object.__new__(MethodRun);run.root=tmp_path;run.stage=tmp_path/'artifacts/rr_method_runtime_20261107/current'
    run.seal={'ledger_path':'book.sqlite3'}
    path=run.stage.parent/origin/'build/calls'/digest(cid);path.mkdir(parents=True)
    (path/'request.json').write_text(value['request_json']);(path/'result.json').write_text(value['result_json'])
    with sqlite3.connect(tmp_path/'book.sqlite3') as db:
        db.execute('create table calls (id,role,purpose,status,reserved_at,result)')
        db.execute('insert into calls values (?,?,?,?,?,?)',(cid,'teacher','method_train_compile','completed',1,value['result_json']))
    return run,json.loads(value['request_json']),value,path


def test_actual_identical_paid_B1_summary_replays_without_a_new_ledger_row(tmp_path):
    run,request,value,_=fixture(tmp_path)
    response=run.paid_batch_summary(request,1)
    assert response['value']==json.loads(value['result_json'])['value']
    assert response['paid_response_origin']['call_id']==value['call_id']
    assert response['paid_response_origin']['new_physical_teacher_requests']==0
    with sqlite3.connect(tmp_path/'book.sqlite3') as db:
        assert db.execute('select count(*) from calls').fetchone()[0]==1


@pytest.mark.parametrize('field',['config','source_ids','system_prompt','user_prompt','output_schema'])
def test_changed_teacher_request_never_uses_old_summary(tmp_path,field):
    run,request,_,_=fixture(tmp_path);changed=deepcopy(request)
    if field=='config':changed[field]['reasoning_effort']='different'
    elif field=='source_ids':changed[field]=list(reversed(changed[field]))
    elif field=='output_schema':changed[field]['properties']['notes']['description']='different'
    else:changed[field]+=' different'
    assert run.paid_batch_summary(changed,1) is None
    assert run.paid_batch_summary(request,2) is None


def test_ledger_and_saved_teacher_result_must_match(tmp_path):
    run,request,_,path=fixture(tmp_path)
    altered=json.loads((path/'result.json').read_text());altered['value']['notes']='changed'
    (path/'result.json').write_text(json.dumps(altered))
    with pytest.raises(ValueError,match='provenance differs'):
        run.paid_batch_summary(request,1)
