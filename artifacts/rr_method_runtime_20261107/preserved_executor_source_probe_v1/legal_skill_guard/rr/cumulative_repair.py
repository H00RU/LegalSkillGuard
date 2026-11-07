"""Serial, bounded repair validation on the existing physical request ledger."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from .checkpoint import immutable_json
from .client import ExecutorClient
from .coverage import digest
from .data_store import PreflightData
from .engine import proposal_schema, wire_messages, source_text
from .ledger import BudgetLedger
from .preflight import atomic_json, science_files
from .schema_validation import execution_binding, source_grounding, validate_response
from .strict_contract import TARGETS, close_expression_inputs

STAGE = 'artifacts/rr_v2_preflight/cumulative_repair'


def inputs(root):
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    data = PreflightData(root, root / cfg['source_manifest'])
    return cfg, data


def closed_inputs(root, source):
    cfg = json.loads((root / 'configs/rr_v2_preflight.json').read_text())
    plan = cfg.get('closed_input_repair')
    if not plan or plan['source'] != source['key']:
        return None
    previous = json.loads((root / plan['validation']).read_text())['analysis']['proposal']
    bindings = previous['program']['body']['bindings']
    checks = [c for c in source_grounding(source_text(source), source["dataset"], previous)['checks'] if 'binding' in c]
    if len(checks) != len(bindings) or not bindings or not all(c['pass'] for c in checks):
        raise ValueError('Only already grounded public input bindings may be reused verbatim')
    return [{key: b[key] for key in ['name', 'type', 'value', 'source']} for b in bindings]


def schema_for(root, source):
    schema = proposal_schema(source['dataset'], source=source)
    bindings = closed_inputs(root, source)
    return close_expression_inputs(schema, bindings) if bindings else schema


def prompts(root, source):
    # No grading records or previous answer/program content enter this builder.
    prompt = wire_messages(source)
    library = json.loads((root / 'artifacts/rr_v2_preflight/oracle_guard/partial_library.frozen.json').read_text())
    prompt[0]['content'] += '\nCurrent frozen parameterized role constraints: ' + json.dumps(
        [p['pattern'] for p in library['content']['patterns']], ensure_ascii=False)
    prompt[1]['content'] += ('\nMechanical contract repair: return an explicit executable query with every branch. '
        'Source IDs are only citations. Do not serialize answer mappings or an old program into scalar bindings.')
    bindings = closed_inputs(root, source)
    if bindings:
        prompt[1]['content'] += ('\nThese input bindings were already quoted correctly. Preserve them exactly. '
            'Use only their declared variable names; citation strings and rule constants may be quoted directly '
            'from the public rules with source links. Construct both EC and EV program outputs. '
            'Each extracted s_asset input has one key in EC and one in EV. Put all its claims in its array, '
            'never repeat the same asset key for different citations. '
            'No prior answer or rule program is supplied. Fixed bindings: ' + json.dumps(bindings, ensure_ascii=False))
    return prompt


def prepare(root: Path, revision: str, change: str):
    cfg, data = inputs(root)
    protocol = json.loads((root / 'reports/legalskillguard_rule_reasoning_protocol_v2.json').read_text())
    if cfg['formal_run_enabled'] or cfg['frozen_test_enabled'] or protocol['run_enabled']:
        raise ValueError('Main training and evaluation remain disabled')
    auth = json.loads((root / cfg['repair_execution_policy']).read_text())
    offline = json.loads((root / 'reports/rr_v2_evidence/offline_latest.json').read_text())
    if offline['exit_code'] or not offline['network_blocked'] or any(
            hashlib.sha256((root / p).read_bytes()).hexdigest() != h for p, h in offline['files'].items()):
        raise ValueError('Current network-blocked offline checks required')
    files = science_files(root)
    required = {p for p in files if p.startswith(('legal_skill_guard/rr/', 'experiments/rr_v2', 'tests/test_rr', 'tests/fixtures/rr_'))}
    if not required <= set(offline['files']):
        raise ValueError('Offline evidence must cover all current implementation and regressions')
    backend = json.loads((root / 'reports/rr_v2_evidence/cumulative_repair/backend_precheck.json').read_text())
    checked = {r['source']: r for r in backend['records']}
    if not backend['network_blocked'] or len(checked) != 12:
        raise ValueError('Twelve affected source schemas need the actual installed decoder check')
    binding = execution_binding(root)
    origin = json.loads((root / 'artifacts/rr_v2_preflight/strict_contract_round2/seal.json').read_text())['binding']
    ledger = BudgetLedger(root / cfg['ledger_path'], sources=data.manifest['allowlist'],
                          code_hash=origin['code_hash'], config_hash=origin['config_hash'])
    ledger.register_cumulative_policy(auth)
    ledger.register_repair_revision(revision, new_binding={k: binding[k] for k in ('code_hash', 'config_hash')},
        change=change, offline_evidence_hash=digest({'offline': offline, 'backend': backend}))
    planned = {}
    for source_id in data.order:
        source = data.public(source_id)
        if source['dataset'] not in TARGETS:
            continue
        messages, schema = prompts(root, source), schema_for(root, source)
        record = checked[source_id]
        if record['schema_hash'] != digest(schema) or record['messages_hash'] != digest(messages) or not record['context_fits']:
            raise ValueError('Prompt/schema differs from decoder/tokenization evidence')
        schema_json = json.dumps(schema, ensure_ascii=False)
        if hashlib.sha256(schema_json.encode()).hexdigest() != record['schema_wire_sha256']:
            raise ValueError('Literal schema order differs from installed-decoder check')
        planned[source_id] = {'messages': messages, 'schema_json': schema_json, 'tokenization': record['tokenization']}
    seal = {'revision': revision, 'change': change, 'binding': binding, 'protected_files': files,
            'authorization_hash': digest(auth), 'offline_hash': digest(offline), 'backend_hash': digest(backend),
            'frozen_library_sha256': hashlib.sha256((root / 'artifacts/rr_v2_preflight/oracle_guard/partial_library.frozen.json').read_bytes()).hexdigest(),
            'config': cfg, 'planned': planned, 'executor_cumulative_max': 96, 'teacher_calls_added': 0}
    immutable_json(root / STAGE / revision / 'seal.json', seal)
    return {'revision': revision, 'binding': binding, 'planned_sources': len(planned), 'executor_used': ledger.export()['executor_used']}


def load(root, revision):
    seal = json.loads((root / STAGE / revision / 'seal.json').read_text())
    cfg, data = inputs(root)
    if science_files(root) != seal['protected_files'] or execution_binding(root) != seal['binding'] or cfg != seal['config']:
        raise ValueError('Sealed scientific implementation/config changed; preserve and verify a new revision')
    auth = json.loads((root / cfg['repair_execution_policy']).read_text())
    if digest(auth) != seal['authorization_hash'] or hashlib.sha256((root /
            'artifacts/rr_v2_preflight/oracle_guard/partial_library.frozen.json').read_bytes()).hexdigest() != seal['frozen_library_sha256']:
        raise ValueError('Authorization/frozen library changed')
    ledger = BudgetLedger(root / cfg['ledger_path'], sources=data.manifest['allowlist'],
                          code_hash=seal['binding']['code_hash'], config_hash=seal['binding']['config_hash'])
    return seal, data, ledger


def run_one(root: Path, revision: str, source_index: int, *, mode='validation'):
    seal, data, ledger = load(root, revision)
    source_id = data.order[source_index]
    if source_id not in seal['planned']:
        raise ValueError('Only affected original fixed training sources are eligible')
    planned = seal['planned'][source_id]
    # Literal schema JSON preserves operator-first grammar order through restore.
    schema = json.loads(planned['schema_json'])
    cfg = seal['config']['executor']
    payload = {'model': cfg['model'], 'messages': planned['messages'], 'temperature': cfg['temperature'],
               'top_p': cfg['top_p'], 'top_k': cfg['top_k'], 'max_tokens': cfg['max_tokens'], 'seed': cfg['seed'],
               'chat_template_kwargs': {'enable_thinking': True}, 'response_format': {'type': 'json_schema',
                'json_schema': {'name': 'rr_joint_proposal', 'strict': True, 'schema': schema}}}
    call_id = f'cumulative:{revision}:{source_id}'
    ledger.register_repair_request(call_id, revision=revision, source=source_id, payload_hash=digest(payload), mode=mode)
    stage = root / STAGE / revision
    path = stage / 'validations' / (digest(call_id) + '.json')
    if path.exists():
        return {'cached_validation': True, 'call_id': call_id, 'outcome': json.loads(path.read_text())}
    client = ExecutorClient(ledger, stage, cfg)
    # Readiness is read-only. tokenize is the serving endpoint, and has no generation retry.
    client.readiness()
    runtime_path = root / 'docs/rr_v2/runtime_state.json'
    runtime = json.loads(runtime_path.read_text())
    runtime.update(goal_status_verified='active', current_phase='cumulative_repair_single_request',
                   live_client_processes=[os.getpid()], live_call_id=call_id, blocking_condition=None)
    atomic_json(runtime_path, runtime)
    print(json.dumps({'dispatch': call_id, 'mode': mode, 'executor_before': ledger.export()['executor_used']}), flush=True)
    try:
        wire = client.generate(call_id, source=source_id, purpose='preflight_bug_retry',
            messages=planned['messages'], thinking=True, schema=schema)
        outcome = validate_response(data.public(source_id), data.grade(source_id), wire['content'])
        outcome['wire_request_hash'] = wire['request_hash']
    except Exception as exc:
        with ledger.transaction() as db:
            row = db.execute('SELECT status FROM calls WHERE id=?', (call_id,)).fetchone()
        if not row or row[0] == 'reserved':
            atomic_json(stage / 'reconciliation_needed.json', {'call_id': call_id, 'error': repr(exc), 'row': row})
            raise
        outcome = {'pass': False, 'reason': 'charged_wire_failure', 'error': repr(exc)}
    immutable_json(path, outcome)
    ledger.record_repair_outcome(call_id, outcome)
    runtime.update(current_phase='cumulative_repair_request_terminal_review', live_client_processes=[],
                   live_call_id=None, executor_generations=ledger.export()['executor_used'],
                   teacher_generations=ledger.export()['teacher_used'], executor_cumulative_max=96,
                   last_repair_revision=revision, last_validation=str(path),
                   next_required='Inspect actual outcome; changed failed sample needs verified revision; validated version may continue original sources')
    atomic_json(runtime_path, runtime)
    summary = {k: outcome.get(k) for k in ('pass', 'reason', 'typed_schema_pass', 'model_IR_executed',
                                         'program_answer', 'program_native_score', 'source_grounding')}
    print(json.dumps({'call_id': call_id, 'executor_after': ledger.export()['executor_used'], **summary}), flush=True)
    return summary
