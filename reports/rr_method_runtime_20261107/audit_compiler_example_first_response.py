"""Replay the fresh executor failure without generation, labels or IR edits."""
from pathlib import Path
from datetime import datetime, timezone
import base64
import hashlib
import json
import socket
import sqlite3
import subprocess

ROOT = Path(__file__).resolve().parents[2]
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.coverage import digest
from legal_skill_guard.rr.compiler_contract import decode_compiler_response
from legal_skill_guard.rr.source_inference import _decode
from legal_skill_guard.rr.source_program import compile_source
from legal_skill_guard.rr.source_structure import inspect_source
from legal_skill_guard.rr.source_validation import validation_feedback
from legal_skill_guard.rr.wire_validation import validate_wire

def blocked(*args, **kwargs):
    raise RuntimeError('Failure replay cannot generate or spawn a model')
socket.create_connection = blocked
socket.socket.connect = blocked
subprocess.Popen = blocked
run = 'compiler_example_executor_v1_20261108'
stage = ROOT / 'artifacts/rr_method_runtime_20261107' / run
seal = json.loads((stage / 'seal.json').read_text())
saved = json.loads((stage / 'result.json').read_text())
cfg = json.loads((ROOT / 'configs/rr_v2_preflight.json').read_text())
with sqlite3.connect('file:' + str(ROOT / cfg['ledger_path']) + '?mode=ro', uri=True) as db:
    call = db.execute('select role,source,request_hash,status,result from calls where id=?',
                      (run + ':compile',)).fetchone()
    baseline = db.execute("select id,result from calls where source=? and id like ? order by reserved_at",
        (seal['source']['key'], 'method_runtime_ast_v1_20261107:build:%')).fetchall()
assert call[:2] == ('executor', seal['source']['key']) and call[3] == 'completed'
raw = json.loads(call[4])
folder = Path(raw['artifact_directory'])
assert json.loads((folder / 'result.json').read_text()) == raw
request = json.loads((folder / 'request.json').read_text())
wire_request = json.loads((folder / 'wire_request.json').read_text())
wire_response = json.loads((folder / 'wire_response.json').read_text())
body = base64.b64decode(wire_request['body_b64'])
response_body = base64.b64decode(wire_response['body_b64'])
payload = json.loads(body)
provider = json.loads(response_body)
assert hashlib.sha256(body).hexdigest() == wire_request['body_sha256']
assert request['request_hash'] == raw['request_hash'] == call[2]
assert provider['choices'][0]['message']['content'] == raw['content']
assert provider['usage'] == raw['usage']
assert payload['chat_template_kwargs']['enable_thinking'] is False
parsed = _decode(raw['content'])
validate_wire(parsed, seal['schema'])
program = decode_compiler_response(parsed, seal['source'], seal['config']['library'])
assert program == json.loads((stage / 'program.json').read_text())
try:
    compile_source(seal['source'], program, library=seal['config']['library'])
except Exception as exc:
    replay = {'type': type(exc).__name__, 'message': str(exc)}
else:
    raise AssertionError('The original rejection must remain rejected')
assert replay == {'type': saved['error_type'], 'message': saved['error']}
feedback = validation_feedback(seal['source'], program)
structure = inspect_source(seal['source'])
texts = {c.id: structure.ledger.text[c.start:c.end] for c in structure.ledger.clauses}
binding = program['bindings'][9]
assert binding['name'] == 'v_employer_domestic_service' and binding['value'] == 'Alice'
assert all('Alice' not in texts[s] for s in binding['sources'])
old = []
for cid, encoded in baseline:
    value = json.loads(encoded)
    old_payload = json.loads(base64.b64decode(json.loads(
        (Path(value['artifact_directory']) / 'wire_request.json').read_text())['body_b64']))
    generation = {k: v for k, v in old_payload.items() if k not in {'messages', 'response_format'}}
    assert generation == {k: v for k, v in payload.items() if k not in {'messages', 'response_format'}}
    assert old_payload['response_format'] == payload['response_format']
    old_user = json.loads(old_payload['messages'][1]['content'])
    new_user = json.loads(payload['messages'][1]['content'])
    assert old_user['units'] == new_user['units'] and old_user['task_id'] == new_user['task_id']
    old.append({'call_id': cid, 'finish_reason': value['finish_reason'], 'usage': value['usage'],
                'elapsed_seconds': value['elapsed_seconds'], 'generation_and_schema_equal': True})
result = {'checked_utc': datetime.now(timezone.utc).isoformat(), 'run_id': run,
    'source': seal['source']['key'], 'role': call[0], 'physical_call_id': run + ':compile',
    'wire_body_sha256': hashlib.sha256(body).hexdigest(),
    'wire_response_sha256': hashlib.sha256(response_body).hexdigest(),
    'raw_content_sha256': hashlib.sha256(raw['content'].encode()).hexdigest(),
    'program_hash': digest(program), 'actual_wire_schema_pass': True,
    'production_error_reproduced_exactly': replay, 'source_only_feedback': feedback,
    'first_bad_binding': {'path': 'bindings[9].value', 'declared_type': binding['type'],
        'actual_JSON_type': type(binding['value']).__name__, 'type_error': False,
        'expected': 'literal appears in the explicitly cited public unit', 'actual': binding,
        'cited_text': {s: texts[s] for s in binding['sources']}},
    'diagnosis': 'Model output errors: wrong provenance, duplicate symbols, undeclared variables and invalid rule residuals. Current schema/decoder agree; runtime correctly rejects the source violation.',
    'lossless_complete_IR_recovery_possible': False,
    'candidate_modified': False, 'grading_labels_read': False, 'network_blocked': True,
    'new_model_calls_by_audit': 0, 'new_oracle_views': 0,
    'actual_new_probe_requests': 1, 'finish_reason': raw['finish_reason'],
    'usage': raw['usage'], 'elapsed_seconds': raw['elapsed_seconds'],
    'baseline_same_original_source': old,
    'new_executor_api_cash_usd': 0, 'GPU_allocation_cost_usd': None,
    'new_teacher_requests': 0, 'core_success': False, 'full_goal_complete': False}
immutable_json(ROOT / 'reports/rr_method_runtime_20261107/compiler_example_first_response_audit_v1.json', result)
print(json.dumps({'wire_pass': True, 'error_reproduced': True, 'source_only_issues': len(feedback['issues']),
    'fresh_output_tokens': raw['usage']['completion_tokens'], 'new_calls_by_audit': 0}))
