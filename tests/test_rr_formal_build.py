"""Artificial controller tests only, not evidence of real model/mechanism quality."""
import io
import json
from urllib.error import HTTPError
from pathlib import Path
from types import SimpleNamespace

import pytest

from legal_skill_guard.inference.codex_cli_client import StructuredCodexResponse
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.formal import FormalRun,FormalExecutor,FormalTeacher
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.ledger import BudgetLedger,BudgetError
from legal_skill_guard.rr.preflight import science_files
from legal_skill_guard.rr.readiness import current_binding
from test_rr_pipeline import fixture_root,answer_for,mock_learning,authorize_formal_fixture


class Transport:
    generations=0
    def open(self,req,timeout):
        payload=json.loads(req.data)
        if req.full_url.endswith('/tokenize'):return io.BytesIO(b'{"count":3,"tokens":[1,2,3]}')
        self.generations+=1
        if self.generations==1:
            raise HTTPError(req.full_url,503,'artificial transient',{},io.BytesIO(b'artificial unavailable'))
        assert payload['chat_template_kwargs']=={'enable_thinking':False}
        user=payload['messages'][1]['content']
        dataset=user.split('Public benchmark: ',1)[1].split('\n',1)[0]
        content=json.dumps({'answer':answer_for(dataset),'program':{'kind':'unsupported','body':{}},
                           'compiled_units':[],'unsupported_units':[],'interfaces':[]})
        return io.BytesIO(json.dumps({'id':'artificial','choices':[{'finish_reason':'stop','message':{'content':content,
            'reasoning_content':None}}],'usage':{'prompt_tokens':3,'completion_tokens':10,'total_tokens':13}}).encode())


class Teacher:
    calls=0
    def generate_json(self,**kwargs):
        self.calls+=1
        if self.calls==1:raise RuntimeError('Artificial first teacher transport failure')
        return StructuredCodexResponse(value={'patterns':[],'notes':'artificial transport'},model='gpt-5.6-sol',
            request_sha256='fixture',response_sha256='fixture',cache_hit=False,invocation={'usage':{}})


