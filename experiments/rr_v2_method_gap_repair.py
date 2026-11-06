"""Current bounded repair evidence. Historical responses are never new generations."""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import sqlite3
import subprocess
from types import SimpleNamespace
from unittest.mock import patch

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.preflight import Preflight, ingest_source, science_files, score_source
from legal_skill_guard.rr.readiness import current_binding
from legal_skill_guard.rr.source_learning import DurableOracle, learn_source

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = 'artifacts/rr_v2_preflight/method_gap_repair_v2'
EVIDENCE = 'reports/rr_v2_evidence/method_gap_repair'
REVISION = 'method_gap_repair_v2'


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def database_state(root):
    path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    with sqlite3.connect('file:' + str(path) + '?mode=ro', uri=True) as db:
        calls = db.execute('select * from calls order by id').fetchall()
        meta = db.execute('select * from meta order by key').fetchall()
        oracle = db.execute('select * from oracle_views order by source,view_hash').fetchall()
    return {'calls': calls, 'meta': meta, 'oracle': oracle,
            'calls_hash': digest(calls), 'meta_hash': digest(meta), 'oracle_hash': digest(oracle),
            'db_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


class CachedOnlyLedger:
    def __init__(self, sources, path):
        self.allowed, self.path = set(sources), path
    def _source(self, source):
        if source not in self.allowed:
            raise ValueError('Source outside original fixed20')
    def reserve_oracle(self, source, view):
        raise ValueError('This reprocessing pass cannot query a new oracle view')


def teacher_material(records, library):
    common = [{'source': r['source'], 'dataset': r['dataset'],
        'program_status': r['analysis']['program_status'],
        'certificate_status': r['analysis']['certificate_status'],
        'learning_status': r['learning']['status'], 'refinement': r['learning'].get('refinement'),
        'pattern': r['learning'].get('learned_pattern')} for r in records]
    return {'common_first_16_training_records': common, 'current_parameterized_library': library.export()}


def replay(root=ROOT, *, name='replay_before_live'):
    root = Path(root)
    binding, before = current_binding(root), database_state(root)
    data = PreflightData(root, root / 'reports/rr_v2_evidence/data_manifest.json')
    prior_rows = json.loads((root / 'reports/rr_v2_evidence/semantic_preflight/source_status.json').read_text())
    stage = root / DIRECTORY / name / binding['code_hash'][:16]
    scope = CachedOnlyLedger(data.order, root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    charged = {r[5]: json.loads(r[8]) for r in before['calls'] if r[6] == 'completed'}
    library, old_library = SkillLibrary(), SkillLibrary()
    records, traces, paths, old_records = [], [], [], []
    def forbidden(*args, **kwargs):
        raise RuntimeError('Offline reprocessing forbids network, subprocess and new generation')
    with patch.object(socket.socket, 'connect', forbidden), patch.object(socket.socket, 'connect_ex', forbidden), \
         patch.object(subprocess, 'run', forbidden), patch.object(subprocess, 'Popen', forbidden):
        for i, item in enumerate(prior_rows):
            sid = item['source']
            old = json.loads((root / item['source_record']).read_text())
            source, grade, trace = data.public(sid), data.grade(sid), {}
            def call(**kw):
                index = int(kw['call_id'].rsplit(':', 1)[1])
                if index >= len(old['calls']):
                    raise ValueError('No historical response for requested step; do not synthesize one')
                original = old['calls'][index]
                saved = charged[original['request_hash']]
                if saved['content'] != original['raw_content']:
                    raise ValueError('Saved raw response differs from charged ledger')
                return {'content': original['raw_content'], 'request_hash': original['request_hash'],
                        'usage': original['usage'], 'elapsed_seconds': original['elapsed_seconds']}
            def learner(s, g, oracle, *, proposal=None):
                return learn_source(s, g, oracle, proposal=proposal, trace=trace)
            record = ingest_source(source=source, grade=grade, library=library, thinking=True,
                call=call, learner=learner, ledger=scope, artifacts=stage, binding=binding,
                purpose='preflight_bug_retry', id_prefix='raw_reprocessing', offline_mock=False,
                oracle_artifacts=root / 'artifacts/rr_v2_preflight/oracle_guard')
            record.update(record_kind='historical_raw_response_reprocessing', new_model_calls=0,
                generation_binding=old['binding'], processing_binding=binding,
                generation_thinking=[charged[c['request_hash']]['thinking_requested'] for c in old['calls']],
                original_record_path=item['source_record'], original_record_hash=digest(old))
            path = stage / 'pilot_sources' / (digest(sid) + '.json')
            immutable_json(path, record)
            records.append(record); old_records.append(old); paths.append(str(path.relative_to(root)))
            if record['learning'].get('learned_pattern'):
                library.add(record['learning']['learned_pattern'], source=sid)
            if old['learning'].get('learned_pattern'):
                old_library.add(old['learning']['learned_pattern'], source=sid)
            traces.append({'source': sid, 'trace': trace})
            if i == 15:
                old_material = teacher_material(old_records, old_library)
                new_material = teacher_material(records, library)
                teacher_exact = json.dumps(old_material, ensure_ascii=False) == json.dumps(new_material, ensure_ascii=False)
                teacher_semantics_equal = digest(old_material) == digest(new_material)
    snapshot = library.freeze(stage / 'partial_library.frozen.json')
    assert SkillLibrary.restore(stage / 'partial_library.frozen.json').export() == library.export()
    checkpoint = {'binding': binding, 'complete_sources': data.order,
        'source_record_paths': paths, 'source_record_hashes': [digest(r) for r in records],
        'library': library.export(), 'library_sha256': snapshot['sha256']}
    immutable_json(stage / 'checkpoint.json', checkpoint)
    after = database_state(root)
    if before != after:
        raise ValueError('Offline reprocessing changed original ledger')
    summary = {'binding': binding, 'stage': str(stage.relative_to(root)), 'sources': 20,
        'source_records': paths, 'source_record_hashes': checkpoint['source_record_hashes'],
        'new_model_calls': 0, 'new_oracle_views': 0, 'ledger_unchanged': True,
        'network_and_subprocess_blocked': True, 'restore_verified': True,
        'teacher_material_bytes_equal': teacher_exact, 'teacher_material_semantics_equal': teacher_semantics_equal,
        'teacher_batch_reuse_requires_existing_actual_record': True,
        'partial_library_sha256': snapshot['sha256'], 'patterns': len(library.patterns),
        'before': {k: before[k] for k in ['calls_hash', 'meta_hash', 'oracle_hash', 'db_sha256']},
        'task_correct': sum(r['score']['task_correct'] for r in records),
        'stable': sum(r['analysis']['certificate_status'] == 'completion_stable' for r in records),
        'B_traces': traces, 'not_new_real_core_evidence': True}
    dump(root / EVIDENCE / (name + '.json'), summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ['B_traces','source_records','source_record_hashes']}, ensure_ascii=False), flush=True)
    return summary


