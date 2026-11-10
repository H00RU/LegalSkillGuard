"""Continuous local batches with exact original-ledger admission per dispatch.

Only this job's known live IDs may be pending. A new/resumed job must first
reconcile every pre-existing pending row. Queued but unstarted work creates no
ledger reservation; failed requests are never implicitly retried.
"""
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import fcntl
import threading

from .physical import reserve_many,dispatch_one
from legal_skill_guard.rr.ledger import BudgetError


def dispatch_stream(ledger,requests,directory,*,endpoint='http://127.0.0.1:8000/v1/chat/completions',concurrency=8,on_result=None):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    lock=ledger.path.with_suffix('.physical_stream.lock').open('a')
    fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    owned={r['call_id']for r in requests}
    try:
        if len(owned)!=len(requests):raise BudgetError('Duplicate ID in physical dispatch queue')
        with ledger.transaction() as db:
            if db.execute("select 1 from calls where status='reserved'").fetchone():raise BudgetError('Reconcile real pending requests before starting/resuming a stream')
    except BaseException:lock.close();raise
    stop=threading.Event()
    def one(request):
        if stop.is_set():raise RuntimeError('Infrastructure failure: queued work was not dispatched')
        cache,fresh=reserve_many(ledger,[request],allowed_pending=owned)
        if not fresh:return request['call_id'],{**cache[request['call_id']],'cache_hit':True}
        result=dispatch_one(ledger,request,directory,endpoint)
        if 'error'in result[1]:stop.set()
        return result
    results={};pool=ThreadPoolExecutor(max_workers=concurrency)
    futures=[pool.submit(one,r)for r in requests]
    try:
        for future in as_completed(futures):
            call_id,result=future.result();results[call_id]=result
            if on_result:on_result(call_id,result)
            if 'error'in result:raise RuntimeError('Infrastructure request failure preserved; no automatic retry: '+call_id)
    except BaseException:
        for future in futures:future.cancel()
        pool.shutdown(wait=True,cancel_futures=True)
        raise
    else:pool.shutdown(wait=True)
    finally:lock.close()
    return [results[r['call_id']]for r in requests]
