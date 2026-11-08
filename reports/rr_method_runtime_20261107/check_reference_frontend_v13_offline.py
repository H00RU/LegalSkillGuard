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
log = ROOT / 'reports/rr_method_runtime_20261107/offline_reference_frontend_v13_20261108_log.txt'
receipt = log.with_name('offline_reference_frontend_v13_20261108.json')
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
    'previous_full_regression': 'offline_reference_frontend_v12_20261108.json',
    'backend_evidence': ['ast_scope_backend_v4.json', 'typed_operand_backend_negatives_v1.json',
                         'provenance_bounds_backend_v1.json'],
    'controller_fixture_results_are_not_research_results': True,
    'scope': 'Common MethodRun inference now consumes the aligned logic/PAL/identical-statute frontends for all six arms. Existing teacher templates enter the learned prefix only after their own original TRAIN source, persist through B1/B8 and exact restore, and are shared with every control; B patterns alone are masked by policy. Exact paid literal-wire TRAIN replay validates physical ledger/raw provenance and reruns current decoding/execution, never imports old scores; tampering is rejected. Truncated generations stop that representation retry, not the Goal. Actual paid legal fragment recovery hoists only an already generated integer with exactly one charged factual owner and proves byte-equivalent expression AST after inlining; a factual evidence marker is stripped only for its exact own source and verbatim suffix. Missing/invented constants and wrong evidence stay rejected. The actual accepted normalized observation rows are retained for later B variant rebinding. Real paid logic and legal components replay through the integrated inference journal without another dispatch; JSON-native canonicalization makes resumed outcomes identical. Actual legal template instance v11 is replayed exactly, including its current-actor observations, actual separating batch and 49 inactive unknowns, without crediting teacher code as independent executor generation. PAL legal follow-ups now return only a source-local fragment plus the exact requested factual rows. Accepted query, scopes, rules and primitive meanings cannot be replaced; selected proper residuals keep Boolean types and new declarations must cite charged source context. Exact tokenizer planner cost includes newly required factual context and is checked against physical dispatch. Unknown/omitted translations remain unresolved; no guessed legal truth is accepted. Runtime prompts now expose existing typed primitive/connector signatures and actual available pattern hashes, removing a genuine B interface omission. The real v10 entity-binding failures are preserved and rejected unchanged. Current instances use a schema enumerating actual current factual entity mentions and target-linked rule output names; deterministic code only composes the selected guarded outputs. Old predicates, source IDs, arbitrary code, default answers and unrelated outputs cannot pass. Actual training employer/employee role hints come only from the earlier public employed phrase, not labels. This replaces the failed unconstrained entity strings and generated query expressions without supplying factual truth. The original scope/definition-only lowerer input remains supported; inferred contexts need actual declared primitive inputs. The v9 failed regression (585 pass, two missing-bindings interface failures) is preserved and was not dispatched to a model. Byte-identical learned statutes can be instantiated only with fresh executor entity binding and guarded query, without old factual truth, answer or numeric bindings. Real parsed parent conjunctions enforce inherited child applicability and preserve the parent output; actual student scope requires both institution service and enrollment. Factual temporal requests expose only public reference years. This does not count teacher code as new executor full-program generation. Actual complete teacher recovery: partition already-declared fact evidence from rule ownership without new inputs or coverage; retain exact citation-qualified propositions as unknown legal Booleans only when expression DAG, all 51 Boolean domains, actor provenance and factual source coverage remain unchanged. Actual source46 list fragment is accepted only through the executable source44 enclosing conditional compound and additional inputs; standalone whole rules, absent parents and trivial/unused contexts remain rejected. Canonical rendering roundtrips exactly; this is a teacher material recovery, never executor/core success. Explicit SARA query section paths are source-only prompt and diagnostic metadata, not effect footprints or discharged obligations. The actual wrong-target executor programs are diagnosed without mutation; the actual correct-but-partial teacher program still has 50 unknown source scopes and is not a full template or core success. Full-source teacher acquisition intent is explicit and differs from the earlier query-only request. The preserved historical feedback fixture is not rewritten: its regression requires every old diagnostic unchanged and only the intended additional concrete scope diagnostics. The first v5 full regression (569 pass/one obsolete exact-feedback comparison) remains recorded; no model was called from that failed binding. Actual failed PAL scope records retain their semantic rejection and receive precise field/source diagnostics without mutation; keyword factual roles and literal-title ID lists expose the existing contract, whole-source legal templates persist/freeze exactly and incomplete programs are rejected. TRAIN teacher acquisition uses the same short code wrapper without native answers. PAL-style compact Python source expressions lower without executing code to the unchanged source/type/scope/resource/completion checks; real earlier teacher control roundtrips exactly, invented facts, missing rules, unsafe code and scope bypass remain rejected. Source-aligned atom generation preserves explicit original if/and/then skeletons, every sign and argument remains model-supplied and whole-source checked; prior real teacher templates project only after exact semantic validation, current source follows demonstrations, finite flat schema order is sealed. Concrete earlier-TRAIN compiler template update, exact freeze/restore, self/future exclusion, actual multiword identifier encoding and unmodified placeholder-failure rejection; short teacher code envelope retains full semantic checking. Reference-based model Horn frontend: source-annotated formal statements, independent public-source checking without prediction substitution, explicit negation and variable sharing, unresolved missing units, actual stored-graph execution, failure without graph replacement. All prior RR regressions and earlier-TRAIN example isolation. '
             'self/future exclusion before dispatch, unmodified empty-example requests, native contract '
             'selection and identical compiler material for all six arms. Historical teacher examples '
             'are compiler inputs only, never fresh executor output or core success.'}
receipt.write_text(json.dumps(evidence, sort_keys=True) + '\n')
print(json.dumps({k: v for k, v in evidence.items() if k != 'files'}))
raise SystemExit(exit_code or (0 if before == after else 1))