def restore(root=ROOT, *, name='replay_before_live'):
    root = Path(root)
    summary = json.loads((root / EVIDENCE / (name + '.json')).read_text())
    if summary['binding'] != current_binding(root):
        raise ValueError('Reprocessed records belong to another execution binding')
    stage = root / summary['stage']
    state = json.loads((stage / 'checkpoint.json').read_text())
    records = [json.loads((root / p).read_text()) for p in state['source_record_paths']]
    if [digest(r) for r in records] != state['source_record_hashes'] or \
            SkillLibrary.restore(stage / 'partial_library.frozen.json').export() != state['library']:
        raise ValueError('Reprocessed checkpoint or frozen library changed')
    before = database_state(root)
    # Repeat real algorithm reprocessing; immutable_json proves deterministic
    # records and snapshot reproduction, with network/dispatch blocked above.
    rerun = replay(root, name=name)
    assert database_state(root) == before
    result = {'binding': current_binding(root), 'sources': 20, 'exact_records_and_library': True,
              'network_and_subprocess_blocked': True, 'new_model_calls': 0, 'new_oracle_views': 0,
              'ledger_unchanged': True}
    dump(root / EVIDENCE / 'restore.json', result)
    return result


def historical_core(root=ROOT):
    """Re-execute the four preserved real core outputs, not fresh predictions."""
    from legal_skill_guard.rr.engine import analyze
    from experiments.rr_v2_core_preflight import checks
    data = PreflightData(root, root / 'reports/rr_v2_evidence/data_manifest.json')
    scope = CachedOnlyLedger(data.order, root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    before, records = database_state(root), []
    def deny(*a, **kw): raise RuntimeError('Historical core audit cannot dispatch')
    with patch.object(socket.socket,'connect',deny), patch.object(socket.socket,'connect_ex',deny), \
            patch.object(subprocess,'run',deny), patch.object(subprocess,'Popen',deny):
        for index in (3,8,13,18):
            sid = data.order[index]
            path = root / 'artifacts/rr_v2_preflight/core_primary_v1/sources' / (digest(sid)+'.json')
            old = json.loads(path.read_text())
            source, grade, trace = data.public(sid), data.grade(sid), {}
            analysis = analyze(source, old['record']['calls'][-1]['raw_content'])
            oracle = DurableOracle(scope, root/'artifacts/rr_v2_preflight/oracle_guard', source, grade)
            learning = learn_source(source, grade, oracle, proposal=analysis.get('proposal'), trace=trace)
            record = dict(source=sid, analysis=analysis, learning=learning,
                          score=score_source(source,analysis,grade,native_oe=True))
            records.append({'index':index, 'source':sid, 'original_record_path':str(path.relative_to(root)),
                'original_record_hash':digest(old), 'checks':checks(record,trace), 'trace':trace,
                'learning':learning, 'generation_thinking':True, 'new_model_calls':0,
                'evidence_kind':'current_algorithm_on_preserved_real_core_response'})
    assert before == database_state(root)
    result = {'binding':current_binding(root), 'records':records, 'new_model_calls':0,
        'new_oracle_views':0, 'ledger_unchanged':True, 'network_and_subprocess_blocked':True}
    dump(root/EVIDENCE/'historical_core.json',result)
    print(json.dumps([{'index':r['index'],'checks':r['checks'],
        'collisions':len(r['learning'].get('refinement',{}).get('collisions',[]))} for r in records]),flush=True)
    return result


def prepare(root=ROOT):
    from legal_skill_guard.rr.ledger import BudgetLedger
    cfg = json.loads((root/'configs/rr_v2_preflight.json').read_text())
    assert not cfg['formal_run_enabled'] and not cfg['frozen_test_enabled'] and cfg['executor']['enable_thinking'] is False
    binding, before = current_binding(root), database_state(root)
    evidence = {name:json.loads((root/path).read_text()) for name,path in {
        'offline':'reports/rr_v2_evidence/offline_latest.json', 'backend':EVIDENCE+'/backend.json',
        'replay':EVIDENCE+'/replay_before_live.json', 'restore':EVIDENCE+'/restore.json',
        'historical_core':EVIDENCE+'/historical_core.json'}.items()}
    offline = evidence['offline']
    if offline['exit_code'] or not offline['network_blocked'] or any(
        hashlib.sha256((root/p).read_bytes()).hexdigest()!=h for p,h in offline['files'].items()):
        raise ValueError('Current complete offline regression required')
    if any(e['binding'] != binding for name,e in evidence.items() if name!='offline') or \
        not evidence['backend']['all_checks_passed'] or not evidence['backend']['local_serving_tokens_exact'] or \
        not evidence['restore']['exact_records_and_library']:
        raise ValueError('Current backend/algorithm/restore evidence required')
    spec = dict(before['meta'])['spec']; spec = json.loads(spec)
    data = PreflightData(root,root/cfg['source_manifest'])
    ledger = BudgetLedger(root/cfg['ledger_path'],sources=data.manifest['allowlist'],
        code_hash=spec['code_hash'],config_hash=spec['config_hash'])
    ledger.register_study_revision(REVISION,new_binding={k:binding[k] for k in ('code_hash','config_hash')},
        change='Connect actual A residual/planning/tokenized requests, canonical five-bank interface schema, typed B candidates and actual primitive I/O collisions; explicit user OFF profile',
        offline_evidence_hash=digest(evidence))
    seal = {'binding':binding,'config':cfg,'protected_files':science_files(root),'evidence_hash':digest(evidence),
        'source_indices':{'wire_contract':4,'primary_path':13}, 'no_new_sources':True,
        'executor_thinking':False,'new_oracle_views':0,'formal_launch_authorized':False,
        'ledger_origin_binding':{k:spec[k] for k in ('code_hash','config_hash')},
        'historical_baseline':{'executor':124,'teacher':3}}
    immutable_json(root/DIRECTORY/'live/seal.json',seal)
    print(json.dumps({'binding':binding,'sealed':True,'baseline':seal['historical_baseline']}),flush=True)
    return seal


def runner(root=ROOT):
    from legal_skill_guard.rr.ledger import BudgetLedger, BudgetError
    from legal_skill_guard.rr.client import ExecutorClient
    seal = json.loads((root/DIRECTORY/'live/seal.json').read_text())
    if science_files(root)!=seal['protected_files']:
        raise ValueError('Sealed code/config changed; do not dispatch')
    cfg=seal['config'];data=PreflightData(root,root/cfg['source_manifest'])
    class NoNewOracle(BudgetLedger):
        def reserve_oracle(self,*args): raise BudgetError('Repair validation uses existing charged oracle views only')
    ledger=NoNewOracle(root/cfg['ledger_path'],sources=data.manifest['allowlist'],
        **{k:seal['binding'][k] for k in ('code_hash','config_hash')})
    client=ExecutorClient(ledger,root/DIRECTORY/'live',cfg['executor'])
    def call(**kw):
        sid=kw['source']['key']
        payload=client.payload(messages=kw['prompt'],thinking=kw['thinking'],schema=kw['schema'])
        ledger.register_study_request(kw['call_id'],revision=REVISION,source=sid,
            request={'thinking':kw['thinking'],'payload':payload},step=int(kw['call_id'].rsplit(':',1)[1]))
        return client.generate(kw['call_id'],source=sid,purpose='preflight_bug_retry',
            messages=kw['prompt'],thinking=kw['thinking'],schema=kw['schema'])
    return seal,data,ledger,client,call


def live_contract(root=ROOT):
    from legal_skill_guard.rr.compilation import prepare_request
    from legal_skill_guard.rr.engine import analyze
    from legal_skill_guard.rr.wire_validation import WireValidator
    seal,data,ledger,client,call=runner(root)
    path=root/DIRECTORY/'live/wire_contract.json'
    if path.exists(): return json.loads(path.read_text())
    sid=data.order[4];source=data.public(sid)
    request=prepare_request(source,request_config=client.config,thinking=False)
    wire=call(call_id=REVISION+':wire_contract:'+sid+':0',source=source,
              prompt=request['messages'],schema=request['schema'],thinking=False)
    analysis=analyze(source,wire['content'])
    value=json.loads(wire['content'])
    result={'binding':seal['binding'],'source':sid,'wire':wire,'analysis':analysis,
        'wire_schema_pass':WireValidator(request['schema']).is_valid(value),
        'parser_structural_pass':analysis['structural_pass'],
        'score':score_source(source,analysis,data.grade(sid),native_oe=True),
        'counts_as_core_success':False,'generation_thinking':False,
        'purpose':'single affected ContractNLI wire/parser compatibility check, no counterfactual oracle'}
    immutable_json(path,result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'wire','analysis'}},ensure_ascii=False),flush=True)
    return result


