"""Offline current-contract regression; only the exact import child is allowed."""
import ast
from contextlib import redirect_stderr,redirect_stdout
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest

from legal_skill_guard.rr.preflight import science_files


def main():
    root=Path(__file__).resolve().parents[2]
    tree=ast.parse((root/'tests/test_rr_horn_library_runtime.py').read_text())
    test=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and
              n.name=='test_prediction_runtime_has_no_training_oracle_or_client_import')
    approved=ast.literal_eval(test.body[0].value)
    original_run,original_popen=subprocess.run,subprocess.Popen
    def denied(*args,**kwargs):raise AssertionError('Blocked external action in offline regression')
    socket.socket.connect=denied;socket.create_connection=denied
    def guarded_run(command,*args,**kwargs):
        if command!=[sys.executable,'-c',approved]:return denied(command)
        prefix=("import socket,subprocess\n"
                "def _deny(*a,**k):raise AssertionError('Offline import child cannot use network/subprocess')\n"
                "socket.socket.connect=_deny;socket.create_connection=_deny;subprocess.run=_deny;subprocess.Popen=_deny\n")
        subprocess.Popen=original_popen
        try:return original_run([sys.executable,'-c',prefix+approved],*args,**kwargs)
        finally:subprocess.Popen=denied
    subprocess.run=guarded_run;subprocess.Popen=denied
    before=science_files(root);started=time.monotonic()
    folder=root/'reports/rr_method_runtime_20261107'
    log=folder/'offline_method_run_v18.txt'
    with log.open('w') as stream,redirect_stdout(stream),redirect_stderr(stream):
        code=int(pytest.main(['-q',*map(str,sorted((root/'tests').glob('test_rr*.py')))]))
    after=science_files(root);assert before==after
    receipt={'checked_utc':datetime.now(timezone.utc).isoformat(),'exit_code':code,
        'files':after,'network_blocked':True,'source_bytes_unchanged_during_checks':True,
        'subprocess_blocked_except_exact_guarded_read_only_import_child':True,
        'approved_import_child_sha256':hashlib.sha256(approved.encode()).hexdigest(),
        'log_sha256':hashlib.sha256(log.read_bytes()).hexdigest(),'elapsed_seconds':time.monotonic()-started,
        'new_model_calls':0,'new_oracle_views':0,'previous_full_regression':'offline_method_run_v17.json',
        'backend_evidence':['ast_scope_backend_v2.json','provenance_bounds_backend_v1.json'],
        'scope':'Actual repeated clause-source8192-token failure, finite distinct provenance matching engine requirements, charged incomplete-response diagnosis after schema change; canonical typed AST and nullable source-keyed scope map; exact paid IR/full-theory/A equivalence, unchanged unknown-scope/native/grounding checks, actual B graph trace, new-schema source/probe/followup persistence; exact settled teacher request/result reuse without a new physical ledger row; actual compact-v1 Bool-list, duplicate-name and provenance regression; explicit actual Boolean helper signatures; typed declaration metadata and compact expression wire; five immutable actual provenance failures, paid scope/full-theory and A-selection equivalence, rooted joint-envelope schema references, native query and all-branch rejection, fixed128/6DEV isolation/recovery and locked OFF',
        'controller_fixture_results_are_not_research_results':True}
    (folder/'offline_method_run_v18.json').write_text(json.dumps(receipt,ensure_ascii=False,sort_keys=True)+'\n')
    print(json.dumps({k:v for k,v in receipt.items() if k!='files'}));print(log.read_text()[-3500:])
    raise SystemExit(code)


if __name__=='__main__':main()
