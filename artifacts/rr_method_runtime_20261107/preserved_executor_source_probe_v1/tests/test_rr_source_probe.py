"""Actual fixed manifest shape; public metadata only, no model or labels."""
from pathlib import Path

from experiments.rr_v2_source_probe import load


def test_actual_probe_load_binds_source_keys_and_original_resources():
    root=Path(__file__).resolve().parents[1]
    cfg,manifest,source,config,sources,stage=load(root,'offline_no_dispatch')
    assert len(sources['train'])==128 and len(sources['dev'])==40
    assert all(isinstance(s,str) for group in sources.values() for s in group)
    assert not set(sources['train'])&set(sources['dev'])
    assert source['key'] in sources['train'] and source['dataset']=='SARA_v2_Binary'
    assert config['executor']['enable_thinking'] is False
    assert config['executor']['model_retries']==config['teacher']['retries']==0


def test_paid_compiler_component_requires_identical_request_and_original_value(tmp_path):
    import json,sqlite3
    import pytest
    from experiments.rr_v2_source_probe import paid_compiler
    stage=tmp_path/'artifacts/rr_method_runtime_20261107/paid'
    stage.mkdir(parents=True);(tmp_path/'configs').mkdir()
    source={'key':'SARA:original','public':{'rules':'public only'}}
    teacher={'model':'unchanged'};schema={'type':'object'};program={'observations':[]}
    seal={'run_id':'paid','source':source,'config':{'teacher':teacher},'system':'system','user':'public',
          'schema':schema,'binding':{'code_hash':'old','config_hash':'old'}}
    (stage/'seal.json').write_text(json.dumps(seal));(stage/'program.json').write_text(json.dumps(program))
    (tmp_path/'configs/rr_v2_preflight.json').write_text(json.dumps({'ledger_path':'original.sqlite3'}))
    with sqlite3.connect(tmp_path/'original.sqlite3') as db:
        db.execute('create table calls (id,role,source,status,result)')
        db.execute('insert into calls values (?,?,?,?,?)',('paid:compile','teacher',source['key'],'completed',
            json.dumps({'value':program,'source_ids':[source['key']],'response_sha256':'original-response'})))
    value,proof=paid_compiler(tmp_path,'paid',source,{'teacher':teacher},'system','public',schema)
    assert value==program and proof['new_teacher_calls']==0
    with pytest.raises(ValueError,match='identical'):
        paid_compiler(tmp_path,'paid',source,{'teacher':teacher},'different','public',schema)
    (stage/'program.json').write_text(json.dumps({'observations':['invented']}))
    with pytest.raises(ValueError,match='immutable paid'):
        paid_compiler(tmp_path,'paid',source,{'teacher':teacher},'system','public',schema)


def test_teacher_cache_cannot_count_as_independent_executor_compilation(tmp_path,monkeypatch):
    import json,sqlite3,pytest
    import experiments.rr_v2_source_probe as probe
    (tmp_path/'reports/rr_method_runtime_20261107').mkdir(parents=True)
    (tmp_path/'docs/rr_v2').mkdir(parents=True)
    (tmp_path/'reports/rr_method_runtime_20261107/offline_executor_contract_v1.json').write_text(json.dumps({
        'exit_code':0,'network_blocked':True,'files':{}}))
    (tmp_path/'docs/rr_v2/method_runtime_authorization_20261107.json').write_text('{}')
    with sqlite3.connect(tmp_path/'book.sqlite3') as db:db.execute('create table calls (status)')
    monkeypatch.setattr(probe,'science_files',lambda root:{})
    stage=tmp_path/'not_dispatched'
    monkeypatch.setattr(probe,'load',lambda *args:({'ledger_path':'book.sqlite3'},{},{},
        {'compiler_role':'executor'},{},stage))
    with pytest.raises(ValueError,match='independent executor'):
        probe.prepare(tmp_path,'test',compiler_origin='teacher_origin',compiler_role='executor')
    assert not stage.exists()