def live_primary(root=ROOT):
    from experiments.rr_v2_core_preflight import checks
    seal,data,ledger,client,call=runner(root)
    path=root/DIRECTORY/'live/primary_path.json'
    if path.exists(): return json.loads(path.read_text())
    sid=data.order[13];trace={}
    # Starting library is shared prior material, not a cached learner output.
    replay=json.loads((root/EVIDENCE/'replay_before_live.json').read_text())
    library=SkillLibrary.restore(root/replay['stage']/'partial_library.frozen.json')
    def learner(s,g,oracle,*,proposal=None):return learn_source(s,g,oracle,proposal=proposal,trace=trace)
    record=ingest_source(source=data.public(sid),grade=data.grade(sid),library=library,thinking=False,
        call=call,learner=learner,ledger=ledger,artifacts=root/DIRECTORY/'live',binding=seal['binding'],
        purpose='preflight_bug_retry',id_prefix=REVISION,offline_mock=False,
        oracle_artifacts=root/'artifacts/rr_v2_preflight/oracle_guard',
        tokenize=lambda p:client.tokenize(p,thinking=False),request_config=client.config)
    record.update(record_kind='current_real_generation',generation_binding=seal['binding'],generation_thinking=False)
    result={'record':record,'trace':trace,'checks':checks(record,trace),'binding':seal['binding']}
    immutable_json(path,result)
    print(json.dumps({'source':sid,'requests':len(record['calls']),'checks':result['checks']},ensure_ascii=False),flush=True)
    return result


