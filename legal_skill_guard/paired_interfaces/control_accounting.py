"""Conservative token accounting when a settled failure has no usage meter.

The unchanged serving context bounds total input+output tokens for one request.
Charge that full bound for unmetered failures. Preserve unknown actual usage,
raw ledger rows, physical failures and all monetary uncertainty.
"""
import json

from legal_skill_guard.rr.ledger import BudgetError


def usage_summary(rows, *, context_tokens):
    if type(context_tokens) is not int or context_tokens <= 0:
        raise ValueError('Bind the original serving context as the per-request token upper bound')
    count, known, unpriced, pending = 0, 0, [], []
    for identity, status, raw in rows:
        if status == 'reserved':
            pending.append(identity)
            continue
        count += 1
        value = json.loads(raw)
        usage = value.get('usage')
        if (not isinstance(usage, dict)
                or any(type(usage.get(key)) is not int or usage[key] < 0
                       for key in ('prompt_tokens', 'completion_tokens'))):
            unpriced.append(identity)
        else:
            total = usage['prompt_tokens'] + usage['completion_tokens']
            if total > context_tokens:
                raise BudgetError('A reported usage exceeds the bound of the frozen serving context')
            known += total
    return {'settled_physical_requests': count, 'known_input_plus_output_tokens': known,
        'unpriced_requests': unpriced, 'pending_requests': pending,
        'unknown_usage_charge_per_request_upper_bound': context_tokens,
        'conservatively_charged_input_plus_output_tokens': known + len(unpriced) * context_tokens,
        'actual_input_plus_output_token_interval': [known, known + len(unpriced) * context_tokens],
        'unknown_actual_usage_not_imputed_as_zero': True,
        'raw_usage_or_ledger_rows_modified': False,
        'actual_cash_or_GPU_price_inferred_from_token_bound': False}


def settled_token_usage(ledger, prefix, *, context_tokens):
    with ledger.transaction() as db:
        rows = db.execute('SELECT id,status,result FROM calls WHERE id LIKE ? AND role=?',
                          (prefix + ':%', 'executor')).fetchall()
    return usage_summary(rows, context_tokens=context_tokens)


class TokenBudgetExecutor:
    def __init__(self, executor, token_cap):
        self.executor, self.ledger = executor, executor.ledger
        self.context_tokens = executor.config['context_tokens']
        if type(token_cap) is not int or token_cap <= 0:
            raise ValueError('Resolve a positive comparison cap from the original primary reads')
        if type(self.context_tokens) is not int or self.context_tokens <= 0:
            raise ValueError('The frozen context bound is missing')
        self.token_cap = token_cap

    def generate(self, call_id, **kwargs):
        with self.ledger.transaction() as db:
            old = db.execute('SELECT status FROM calls WHERE id=?', (call_id,)).fetchone()
        if old:
            # The frozen transport returns original successes or rejects the
            # unchanged previously failed identity. Neither is dispatched anew.
            return self.executor.generate(call_id, **kwargs)
        used = settled_token_usage(self.ledger, self.ledger.run_id, context_tokens=self.context_tokens)
        if used['pending_requests']:
            raise BudgetError('An actual executor request is still in flight')
        count = self.executor.tokenize(kwargs['messages'], thinking=False)['count']
        reservation = count + self.executor.config['max_tokens']
        if reservation > self.context_tokens:
            raise BudgetError('Complete predicate input plus unchanged output cap exceeds the serving context')
        if used['conservatively_charged_input_plus_output_tokens'] + reservation > self.token_cap:
            raise BudgetError('Conservative shared token budget exhausted before the next request')
        return self.executor.generate(call_id, **kwargs)
