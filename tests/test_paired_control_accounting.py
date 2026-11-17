"""Unmetered failures are fully reserved; raw evidence is never rewritten."""
from contextlib import contextmanager
import json
import sqlite3
import unittest

from legal_skill_guard.paired_interfaces.control_accounting import TokenBudgetExecutor, usage_summary
from legal_skill_guard.rr.ledger import BudgetError


class Ledger:
    run_id = 'fixture'
    def __init__(self, rows):
        self.db = sqlite3.connect(':memory:')
        self.db.execute('create table calls(id,role,status,result)')
        self.db.executemany('insert into calls values(?,?,?,?)', [(i, 'executor', s, r) for i, s, r in rows])

    @contextmanager
    def transaction(self):
        yield self.db


class Executor:
    config = {'context_tokens': 100, 'max_tokens': 20}
    def __init__(self, rows):
        self.ledger = Ledger(rows)
        self.dispatched = []
    def tokenize(self, messages, thinking):
        return {'count': 10}
    def generate(self, identity, **kwargs):
        old = self.ledger.db.execute('select status from calls where id=?', (identity,)).fetchone()
        if old:
            if old[0] == 'failed':
                raise BudgetError('original physical failure;no retry')
            return {'cache_hit': True}
        self.dispatched.append(identity)
        return {'cache_hit': False}


class AccountingTests(unittest.TestCase):
    def test_null_usage_gets_a_conservative_bound_without_zero_imputation(self):
        rows = [('fixture:ok', 'completed', json.dumps({'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})),
                ('fixture:error', 'failed', json.dumps({'usage': None, 'error': 'HTTP400'}))]
        report = usage_summary(rows, context_tokens=100)
        self.assertEqual(report['known_input_plus_output_tokens'], 15)
        self.assertEqual(report['actual_input_plus_output_token_interval'], [15, 115])
        self.assertEqual(report['conservatively_charged_input_plus_output_tokens'], 115)
        self.assertEqual(report['unpriced_requests'], ['fixture:error'])
        executor = Executor(rows)
        budget = TokenBudgetExecutor(executor, 145)
        self.assertFalse(budget.generate('fixture:new', messages=[])['cache_hit'])
        with self.assertRaises(BudgetError):
            TokenBudgetExecutor(executor, 144).generate('fixture:too_much', messages=[])
        self.assertEqual(executor.ledger.db.execute('select result from calls where id=?', ('fixture:error',)).fetchone()[0], rows[1][2])

    def test_existing_successes_reuse_and_unchanged_failures_never_retry(self):
        rows = [('fixture:ok', 'completed', json.dumps({'usage': None})),
                ('fixture:bad', 'failed', json.dumps({'usage': None}))]
        executor = Executor(rows)
        budget = TokenBudgetExecutor(executor, 1)
        self.assertTrue(budget.generate('fixture:ok', messages=[])['cache_hit'])
        with self.assertRaises(BudgetError):
            budget.generate('fixture:bad', messages=[])
        self.assertEqual(executor.dispatched, [])

    def test_pending_or_changed_serving_context_prevents_new_dispatch(self):
        executor = Executor([('fixture:pending', 'reserved', None)])
        with self.assertRaises(BudgetError):
            TokenBudgetExecutor(executor, 1000).generate('fixture:new', messages=[])
        with self.assertRaises(BudgetError):
            usage_summary([('fixture:bad', 'completed', json.dumps({
                'usage': {'prompt_tokens': 99, 'completion_tokens': 2}}))], context_tokens=100)


if __name__ == '__main__':
    unittest.main()