def assemble(root=ROOT):
    """Current common training material; retain generation provenance per source."""
    from legal_skill_guard.rr.example_synthesis import fit_shared_examples
    seal,data,ledger,client,call=runner(root)
    replay=json.loads((root/EVIDENCE/'replay_before_live.json').read_text())
    live=json.loads((root/DIRECTORY/'live/primary_path.json').read_text())
    stage=root/DIRECTORY/'current_material'
    records=[json.loads((root/p).read_text()) for p in replay['source_records']]
    assert len(records)==20 and records[13]['source']==live['record']['source']
    records[13]=live['record']
    library=SkillLibrary();paths=[]
    for index,record in enumerate(records):
        path=stage/'pilot_sources'/(digest(record['source'])+'.json')
        immutable_json(path,record);paths.append(str(path.relative_to(root)))
        if record['learning'].get('learned_pattern'):
            library.add(record['learning']['learned_pattern'],source=record['source'])
        if index==15:
            library.freeze(stage/'B1_preflight_partial.json')
            library=SkillLibrary(library.patterns)
    snapshot=library.freeze(stage/'partial_library.frozen.json')
    common={'binding':seal['binding'],'complete_sources':data.order,'source_record_paths':paths,
        'source_record_hashes':[digest(r) for r in records],'library_sha256':snapshot['sha256'],
        'historical_generated_sources':19,'current_generated_sources':1,
        'historical_predictions_reused_as_OFF_predictions':False,'teacher_complete':False}
    immutable_json(stage/'checkpoint.json',common)
    examples=fit_shared_examples({s:data.public(s) for s in data.order},records,{s:data.grade(s) for s in data.order})
    immutable_json(stage/'MB_preflight_examples.frozen.json',examples)
    return common