def test_fresh_128_build_ignores_old_pilot_and_first_teacher_then_resumes_free(tmp_path,monkeypatch):
    import legal_skill_guard.rr.formal as mod
    manifest=fixture_root(tmp_path)
    cfgpath=tmp_path/'configs/rr_v2_formal.json';cfg=json.loads(cfgpath.read_text());cfg.update(run_enabled=True,full_build_enabled=True)
    cfgpath.write_text(json.dumps(cfg))
    path=tmp_path/'reports/legalskillguard_rule_reasoning_protocol_v2.json';protocol=json.loads(path.read_text())
    protocol['run_enabled']=True;protocol['execution_request']['full_build_enabled']=True;path.write_text(json.dumps(protocol))
    generation=json.loads((tmp_path/'configs/rr_v2_preflight.json').read_text())
    b=BudgetLedger(tmp_path/generation['ledger_path'],sources=manifest['allowlist'],code_hash='old',config_hash='cfg')
    anchor=manifest['pilot_order'][0]
    with b.transaction() as db:
        # Historical spend includes four teachers and 36 completed build calls.
        for i in range(127):
            bucket='thinking_comparison' if i<40 else 'full_build_including_pilot' if i<76 else 'shared_retries_and_recovery'
            db.execute('insert into calls values (?,?,?,?,?,?,?,?,?)',(f'oldE{i}','executor','pilot_ingestion',bucket,anchor,str(i),'failed',i,'{}'))
        for i in range(4):db.execute('insert into calls values (?,?,?,?,?,?,?,?,?)',
            (f'oldT{i}','teacher','pilot_teacher_summary','teacher',anchor,str(i),'failed',i,'{}'))
    old=b.export()['calls']
    artifacts=tmp_path/cfg['artifact_directory'];artifacts.mkdir(parents=True)
    binding=current_binding(tmp_path)
    immutable_json(artifacts/'seal.json',{'binding':binding,'formal_config':cfg,'protected_files':science_files(tmp_path),
        'ledger_origin_binding':{'code_hash':'old','config_hash':'cfg'},'teacher_transport':{'executable':'artificial'}})
    # Deliberately unusable old material proves the formal controller never reads it.
    olddir=tmp_path/'artifacts/rr_v2_preflight/method_gap_repair_v2/current_material'
    (olddir/'pilot_sources').mkdir(parents=True)
    for sid in manifest['pilot_order']:(olddir/'pilot_sources'/(digest(sid)+'.json')).write_text('{"forbidden":"old pilot"}')
    (olddir/'teacher_batch1.json').write_text('{"forbidden":"old teacher"}')
    transport,teacher=Transport(),Teacher()
    monkeypatch.setattr(mod,'FormalExecutor',lambda ledger,directory,config:FormalExecutor(ledger,directory,config,opener=transport))
    monkeypatch.setattr(mod,'FormalTeacher',lambda ledger,directory,config:FormalTeacher(ledger,directory,config,adapter=teacher))
    monkeypatch.setattr(mod,'learn_source',mock_learning)
    run=FormalRun(tmp_path,partition='train');authorize_formal_fixture(run.ledger)
    result=run.train()
    assert result['sources']==128 and result['batches']==8 and teacher.calls==9
    assert run.ledger.export()['executor_used']==127+transport.generations
    assert run.ledger.export()['teacher_used']==13
    assert transport.generations>128  # old20 were actually acquired afresh
    first=json.loads((artifacts/'sources'/(digest(manifest['formal_train_order'][0])+'.json')).read_text())
    assert first['library_before_hash']==digest(SkillLibrary(stage='formal_train').export())
    for k in (1,8):assert SkillLibrary.restore(artifacts/f'B{k}.frozen.json').frozen
    assert len(list((artifacts/'batches').glob('B*.json')))==8
    before=run.ledger.export()['calls'];old_generations=transport.generations
    # Resume an interrupted source using its failed+completed charged requests,
    # rather than paying again. All later source/batch checkpoints remain intact.
    (artifacts/'sources'/(digest(manifest['formal_train_order'][0])+'.json')).unlink()
    FormalRun(tmp_path,partition='train').train()
    assert teacher.calls==9 and transport.generations==old_generations
    assert run.ledger.export()['calls']==before
    assert all(next(x for x in before if x['id']==r['id'])==r for r in old)
    with pytest.raises(BudgetError,match='evaluation'):
        FormalRun(tmp_path,partition='dev')
    with pytest.raises(BudgetError,match='evaluation'):run.evaluate()
    with pytest.raises(BudgetError,match='evaluation'):run.native_empty()
    with pytest.raises(BudgetError,match='evaluation'):run.diagnostics(None,None)


def test_recover_complete_wire_response_without_model_or_duplicate_charge(tmp_path):
    import base64
    from experiments.rr_v2_formal_build import reconcile
    from test_rr_ledger import sources
    b=BudgetLedger(tmp_path/'ledger',sources=sources(),code_hash='fixed',config_hash='fixed')
    sid=sources()['OpenExempt'][0];cid='fixture:source:0'
    ticket=b.reserve(cid,role='executor',purpose='pilot_ingestion',source=sid,request={})
    directory=tmp_path/'calls'/digest(cid)
    payload={'chat_template_kwargs':{'enable_thinking':False}}
    immutable_json(directory/'request.json',{'request_hash':ticket['request_hash'],'payload':payload,'tokenization':{'tokens':[1,2]}})
    raw={'id':'preserved','choices':[{'finish_reason':'stop','message':{'content':'{"answer":null}'}}],
         'usage':{'prompt_tokens':2,'completion_tokens':5,'total_tokens':7}}
    immutable_json(directory/'wire_response.json',{'body_b64':base64.b64encode(json.dumps(raw).encode()).decode(),'elapsed_seconds':.5})
    reconcile(SimpleNamespace(run_id='fixture',artifacts=tmp_path,ledger=b))
    state=b.export()
    assert state['executor_used']==1 and state['calls'][0]['status']=='completed'
    assert state['calls'][0]['result']['content']=='{"answer":null}'
    assert state['calls'][0]['result']['usage']==raw['usage']
