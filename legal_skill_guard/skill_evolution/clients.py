"""Reuse preserved wire transports with current TRAIN/DEV/frozen-TEST scope."""
from dataclasses import asdict
from pathlib import Path
import time
import json
import base64
import hashlib

from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.inference.codex_cli_client import (CodexCLIClient,
    render_structured_codex_prompt, strict_output_schema_issues, CODEX_TURN_INPUT_CHARACTER_LIMIT,
    canonical_json_sha256)
from .objects import digest


class GenerationHold(RuntimeError):
    """A request-boundary hold; never interrupt an in-flight physical request."""


class FrozenExecutor(ExecutorClient):
    def replay_index(self, roots):
        signature = tuple(str(Path(root)) for root in roots)
        if getattr(self, '_replay_index_signature', None) == signature:
            return self._replay_index
        with self.ledger.transaction() as db:
            settled = {r[0]: r[1:] for r in db.execute(
                "select id,result,reserved_at from calls where status='completed'")}
        index = {}
        for root in roots:
            for path in (Path(root) / 'calls').glob('*/request.json'):
                prior = json.loads(path.read_text())
                identity = prior.get('id')
                if identity not in settled:continue
                wire_path = path.with_name('wire_request.json')
                if not wire_path.exists():continue
                raw = json.loads(wire_path.read_text())
                wire = base64.b64decode(raw['body_b64'])
                wire_hash = hashlib.sha256(wire).hexdigest()
                if wire_hash != raw['body_sha256']:continue
                result, at = settled[identity]
                result = json.loads(result)
                if result.get('request_hash') != prior['request_hash']:
                    raise BudgetError('Prior exact-wire request differs from its settled physical ledger row')
                key = (prior['source'], prior['purpose'], wire_hash)
                index.setdefault(key, []).append((at, identity, wire, prior['request_hash']))
        for matches in index.values():matches.sort(key=lambda x: (x[0], x[1]))
        self._replay_index_signature, self._replay_index = signature, index
        return index

    def generate(self, *args, **kwargs):
        if (self.artifacts / 'HOLD_GENERATION').exists():
            raise GenerationHold('Held before the next physical request; in-flight calls were allowed to settle')
        roots = getattr(self, 'exact_replay_roots', ())
        if roots:
            self.validate_scope(kwargs['source'], kwargs['purpose'], kwargs['thinking'])
            payload = self.payload(messages=kwargs['messages'], thinking=kwargs['thinking'], schema=kwargs.get('schema'))
            wire = json.dumps(payload, ensure_ascii=False).encode()
            key = (kwargs['source'], kwargs['purpose'], hashlib.sha256(wire).hexdigest())
            matches = self.replay_index(roots).get(key, ())
            exact = next((m for m in matches if m[2] == wire), None)
            if exact:
                at, identity, _, request_hash = exact
                # Recheck the physical ledger on every reuse; indexing cannot
                # turn a failed, changed or orphaned request into a completion.
                with self.ledger.transaction() as db:
                    row = db.execute('select status,result,reserved_at from calls where id=?', (identity,)).fetchone()
                if not row or row[0] != 'completed' or row[2] != at:
                    raise BudgetError('Indexed physical response no longer has its original settled ledger identity')
                result = json.loads(row[1])
                if result.get('request_hash') != request_hash:
                    raise BudgetError('Indexed response differs from the preserved physical request')
                immutable_json(self.artifacts / 'exact_replay_receipts' / (digest(args[0]) + '.json'), {
                    'logical_call_id': args[0], 'physical_call_id': identity,
                    'wire_sha256': hashlib.sha256(wire).hexdigest(), 'same_source_and_purpose': True,
                    'same_frozen_executor_profile': True, 'new_physical_requests': 0})
                return {**result, 'cache_hit': True, 'reused_physical_call_id': identity}
        return super().generate(*args, **kwargs)

    def validate_scope(self, source, purpose, thinking):
        if thinking is not False or self.config['enable_thinking'] is not False:
            raise BudgetError('Executor thinking differs from the fixed OFF profile')
        self.ledger.permit(source, purpose, 'executor')


class FrozenTeacher:
    def __init__(self, ledger, artifacts, config):
        if config['retries'] != 0 or config['model'] != 'gpt-5.6-sol' or config['reasoning_effort'] != 'high':
            raise BudgetError('Teacher identity/effort or visible retry policy changed')
        self.ledger = ledger
        self.artifacts = Path(artifacts)
        self.config = config
        self.adapter = CodexCLIClient(model=config['model'], reasoning_effort=config['reasoning_effort'],
            timeout_seconds=config['timeout_seconds'], retries=0, executable=config['executable'],
            cache_root=self.artifacts / 'teacher_adapter_cache')

    def propose(self, call_id, *, source_ids, system_prompt, user_prompt, output_schema):
        if (self.artifacts / 'HOLD_GENERATION').exists():
            raise GenerationHold('Held before the next teacher request; settled work is preserved')
        self.ledger.require_train(source_ids)
        issues = strict_output_schema_issues(output_schema)
        if issues:
            raise ValueError('Teacher schema must be fixed offline before dispatch: ' + str(issues[:3]))
        if len(render_structured_codex_prompt(system_prompt, user_prompt)) > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise ValueError('Complete teacher evidence exceeds the transport cap; no truncation permitted')
        args = {'purpose': 'skill_teacher', 'system_prompt': system_prompt,
                'user_prompt': user_prompt, 'output_schema': output_schema}
        request = {'source_ids': source_ids, 'config': self.config, **args}
        adapter_hash = canonical_json_sha256(self.adapter.request_payload(**args))
        cache = self.adapter.cache_root / args['purpose'] / (adapter_hash + '.json')
        with self.ledger.transaction() as db:
            existing = db.execute('select status from calls where id=?', (call_id,)).fetchone()
        if cache.exists() and not existing:
            raise BudgetError('Unreconciled teacher cache predates this call identity; no new physical reservation')
        reserved = self.ledger.reserve(call_id, role='teacher', purpose='skill_teacher',
                                       source=source_ids[0], request=request)
        if not reserved['dispatch']:
            return {**reserved['result'], 'ledger_cache_hit': True}
        folder = self.artifacts / 'calls' / digest(call_id)
        immutable_json(folder / 'request.json', request)
        started = time.monotonic()
        try:
            response = self.adapter.generate_json(**args)
            result = {**asdict(response), 'source_ids': source_ids,
                'elapsed_seconds': time.monotonic() - started,
                'billing_basis': 'existing_authorized_Codex_CLI', 'actual_cash_invoice_available': False}
            immutable_json(folder / 'result.json', result)
            self.ledger.finish(call_id, status='completed', result=result)
            return result
        except Exception as error:
            result = {'error': type(error).__name__ + ': ' + str(error),
                'elapsed_seconds': time.monotonic() - started, 'reserved_and_charged': True}
            immutable_json(folder / 'failure.json', result)
            self.ledger.finish(call_id, status='failed', result=result)
            raise