def teacher(root=ROOT):
    from legal_skill_guard.rr.client import TeacherClient
    seal,data,ledger,client,call=runner(root)
    stage=root/DIRECTORY/'current_material'
    checkpoint=json.loads((stage/'checkpoint.json').read_text())
    records=[json.loads((root/p).read_text()) for p in checkpoint['source_record_paths'][:16]]
    library=SkillLibrary.restore(stage/'B1_preflight_partial.json')
    transport=json.loads((root/'artifacts/rr_v2_preflight/oracle_guard/teacher_transport_retry_receipt.json').read_text())
    if hashlib.sha256(Path(transport['actual_retry_executable']).read_bytes()).hexdigest()!=transport['direct_cli_sha256']:
        raise ValueError('Previously verified teacher transport changed')
    client=TeacherClient(ledger,root/DIRECTORY/'live',seal['config']['teacher'])
    client.adapter.executable=transport['actual_retry_executable']
    original=client.summarize
    def summarize(call_id,**kwargs):
        request=dict(source_ids=kwargs['source_ids'],config=client.config,purpose=client.summary_purpose,
            system_prompt=kwargs['system_prompt'],user_prompt=kwargs['user_prompt'],output_schema=kwargs['output_schema'])
        ledger.register_study_request(call_id,revision=REVISION,source=kwargs['source_ids'][0],request=request,role='teacher')
        return original(call_id,**kwargs)
    client.summarize=summarize
    proxy=SimpleNamespace(artifacts=stage,data=SimpleNamespace(order=data.order),teacher=client,
        seal={'binding':seal['binding'],'offline_mock':False,'study_preflight_revision':REVISION})
    result=Preflight._summarize(proxy,records,library)
    immutable_json(stage/'teacher_transport.json',{'executable':transport['actual_retry_executable'],
        'executable_sha256':transport['direct_cli_sha256'],'configured_launcher_sha256':transport['launcher_sha256'],
        'same_model_parameters':True,'temperature_explicit':False,'automatic_adapter_retries':0})
    print(json.dumps({'batch_record_accepted':result['batch_record_accepted'],
        'accepted':result['accepted_pattern_hashes'],'pending':len(result['pending_proposals'])}),flush=True)
    return result


