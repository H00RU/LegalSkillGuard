"""Comparison accounting fixtures;never touch the research ledger or server."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from legal_skill_guard.paired_interfaces.formal_budget import (
    ComparisonBudgetExhausted, PrefixBudgetExecutor, primary_comparison_cap)
from legal_skill_guard.rr.ledger import BudgetError


class FixtureLedger:
    def __init__(self, run_id='fixture_control'):
        self.run_id = run_id
        self.db = sqlite3.connect(':memory:')
        self.db.execute('create table calls(id text primary key,role text,purpose text,source text,status text,result text)')
    @contextmanager
    def transaction(self):
        yield self.db
    def reserve(self, identity, **kwargs):
        row = self.db.execute('select result from calls where id=?', (identity,)).fetchone()
        return {'dispatch': False, 'result': json.loads(row[0])}


class FixtureExecutor:
    def __init__(self, ledger=None):
        self.ledger = ledger or FixtureLedger()
        self.config = {'enable_thinking': False, 'context_tokens': 32768, 'max_tokens': 16}
        self.physical_calls = []
        self.failure = False
        self.cached_id = None
    def validate_scope(self, source, purpose, thinking):
        if purpose != 'skill_actor' or thinking is not False:
            raise BudgetError('fixture scope violation')
    def payload(self, **kwargs):
        return {'fixed_profile': self.config, **kwargs}
    def tokenize(self, messages, **kwargs):
        return {'count': 5}
    def generate(self, identity, **kwargs):
        if self.cached_id:
            row = self.ledger.db.execute('select result from calls where id=?', (self.cached_id,)).fetchone()
            return {**json.loads(row[0]), 'reused_physical_call_id': self.cached_id, 'cache_hit': True}
        self.physical_calls.append(identity)
        result = ({'error': 'constructed physical failure', 'usage': None} if self.failure else
            {'content': json.dumps({'value': {'native': {'answer': True, 'evidence_sentence_ids': []}}}),
             'finish_reason': 'stop', 'usage': {'prompt_tokens': 5, 'completion_tokens': 8}, 'elapsed_seconds': 0})
        self.ledger.db.execute('insert into calls values(?,?,?,?,?,?)',
            (identity, 'executor', kwargs['purpose'], kwargs['source'], 'failed' if self.failure else 'completed', json.dumps(result)))
        if self.failure:
            raise RuntimeError('constructed physical failure')
        return {**deepcopy(result), 'cache_hit': False}


class FormalBudgetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.raw = FixtureExecutor(); self.addCleanup(self.raw.ledger.db.close)
        self.executor = PrefixBudgetExecutor(self.raw, Path(self.tmp.name))
        self.kw = {'source': 'constructed', 'purpose': 'skill_actor', 'thinking': False,
                   'messages': [{'role': 'user', 'content': 'fixture'}], 'schema': {'type': 'object'}}
    def limit(self, batch, cap):
        self.executor.set_limit(batch, {'input_plus_output_token_cap': cap, 'fixture': True})

    def test_same_frozen_wire_is_one_observation_despite_repeated_callbacks(self):
        self.limit(1, 40)
        first = self.executor.generate('fixture_control:one', **self.kw)
        second = self.executor.generate('fixture_control:two', **self.kw)
        self.assertEqual(first['content'], second['content'])
        self.assertEqual(second['reused_physical_call_id'], 'fixture_control:one')
        self.assertEqual(len(self.raw.physical_calls), 1)
        self.assertEqual(self.executor.summary()['charged_input_plus_output_tokens'], 13)

    def test_old_paid_reuse_still_consumes_the_control_logical_budget(self):
        response = {'content': '{}', 'finish_reason': 'stop', 'usage': {'prompt_tokens': 5, 'completion_tokens': 8}}
        self.raw.ledger.db.execute('insert into calls values(?,?,?,?,?,?)',
            ('old_paid:one', 'executor', 'skill_actor', 'constructed', 'completed', json.dumps(response)))
        self.raw.cached_id = 'old_paid:one'; self.limit(1, 30)
        self.executor.generate('fixture_control:one', **self.kw)
        self.assertEqual(self.raw.physical_calls, [])
        self.assertEqual(self.executor.summary()['old_paid_cache_observations'], 1)
        changed = {**self.kw, 'messages': [{'role': 'user', 'content': 'other observation'}]}
        with self.assertRaises(ComparisonBudgetExhausted):
            self.executor.generate('fixture_control:two', **changed)
        self.assertTrue(self.executor.declined_request('fixture_control:two')['no_physical_request_dispatched'])

    def test_larger_prefix_can_admit_a_previously_unrequested_wire(self):
        self.limit(1, 10)
        with self.assertRaises(ComparisonBudgetExhausted):
            self.executor.generate('fixture_control:one', **self.kw)
        self.assertEqual(self.raw.physical_calls, [])
        self.limit(2, 30)
        self.executor.generate('fixture_control:two', **self.kw)
        self.assertEqual(self.raw.physical_calls, ['fixture_control:two'])

    def test_unmetered_physical_failure_is_charged_and_never_retried(self):
        self.limit(1, 40000); self.raw.failure = True
        with self.assertRaises(RuntimeError):
            self.executor.generate('fixture_control:one', **self.kw)
        self.assertEqual(self.executor.summary()['logical_observation_token_interval'], [0, 32768])
        with self.assertRaisesRegex(BudgetError, 'failed physical wire'):
            self.executor.generate('fixture_control:two', **self.kw)
        self.assertEqual(len(self.raw.physical_calls), 1)

    def test_changed_actual_response_and_future_or_lower_limits_are_rejected(self):
        self.limit(2, 100); self.executor.generate('fixture_control:one', **self.kw)
        with self.assertRaises(ValueError):
            self.limit(1, 100)
        self.raw.ledger.db.execute("update calls set result='{}'")
        with self.assertRaisesRegex(BudgetError, 'changed in the continuous ledger'):
            self.executor.summary()

    def test_primary_cap_counts_unique_real_response_ids_and_requires_completed_TRAIN(self):
        self.limit(1, 100); self.executor.generate('fixture_control:one', **self.kw)
        evidence = primary_comparison_cap(self.raw.ledger,
            [{'physical_call_id': 'fixture_control:one'}] * 2, context_tokens=32768)
        self.assertEqual(evidence['input_plus_output_token_cap'], 13)
        self.assertEqual(evidence['unique_primary_observations'], 1)
        self.raw.ledger.db.execute("update calls set purpose='skill_test'")
        with self.assertRaises(BudgetError):
            primary_comparison_cap(self.raw.ledger, [{'physical_call_id': 'fixture_control:one'}], context_tokens=32768)


if __name__ == '__main__':
    unittest.main()
