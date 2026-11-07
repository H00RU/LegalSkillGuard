"""Fixed-source common-path repair, existing budget and resumable pilot. No main build."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from copy import deepcopy

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import ExecutorClient, TeacherClient
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.data_store import PreflightData
from legal_skill_guard.rr.engine import analyze, proposal_schema, wire_messages
from legal_skill_guard.rr.learning import SkillLibrary
from legal_skill_guard.rr.ledger import BudgetLedger
from legal_skill_guard.rr.preflight import Preflight, atomic_json, ingest_source, science_files, score_source
from legal_skill_guard.rr.schema_validation import execution_binding, validate_response
from legal_skill_guard.rr.strict_contract import TARGETS

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'semantic_common_path_v3'
DIRECTORY = 'semantic_common_path_v3'


def inputs(root):
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    return cfg, PreflightData(root, root / cfg['source_manifest'])


def backend(root):
    import socket
    from unittest.mock import patch
    import xgrammar
    from transformers import AutoTokenizer
    from legal_skill_guard.rr.compiler_prompt import format_examples
    cfg, data = inputs(root)
    def deny(*args, **kwargs):
        raise RuntimeError('Offline decoder regression forbids network')
    records = []
    with patch.object(socket.socket, 'connect', deny), patch.object(socket.socket, 'connect_ex', deny):
        model = Path(cfg['executor']['model_root'])
        tok = AutoTokenizer.from_pretrained(str(model), local_files_only=True, trust_remote_code=False)
        compiler = xgrammar.GrammarCompiler(xgrammar.TokenizerInfo.from_huggingface(tok,
            vocab_size=json.loads((model / 'config.json').read_text())['vocab_size']), max_threads=1)
        for sid in data.order:
            source = data.public(sid)
            if source['dataset'] not in TARGETS:
                continue
            schema = proposal_schema(source['dataset'], source=source)
            grammar = compiler.compile_json_schema(schema, strict_mode=True, any_whitespace=False)
            ex = deepcopy(format_examples()[{'RuleArena_Airline': 0, 'SARA_v2_Binary': 1, 'OpenExempt': 2}[source['dataset']]]['proposal'])
            if source['dataset'] == 'OpenExempt':
                ex['answer'] = {'EC': {}, 'EV': {}}
            cases = [(True, ex)]
            for query in [{'op':'and','args':['s157']}, {'op':'if','args':['s0',1,0]},
                          {'op':'add','args':['5',0]}, {'op':'if','args':[True]}]:
                p = deepcopy(ex); p['program']['body']['query'] = query; cases.append((False,p))
            actual = json.loads((root / 'tests/fixtures/rr_strict_actual_failure.json').read_text())
            cases.append((False, json.loads(actual['raw_response']['choices'][0]['message']['content'])))
            for expected,p in cases:
                m = xgrammar.GrammarMatcher(grammar)
                tokens = tok.encode(json.dumps(p,ensure_ascii=False),add_special_tokens=False)
                ok = True
                for i,t in enumerate(tokens):
                    if not m.accept_token(t):
                        ok = False
                        break
                ok = ok and m.accept_token(tok.eos_token_id) and m.is_terminated()
                if ok != expected:
                    raise AssertionError((sid,expected,i,tok.decode(tokens[max(0,i-16):i+16])))
            second_pass_cases = 0
            if sid == data.order[0]:
                from legal_skill_guard.rr.engine import reusable_inputs
                actual95 = json.loads((root/'tests/fixtures/rr_actual_failure_95.json').read_text())
                actual_proposal = json.loads(actual95['content'])
                previous = {'proposal': actual_proposal}
                if len(reusable_inputs(source, previous)) != 4:
                    raise AssertionError('Real failed response lost its four publicly quoted input literals')
                second_schema = proposal_schema(source['dataset'], source=source, previous=previous)
                second_grammar = compiler.compile_json_schema(second_schema, strict_mode=True, any_whitespace=False)
                m = xgrammar.GrammarMatcher(second_grammar)
                # Original duplicate keys remain executable-IR errors, never merged/adapted.
                tokens = tok.encode(actual95['content'], add_special_tokens=False)
                if not all(m.accept_token(t) for t in tokens) or not m.accept_token(tok.eos_token_id) or not m.is_terminated():
                    raise AssertionError('Exact real response fails the grounded-input syntax regression')
                second_pass_cases = 1
            messages = wire_messages(source)
            tokens = tok.apply_chat_template(messages, tokenize=True, add_generation_prompt=True,enable_thinking=True)
            if len(tokens)+cfg['executor']['max_tokens'] > cfg['executor']['context_tokens']:
                raise ValueError('No truncation allowed')
            records.append(dict(source=sid,schema_hash=digest(schema),messages_hash=digest(messages),
                cases=len(cases),second_pass_cases=second_pass_cases,context_fits=True,prompt_tokens=len(tokens)))
            print(json.dumps(records[-1]),flush=True)
    atomic_json(root / 'reports/rr_v2_evidence/semantic_preflight/backend.json', dict(
        network_blocked=True,weights_loaded=False,labels_loaded=False,requests_added=0,records=records))


def prepare(root):
    cfg,data=inputs(root);base=root/cfg['artifact_directory'];stage=base/DIRECTORY
    if (base/'seal.semantic_path.json').exists():
        return json.loads((base/'seal.semantic_path.json').read_text())
    old=json.loads((base/'seal.oracle_guard.json').read_text());binding=execution_binding(root)
    offline=json.loads((root/'reports/rr_v2_evidence/offline_latest.json').read_text())
    if offline['exit_code'] or not offline['network_blocked'] or any(
        hashlib.sha256((root/p).read_bytes()).hexdigest()!=v for p,v in offline['files'].items()):
        raise ValueError('Current offline acceptance required')
    backend_receipt=json.loads((root/'reports/rr_v2_evidence/semantic_preflight/backend.json').read_text())
    if not backend_receipt['network_blocked'] or len(backend_receipt['records'])!=12:
        raise ValueError('Twelve actual decoder checks required')
    for r in backend_receipt['records']:
        source=data.public(r['source'])
        if r['schema_hash']!=digest(proposal_schema(source['dataset'],source=source)) or r['messages_hash']!=digest(wire_messages(source)):
            raise ValueError('Decoder receipt stale')
    ledger=BudgetLedger(root/cfg['ledger_path'],sources=data.manifest['allowlist'],
        **{k:old['binding'][k] for k in ('code_hash','config_hash')})
    ledger.register_study_authorization(json.loads((root/cfg['repair_execution_policy']).read_text()))
    ledger.register_study_revision(REVISION,new_binding={k:binding[k] for k in ('code_hash','config_hash')},
        change='Source-bound schema through common train/inference two-pass path; grounded input reuse; native OE format/multiset scoring',
        offline_evidence_hash=digest(dict(offline=offline,backend=backend_receipt)))
    # B learner, source inputs, references and cached oracle views are unchanged.
    import tarfile
    with tarfile.open(base/'preserved_before_semantic_diagnosis/science.tar.gz') as archive:
        for name in ['legal_skill_guard/rr/source_learning.py','legal_skill_guard/rr/learning.py','legal_skill_guard/rr/oracles.py']:
            if archive.extractfile(name).read()!=(root/name).read_bytes():
                raise ValueError('Cached interface-learning implementation changed')
    reused=[]
    for sid in data.order:
        source=data.public(sid)
        if source['dataset'] in TARGETS:
            continue
        prior=json.loads((base/'oracle_guard/pilot_sources'/f'{digest(sid)}.json').read_text())
        if prior['input_hash']!=source['content_hash'] or prior['offline_mock']:
            raise ValueError('Cannot reuse historical source')
        record=deepcopy(prior)
        for call in record['calls']:
            analysis=analyze(source,call['raw_content'])
            if digest(analysis)!=digest(call['analysis']):
                raise ValueError('Unchanged-source replay differs')
        record.update(binding=binding,generation_binding=prior.get('generation_binding',prior['binding']),
            replay_provenance=dict(original_record_hash=digest(prior),new_generation_requests=0))
        record['score']=score_source(source,record['analysis'],data.grade(sid))
        immutable_json(stage/'pilot_sources'/f'{digest(sid)}.json',record);reused.append(sid)
    selection=json.loads((base/'oracle_guard'/old['wire_repair']['selection_file']).read_text())
    immutable_json(stage/'thinking_selection.json',selection)
    transport=json.loads((base/'oracle_guard/teacher_transport_retry_receipt.json').read_text())
    immutable_json(stage/'teacher_transport_retry_receipt.json',transport)
    files=science_files(root)
    seal=dict(schema=1,stage='preflight',offline_mock=False,binding=binding,protected_files=files,config=cfg,
        allowlist=data.manifest['allowlist'],pilot_order=data.order,offline_evidence_hash=digest(offline),
        formal_execution_enabled=False,study_preflight_revision=REVISION,
        processing_continuation=dict(artifact_subdirectory=DIRECTORY,generation_binding=binding,thinking_binding=selection['binding']),
        replayed_unaffected_sources=reused,
        reused_interface_material={sid:digest(json.loads((base/'oracle_guard/pilot_sources'/f'{digest(sid)}.json').read_text())['learning']) for sid in data.order})
    immutable_json(base/'seal.semantic_path.json',seal)
    return seal


def runner(root):
    cfg,data=inputs(root);base=root/cfg['artifact_directory']
    seal=json.loads((base/'seal.semantic_path.json').read_text())
    p=Preflight(root,oracle_artifacts=base/'oracle_guard')
    # Use the previously verified direct CLI transport, with identical model/effort/no retry.
    transport=json.loads((p.artifacts/'teacher_transport_retry_receipt.json').read_text())
    if hashlib.sha256(Path(transport['actual_retry_executable']).read_bytes()).hexdigest()!=transport['direct_cli_sha256']:
        raise ValueError('Teacher executable changed')
    p.teacher.adapter.executable=transport['actual_retry_executable']
    original=p.teacher.summarize
    def summary(call_id,**kwargs):
        request=dict(source_ids=kwargs['source_ids'],config=p.teacher.config,purpose=p.teacher.summary_purpose,
                     system_prompt=kwargs['system_prompt'],user_prompt=kwargs['user_prompt'],output_schema=kwargs['output_schema'])
        p.ledger.register_study_request(call_id,revision=REVISION,source=kwargs['source_ids'][0],request=request,role='teacher')
        return original(call_id,**kwargs)
    p.teacher.summarize=summary
    return p


def one(root,index):
    p=runner(root);sid=p.data.order[index];source=p.data.public(sid)
    path=p.artifacts/'pilot_sources'/f'{digest(sid)}.json'
    if path.exists():
        return json.loads(path.read_text())
    library=SkillLibrary()
    for previous in p.data.order[:index]:
        record=json.loads((p.artifacts/'pilot_sources'/f'{digest(previous)}.json').read_text())
        pattern=record['learning'].get('learned_pattern')
        if pattern:library.add(pattern,source=previous)
    record=ingest_source(source=source,grade=p.data.grade(sid),library=library,thinking=True,call=p._call,
        learner=p.learner,ledger=p.ledger,artifacts=p.artifacts,binding=p.seal['binding'],
        purpose='preflight_bug_retry',id_prefix=REVISION,offline_mock=False)
    record['interface_replay_provenance']=dict(original_learning_hash=p.seal['reused_interface_material'][sid],new_oracle_queries=0)
    immutable_json(path,record)
    validations=[validate_response(source,p.data.grade(sid),c['raw_content']) for c in record['calls']]
    immutable_json(p.artifacts/'semantic_checks'/f'{digest(sid)}.json',dict(source=sid,validations=validations))
    return record


def finish(root):
    import socket
    import subprocess
    from unittest.mock import patch
    p=runner(root)
    result=p.pilot()
    before=p.ledger.export()
    def deny(*args,**kwargs):raise RuntimeError('Completed pilot restore must add no calls or oracles')
    with patch.object(socket.socket,'connect',deny), patch.object(subprocess,'run',deny), patch.object(subprocess,'Popen',deny):
        restored=p.pilot()
    after=p.ledger.export()
    if before!=after or result!=restored:
        raise ValueError('Free restore changed outputs or ledger')
    atomic_json(root/'reports/rr_v2_evidence/semantic_preflight/restore.json',dict(
        network_and_subprocess_blocked=True,model_calls_added=0,oracle_views_added=0,
        sources=result['sources'],library_sha256=result['library_sha256'],binding=p.seal['binding']))
    from legal_skill_guard.rr.readiness import prepare,validate
    receipt=prepare(root)
    validate(root,p.seal['binding'])
    return dict(sources=result['sources'],patterns=result['patterns'],restore_verified=True,
                engineering_ready=receipt['engineering_ready'])


def main():
    a=argparse.ArgumentParser();a.add_argument('action',choices=['backend','prepare','one','finish']);a.add_argument('--index',type=int);args=a.parse_args()
    if args.action=='backend': backend(ROOT);return
    if args.action=='prepare':result=prepare(ROOT);print(json.dumps({'binding':result['binding']}));return
    if args.action=='finish':result=finish(ROOT);print(json.dumps(result));return
    if args.index is None or not 0<=args.index<20:raise ValueError('Original source index required')
    result=one(ROOT,args.index)
    print(json.dumps({'source':result['source'],'calls':len(result['calls']),'score':result['score'],
        'program_status':result['analysis']['program_status'],'diagnostics':result['analysis']['diagnostics'],
        'certificate_status':result['analysis']['certificate_status']}),flush=True)

if __name__=='__main__':main()
