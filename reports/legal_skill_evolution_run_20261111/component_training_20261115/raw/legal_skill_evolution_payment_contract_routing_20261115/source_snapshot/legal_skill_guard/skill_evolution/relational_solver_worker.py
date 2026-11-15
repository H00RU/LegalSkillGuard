"""Isolated clingo driver for finite learned compositions, never a model API."""
import json
import math
import resource
import sys
import time

import clingo


def main():
    request=json.load(sys.stdin);seconds=request['timeout_seconds']
    resource.setrlimit(resource.RLIMIT_CPU,(math.ceil(seconds)+1,math.ceil(seconds)+2))
    resource.setrlimit(resource.RLIMIT_AS,(1024**3,1024**3))
    resource.setrlimit(resource.RLIMIT_FSIZE,(0,0));resource.setrlimit(resource.RLIMIT_NOFILE,(16,16))
    mode=request['mode'];warnings=[];start=time.monotonic();models=0
    def run(enumeration):
        nonlocal models
        control=clingo.Control(['--warn=none'],logger=lambda code,message:warnings.append(message[-1000:]))
        control.configuration.solve.models='1' if enumeration=='one' else '0'
        if enumeration=='optimize':control.configuration.solve.opt_mode='opt'
        if enumeration in ('brave','cautious'):control.configuration.solve.enum_mode=enumeration
        control.add('base',[],request['program']);control.ground([('base',[])])
        remaining=max(0,seconds-(time.monotonic()-start));last=[];cost=[]
        def model(value):
            nonlocal last,cost,models
            # clingo's brave/cautious modes return successively accumulated
            # union/intersection models. Do not enumerate their Cartesian worlds.
            last=sorted(map(str,value.symbols(shown=True)));cost=list(value.cost);models+=1
        with control.solve(on_model=model,async_=True) as handle:
            finished=handle.wait(remaining)
            if not finished:handle.cancel()
            result=handle.get()
        status='timeout' if not finished or result.interrupted or result.unknown else 'sat' if result.satisfiable else 'unsat'
        return {'status':status,'exhausted':result.exhausted,'last_model':last,'cost':cost}
    if mode=='all':
        result=run('brave');possible=result['last_model'];certain=[]
        if result['status']=='sat' and result['exhausted']:
            result=run('cautious');certain=result['last_model']
    else:
        result=run(mode);possible=[];certain=[]
    print(json.dumps({**result,
        'possible':possible,'certain':certain,'models':models,
        'seconds':time.monotonic()-start,'clingo_version':clingo.__version__,'warnings':warnings[-3:]}))


if __name__=='__main__':main()
