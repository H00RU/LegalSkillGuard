"""Current method controller; every action is explicit and TEST is absent."""
import argparse
import fcntl
import json
import os
from pathlib import Path

from legal_skill_guard.rr.method_run import MethodRun,prepare_method_run
from legal_skill_guard.rr.preflight import atomic_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['prepare','build','dev'])
    parser.add_argument('--run-id',required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1]
    stage=root/'artifacts/rr_method_runtime_20261107'/args.run_id;stage.mkdir(parents=True,exist_ok=True)
    with (stage/'controller.lock').open('a') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise RuntimeError('This exact run already has a live controller; do not duplicate it')
        ticks=int(Path('/proc/self/stat').read_text().split(') ',1)[1].split()[19])
        atomic_json(stage/'controller.json',{'pid':os.getpid(),'start_ticks':ticks,'action':args.action,'status':'running'})
        try:
            result=prepare_method_run(root,args.run_id) if args.action=='prepare' else getattr(MethodRun(root,args.run_id),args.action)()
            atomic_json(stage/'controller.json',{'pid':os.getpid(),'start_ticks':ticks,'action':args.action,'status':'completed'})
            print(json.dumps(result,ensure_ascii=False))
        except BaseException as exc:
            atomic_json(stage/'controller.json',{'pid':os.getpid(),'start_ticks':ticks,'action':args.action,
                'status':'stopped','error_type':type(exc).__name__,'error':str(exc)})
            raise


if __name__=='__main__':main()
