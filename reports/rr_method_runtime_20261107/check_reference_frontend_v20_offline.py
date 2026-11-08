"""Offline regression for the earlier-TRAIN compiler material input repair."""
from pathlib import Path
import ast
import hashlib
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
from legal_skill_guard.rr.preflight import science_files

before = science_files(ROOT)
log = ROOT / 'reports/rr_method_runtime_20261107/offline_reference_frontend_v20_20261108_log.txt'
receipt = log.with_name('offline_reference_frontend_v20_20261108.json')
tree = ast.parse((ROOT / 'tests/test_rr_horn_library_runtime.py').read_text())
test = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
            and n.name == 'test_prediction_runtime_has_no_training_oracle_or_client_import')
code = next(n.value.value for n in test.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'code' for t in n.targets))
approved = hashlib.sha256(code.encode()).hexdigest()
assert approved == '69d0bfeb189aec1cc5ade124d9e440980963beb8983d62b249bff816cfb9f14c'
private = (ROOT / 'data/packets/rr_v2/grading_only').resolve()
ledger = (ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3').resolve()
guard = '''
import os, sys
from pathlib import Path
_heldout_root = Path(PRIVATE_PATH)
_ledger_path = Path(LEDGER_PATH)
def _readonly_audit(event, args):
    if event in {'socket.connect', 'socket.bind', 'socket.sendto', 'os.system', 'os.posix_spawn', 'os.exec', 'subprocess.Popen'}:
        raise RuntimeError('Offline regression blocks network and subprocess dispatch')
    if event == 'sqlite3.connect' and Path(str(args[0])).resolve() == _ledger_path:
        raise RuntimeError('Offline regression cannot open the physical request ledger')
    if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
        p = Path(os.fsdecode(args[0])).resolve()
        if p.parent == _heldout_root and p.name in {'dev.json', 'test.json'}:
            raise RuntimeError('Offline regression blocks actual DEV and TEST labels')
sys.addaudithook(_readonly_audit)
'''.replace('PRIVATE_PATH', repr(str(private))).replace('LEDGER_PATH', repr(str(ledger)))
original_popen = subprocess.Popen
children = []

def guarded_popen(args, *rest, **kwargs):
    if args != [sys.executable, '-c', code]:
        raise RuntimeError('Only the exact read-only import child is permitted offline')
    children.append(approved)
    return original_popen([sys.executable, '-B', '-c', guard + code], *rest, **kwargs)

subprocess.Popen = guarded_popen
exec(guard.replace(", 'subprocess.Popen'", ''), {})
def blocked(*args, **kwargs):
    raise RuntimeError('Offline regression blocks network dispatch')
socket.create_connection = blocked
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
os.environ['PYTHONDONTWRITEBYTECODE'] = '1'
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'
started = time.monotonic()
with log.open('w') as output:
    oldout, olderr = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = output
    try:
        import pytest
        exit_code = int(pytest.main(['-q', *[str(p.relative_to(ROOT))
            for p in sorted((ROOT / 'tests').glob('test_rr_*.py'))]]))
    finally:
        sys.stdout, sys.stderr = oldout, olderr
after = science_files(ROOT)
evidence = {'checked_utc': datetime.now(timezone.utc).isoformat(),
    'exit_code': exit_code, 'files': before,
    'source_bytes_unchanged_during_checks': before == after,
    'elapsed_seconds': time.monotonic() - started,
    'network_blocked': True, 'actual_DEV_and_TEST_labels_blocked': True,
    'physical_request_ledger_blocked': True,
    'subprocess_blocked_except_exact_guarded_read_only_import_child': True,
    'approved_import_child_sha256': approved, 'guarded_import_children': children,
    'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest(),
    'new_model_calls': 0, 'new_oracle_views': 0,
    'previous_full_regression': 'offline_reference_frontend_v19_20261108.json',
    'backend_evidence': ['ast_scope_backend_v4.json', 'typed_operand_backend_negatives_v1.json',
                         'provenance_bounds_backend_v1.json'],
    'controller_fixture_results_are_not_research_results': True,
    'scope': 'The actual v19 wire contains an11-ID nested enum excluding s155, yet both real responses returned s155. The pinned xgrammar0.1.23 full-schema grammar reproduces accepting this forbidden value; this is a concrete schema/backend compatibility defect. Reuse the existing exact finite source-ID trie regex, preserving the original allowed set and local validation. No model setting, thinking OFF, weights, service or correctness relaxation. The actual paid earlier complete query is restored to the PAL line-list example, with only associative exact addition flattened: every leaf and all other declarations remain unchanged. No invented native query repairs are applied to actual failed output. Real v19 also redundantly redeclared the49 supplied current literals and omitted query: only typed/value/source-identical literal declarations may be removed as idempotent introductions; changed values/owners/types, observations or rules stay protected. The omitted query remains an error and the actual invalid selector is never guessed. All original literal extraction, controlled explicit item parameter, unknown25 source obligations, numeric vector sums and all-branch checking, current scope/source/type/grounding/completion checks, exact paid wire replays, library learning/freeze/restore, six-arm fairness, source budgets and TEST/network/ledger isolation remain. Offline syntax/grammar witnesses are not new real primary or skill successes.'}

receipt.write_text(json.dumps(evidence, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in evidence.items() if k != 'files'}))
raise SystemExit(exit_code or (0 if before == after else 1))
