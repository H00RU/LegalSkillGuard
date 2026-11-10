"""Reuse preserved wire transports with current TRAIN/DEV/frozen-TEST scope."""
from dataclasses import asdict
from pathlib import Path
import time

from legal_skill_guard.rr.client import ExecutorClient
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.inference.codex_cli_client import (CodexCLIClient,
    render_structured_codex_prompt, strict_output_schema_issues, CODEX_TURN_INPUT_CHARACTER_LIMIT)
from .objects import digest


class FrozenExecutor(ExecutorClient):
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
        self.ledger.require_train(source_ids)
        issues = strict_output_schema_issues(output_schema)
        if issues:
            raise ValueError('Teacher schema must be fixed offline before dispatch: ' + str(issues[:3]))
        if len(render_structured_codex_prompt(system_prompt, user_prompt)) > CODEX_TURN_INPUT_CHARACTER_LIMIT:
            raise ValueError('Complete teacher evidence exceeds the transport cap; no truncation permitted')
        args = {'purpose': 'skill_teacher', 'system_prompt': system_prompt,
                'user_prompt': user_prompt, 'output_schema': output_schema}
        request = {'source_ids': source_ids, 'config': self.config, **args}
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
