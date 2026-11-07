"""Replay an exactly compatible TRAIN prefix through the current controller.

This script cannot generate model output. At the first unmatched wire request
it leaves the production journal ready for the ordinary controller to resume.
The original physical rows/results stay in their original run and ledger.
"""
import argparse
import base64
import fcntl
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.method_client import MethodExecutor,MethodTeacher
from legal_skill_guard.rr.method_run import MethodRun


class NoExactPaidResponse(BudgetError):pass


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    parser.add_argument('--prior-run-id',required=True);parser.add_argument('--phase',choices=['thinking','build'],default='thinking')
    args=parser.parse_args();root=Path(__file__).resolve().parents[2]
    run=MethodRun(root,args.run_id);old_stage=root/'artifacts/rr_method_runtime_20261107'/args.prior_run_id
    old=json.loads((old_stage/'seal.json').read_text())
    if old['source_manifest_hash']!=run.seal['source_manifest_hash'] or old['config']['executor']!=run.config['executor']:
        raise ValueError('Only the same original TRAIN sources/model configuration can reuse a response')
    for stage in (old_stage,run.stage):
        ctrl=json.loads((stage/'controller.json').read_text());stat=Path('/proc')/str(ctrl['pid'])/'stat'
        if stat.exists() and int(stat.read_text().split(') ',1)[1].split()[19])==ctrl['start_ticks']:
            raise BudgetError('An actual controller is live; do not duplicate it')
    with (run.stage/'controller.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        with sqlite3.connect('file:'+str(root/run.seal['ledger_path'])+'?mode=ro',uri=True) as db:
            before=db.execute('select * from calls order by id').fetchall()
            if any(r[6]=='reserved' for r in before):raise BudgetError('Reconcile the actual in-flight request first')
        eligible=[]
        allowed={'method_thinking_comparison','method_train_synthesis','method_primitive_observation'}
        for row in sorted(before,key=lambda r:r[7]):
            call_id,role,purpose,_,source,request_hash,status,_,encoded=row
            if role!='executor' or purpose not in allowed or status!='completed' or source not in run.seal['sources']['train']:
                continue
            if not any(call_id.startswith(prefix+':') for prefix in (args.prior_run_id,args.run_id)):continue
            result=json.loads(encoded);folder=Path(result['artifact_directory'])
            request=json.loads((folder/'request.json').read_text());wire=json.loads((folder/'wire_request.json').read_text())
            body=base64.b64decode(wire['body_b64']);response=json.loads((folder/'wire_response.json').read_text())
            actual=json.loads(base64.b64decode(response['body_b64']));choice=actual['choices'][0]
            if hashlib.sha256(body).hexdigest()!=wire['body_sha256'] or request['source']!=source or \
                    request['request_hash']!=request_hash or result['request_hash']!=request_hash or \
                    choice['message'].get('content','')!=result['content'] or actual['usage']!=result['usage'] or \
                    choice['message'].get('reasoning_content')!=result.get('reasoning_content') or \
                    actual.get('id')!=result.get('raw_id') or choice['finish_reason']!=result['finish_reason']:
                raise ValueError('Paid raw wire, ledger, and result do not agree: '+call_id)
            eligible.append({'call_id':call_id,'source':source,'body':body,'result':result,
                'wire_sha256':wire['body_sha256'],'response_sha256':hashlib.sha256(base64.b64decode(response['body_b64'])).hexdigest()})
        def find(body,source):
            return next((item for item in eligible if item['body']==body and item['source']==source),None)
        for item in eligible:
            assert find(item['body']+b' ',item['source']) is None
            assert find(item['body'],'unauthorized_source') is None
        uses=[]
        def paid_dispatcher(ledger,executor,source,prefix,purpose,thinking):
            def generate(messages,*,purpose,step,schema):
                run.verify()
                payload=executor.payload(messages=messages,thinking=thinking,schema=schema)
                body=json.dumps(payload,ensure_ascii=False).encode();item=find(body,source['key'])
                if item is None:raise NoExactPaidResponse('No exact prior physical wire for '+prefix+':'+str(step))
                proof={'current_logical_call_id':prefix+':'+str(step),'physical_origin_call_id':item['call_id'],
                    'source':source['key'],'prior_run_id':args.prior_run_id,'current_code_hash':run.seal['code_hash'],
                    'wire_body_sha256':item['wire_sha256'],'raw_response_sha256':item['response_sha256'],
                    'literal_wire_bytes_equal':True,'new_physical_requests':0,
                    'prior_analysis_or_scores_reused':False,'raw_response_modified':False}
                immutable_json(run.stage/args.phase/'paid_response_reuses'/(digest(prefix+':'+str(step))+'.json'),proof)
                uses.append(proof)
                return {**item['result'],'cache_hit':True,'physical_origin_call_id':item['call_id']}
            return generate
        def forbidden(*args,**kwargs):raise AssertionError('The exact-paid replay cannot call a model')
        MethodExecutor.generate=forbidden;MethodTeacher.summarize=forbidden
        run.dispatcher=paid_dispatcher
        try:
            result=getattr(run,args.phase)();outcome={'status':'entire_phase_replayed','result':result}
        except NoExactPaidResponse as exc:
            misses=[str(exc)]
            if args.phase=='thinking':
                # Profiles are independent: empty library, original source,
                # fixed seed and exact wire equality. Preserve compatible
                # later profiles without changing the sealed original order.
                ledger,executor,_,binding=run.clients('thinking',False)
                profiles=json.loads((run.stage/'thinking/template_profiles.json').read_text())
                public={s['key']:s for s in run.packet('public','train')}
                for source_id in run.seal['thinking_sources']:
                    for mode in (True,False):
                        try:run.thinking_profile(public[source_id],mode,ledger,executor,binding,profiles)
                        except NoExactPaidResponse as missing:
                            if str(missing) not in misses:misses.append(str(missing))
            outcome={'status':'compatible_profiles_and_journals_replayed_ready_for_real_resume',
                'unmatched_requests':misses,'original_fixed20_order_unchanged':True,
                'completed_profiles':len(list((run.stage/'thinking/records').glob('*.json')))}
        with sqlite3.connect('file:'+str(root/run.seal['ledger_path'])+'?mode=ro',uri=True) as db:
            assert db.execute('select * from calls order by id').fetchall()==before
        outcome.update(run_id=args.run_id,prior_run_id=args.prior_run_id,phase=args.phase,uses=uses,
            eligible_physical_responses=len(eligible),new_model_calls=0,physical_ledger_unchanged=True,
            teacher_calls=0,raw_responses_unchanged=True,
            selection='earliest exact physical wire; no correctness/label filtering')
        immutable_json(run.stage/args.phase/'exact_paid_prefix_replay.json',outcome)
        print(json.dumps(outcome,ensure_ascii=False))


if __name__=='__main__':main()
