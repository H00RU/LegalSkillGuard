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
log = ROOT / 'reports/rr_method_runtime_20261107/offline_reference_frontend_v23_20261109_log.txt'
receipt = log.with_name('offline_reference_frontend_v23_20261109.json')
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
    'previous_full_regression': 'offline_reference_frontend_v22_20261109.json',
    'backend_evidence': ['ast_scope_backend_v4.json', 'typed_operand_backend_negatives_v1.json',
                         'provenance_bounds_backend_v1.json'],
    'controller_fixture_results_are_not_research_results': True,
    'scope': 'Actual v6 numeric A follow-ups echo accepted declarations: source7 reaches8192 while repeating known input and fee code; source12 finishes but repeats49 protected inputs and local expressions. Replace that unnecessary full executable K payload with a read-only declaration catalog: names, input types/provenance and observation interfaces, with no input values or accepted definition bodies. The exact same selected source texts, legal targets, fact tasks and charged context are retained. The accepted query, protected definitions, scopes, primitive meanings and all accept_followup checks are unchanged. Requested factual rows precede optional new patch lines in the same strict two-field schema. Only type-sensitive canonical-identical repeated declarations may be omitted as idempotent; any changed value, type, provenance, primitive meaning, scope or expression remains rejected. Actual incomplete replies remain rejected and no missing output is reconstructed. Offline evidence counts full-K echo from complete prefix strings for diagnosis only; it does not recover or score a program. Initial128 requests are unchanged, so exact paid-wire reuse remains possible for compatible work. Current656-check evidence, original five-bank data/OFF/configuration, cumulative ledger, teacher materials, B1/MB and earlier successes/failures are preserved. A real source16 OpenExempt repair exceeded24576 solely after duplicate detailed diagnostics were added:24595 full versus24133 with the complete same root error and unchanged CURRENT input. Only when a full PAL repair would otherwise exceed context, retry request construction with that root error and field path; the full diagnostics remain in the previous immutable call. No extra model call or source truncation, and fitting historical requests remain literal-identical. A shorter request is not a semantic success; actual validation continues through the original shared build and six DEV scope.'}


receipt.write_text(json.dumps(evidence, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in evidence.items() if k != 'files'}))
raise SystemExit(exit_code or (0 if before == after else 1))