def current_restore(root=ROOT):
    from legal_skill_guard.rr.controls import ARMS
    from legal_skill_guard.rr.routing import route_prediction
    seal,data,ledger,client,call=runner(root)
    stage=root/DIRECTORY/'current_material'
    checkpoint=json.loads((stage/'checkpoint.json').read_text())
    records=[json.loads((root/p).read_text()) for p in checkpoint['source_record_paths']]
    frozen=SkillLibrary.restore(stage/'partial_library.frozen.json')
    examples=json.loads((stage/'MB_preflight_examples.frozen.json').read_text())
    teacher=json.loads((stage/'teacher_batch1.json').read_text())
    assert teacher['batch_record_accepted'] and not teacher['offline_mock']
    assert teacher['source_ids']==data.order[:16] and teacher['reuse_requires_matching_binding']==seal['binding']
    before=database_state(root)
    charged={r[5]:json.loads(r[8]) for r in before['calls'] if r[6]=='completed'}
    library=SkillLibrary();controls=[]
    def deny(*a,**kw):raise RuntimeError('Current restore cannot dispatch network or subprocesses')
    with patch.object(socket.socket,'connect',deny),patch.object(socket.socket,'connect_ex',deny),\
            patch.object(subprocess,'run',deny),patch.object(subprocess,'Popen',deny):
        for index,record in enumerate(records):
            sid=record['source'];source=data.public(sid);grade=data.grade(sid)
            def saved_call(**kw):
                step=int(kw['call_id'].rsplit(':',1)[1]);saved=record['calls'][step]
                if saved['raw_content']!=charged[saved['request_hash']]['content']:
                    raise ValueError('Restored output differs from actual charged response')
                return {'content':saved['raw_content'],'request_hash':saved['request_hash'],
                    'usage':saved['usage'],'elapsed_seconds':saved['elapsed_seconds']}
            scope=CachedOnlyLedger(data.order,root/seal['config']['ledger_path'])
            reproduced=ingest_source(source=source,grade=grade,library=library,
                thinking=record.get('generation_thinking',True) is not False,call=saved_call,learner=learn_source,
                ledger=scope,artifacts=stage,binding=seal['binding'],purpose='preflight_bug_retry',
                id_prefix='restore',offline_mock=False,oracle_artifacts=root/'artifacts/rr_v2_preflight/oracle_guard')
            # Generation provenance is deliberately outside deterministic processing.
            # New PW validation normally terminates in its first call; planned
            # request costs from a live second call are checked separately.
            for key in ('source','dataset','calls','analysis','learning','score','input_hash','learning_attempts'):
                if digest(reproduced[key])!=digest(record[key]):
                    raise ValueError('Current algorithm restore differs at '+sid+':'+key)
            pattern=reproduced['learning'].get('learned_pattern')
            if pattern:library.add(pattern,source=sid)
            for arm in ARMS:
                def generate(prompt,**kwargs):
                    return {'content':record['calls'][min(kwargs['step'],len(record['calls'])-1)]['raw_content']}
                generate.is_offline_mock=True
                routed=route_prediction(source,arm=arm,library=frozen.export(),generate=generate,protocol={},
                    partition='train',offline_mock=True,example_model=examples,thinking=False)
                assert routed['model_calls']<=3 and routed['frozen_library_unchanged']
                controls.append({'source':sid,'arm':arm,'calls':routed['model_calls'],
                    'fallback':routed['result'].get('fallback_used',False),
                    'certificate_status':routed['result']['certificate_status'],
                    'evidence_kind':'offline_control_flow_reusing_saved_raw_response_including_last_for_fallback'})
    library.frozen=True
    assert library.export()==frozen.export()
    assert before==database_state(root)
    result={'binding':seal['binding'],'sources':20,'exact_records_and_library':True,
        'network_and_subprocess_blocked':True,'new_model_calls':0,'new_oracle_views':0,
        'ledger_unchanged':True,'controls':controls,'not_real_six_arm_predictions':True}
    dump(root/EVIDENCE/'current_restore.json',result)
    immutable_json(stage/'pilot_completion.json',{'binding':seal['binding'],'sources':20,
        'restore_verified':True,'teacher_batch_record_accepted':True,'library_sha256':checkpoint['library_sha256'],
        'historical_generated_sources':19,'current_generated_sources':1,
        'historical_predictions_reused_as_OFF_predictions':False})
    print(json.dumps({k:v for k,v in result.items() if k!='controls'}),flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    commands={'replay':replay,'restore':restore,'historical_core':historical_core,'prepare':prepare,
              'live_contract':live_contract,'live_primary':live_primary,'assemble':assemble,'teacher':teacher,
              'current_restore':current_restore}
    parser.add_argument('command', choices=list(commands))
    args = parser.parse_args()
    commands[args.command]()
