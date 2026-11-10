"""Concurrent local generation over the original persistent call ledger.

Each HTTP dispatch is one charged physical request. All reservations are atomic
before dispatch; no retries are hidden, no old counts or pending rows reset.
The extension exists for actual batched serving, not an alternate budget.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import json
import time

import httpx

from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.ledger import BudgetError
from .data import write_json


def reserve_many(ledger,requests):
    cache={};fresh=[]
    with ledger.transaction() as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise BudgetError('Reconcile existing physical dispatches before another batch')
        for r in requests:
            call_id=r['call_id'];source=r['source'];purpose=r['purpose'];request=r['request']
            role='executor';partition=ledger.PURPOSES.get(purpose,(None,None))[0]
            if partition is None or ledger.PURPOSES[purpose][1]!=role or source not in ledger.sources[partition] or not call_id.startswith(ledger.run_id+':'):
                raise BudgetError('Batch differs from current fixed TRAIN/DEV authorization')
            if request.get('thinking') is not False:raise BudgetError('Thinking must remain OFF')
            h=digest({'request':request,'origin_spec':ledger.spec,'policy':ledger.policy})
            prior=db.execute('select role,purpose,source,request_hash,status,result from calls where id=?',(call_id,)).fetchone()
            if prior:
                if prior[:4]!=(role,purpose,source,h):raise BudgetError('Changed physical cache identity')
                if prior[4]!='completed':raise BudgetError('Failed/ambiguous request remains charged; no implicit retry')
                cache[call_id]=json.loads(prior[5]);continue
            db.execute('insert into calls values (?,?,?,?,?,?,?,?,NULL)',
                (call_id,role,purpose,'method_'+partition,source,h,'reserved',time.time()))
            fresh.append(r)
    return cache,fresh


def dispatch_many(ledger,requests,directory,*,endpoint='http://127.0.0.1:8000/v1/chat/completions',concurrency=8):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    cache,fresh=reserve_many(ledger,requests);results=dict(cache)
    def dispatch(r):
        call_id=r['call_id'];request=r['request'];started=time.monotonic()
        payload=request['payload'];status='completed'
        result={'source':r['source'],'call_id':call_id,'thinking':False,'request_hash':digest(request),
                'transport_retries':0,'actual_HTTP_dispatches':1,'model_alias':payload['model']}
        try:
            # HTTPTransport defaults to zero retries; trust_env=False also
            # prevents the local request being sent to an external proxy.
            with httpx.Client(timeout=600,trust_env=False,transport=httpx.HTTPTransport(retries=0)) as client:
                response=client.post(endpoint,json=payload,headers={'X-Request-Id':call_id})
            result['http_status']=response.status_code;result['raw_response']=response.text
            response.raise_for_status();wire=response.json();choice=wire['choices'][0]
            text=choice['message'].get('content');result.update(text=text,finish=choice['finish_reason'],
                reasoning_content=choice['message'].get('reasoning_content'),usage=wire.get('usage'),wire_id=wire.get('id'))
            try:result['parsed']=json.loads(text);result['parse_error']=None
            except Exception as e:result.update(parsed=None,parse_error=str(e))
        except Exception as e:status='failed';result['error']=type(e).__name__+': '+str(e)
        result['elapsed_seconds']=time.monotonic()-started
        # Durable raw response precedes terminalizing the immutable ledger.
        write_json(directory/(digest(call_id)+'.json'),{'status':status,'result':result})
        ledger.finish(call_id,status=status,result=result)
        return call_id,result
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures=[pool.submit(dispatch,r) for r in fresh]
        for future in as_completed(futures):
            call_id,result=future.result();results[call_id]=result
            print(json.dumps({'physical_result':call_id,'finish':result.get('finish'),
                'output_tokens':(result.get('usage') or {}).get('completion_tokens'),'error':result.get('error')},ensure_ascii=False),flush=True)
    return [results[r['call_id']] for r in requests]


def payload(messages,schema,*,model='common',max_tokens=8192):
    return {'model':model,'messages':messages,'temperature':.6,'top_p':.95,'top_k':20,'seed':45,
            'max_tokens':max_tokens,'chat_template_kwargs':{'enable_thinking':False},
            'response_format':{'type':'json_schema','json_schema':{'name':'native_output','strict':True,'schema':schema}}}
