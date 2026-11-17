from contextlib import contextmanager
import json
import sqlite3
import tempfile
from pathlib import Path
import types
import unittest

from legal_skill_guard.paired_interfaces.control_learning import (
    TokenBudgetExecutor, pack_teacher_payload, unpack_teacher_payload, validate_teacher_schemas)
from legal_skill_guard.rr.ledger import BudgetError


class BudgetTransportFixture:
    def __init__(self, path):
        self.config, self.new_generations = {'max_tokens': 20}, 0
        self.ledger = types.SimpleNamespace(run_id='fixture', transaction=self.transaction)
        self.path = path
        with sqlite3.connect(path) as db:
            db.execute('CREATE TABLE calls(id TEXT,role TEXT,status TEXT,result TEXT)')

    @contextmanager
    def transaction(self):
        with sqlite3.connect(self.path) as db:
            yield db

    def tokenize(self, messages, thinking):
        assert thinking is False
        return {'count': 10}

    def generate(self, identity, **kwargs):
        with self.transaction() as db:
            old = db.execute('SELECT status FROM calls WHERE id=?', (identity,)).fetchone()
        if old:
            return {'cache_hit': True}
        self.new_generations += 1
        return {'cache_hit': False}


class IndependentControlLearning(unittest.TestCase):
    def test_long_feedback_is_losslessly_deduplicated_even_with_literal_reference_like_objects(self):
        text = 'Exact source and actual weak trace. ' * 100
        original = {'sources': [text, {'another': text}], 'literal': {'$shared_text': 'unrelated'},
                    'short': ['yes', None, 3, False]}
        packed = pack_teacher_payload(original)
        self.assertEqual(unpack_teacher_payload(packed), original)
        self.assertLess(len(json.dumps(packed)), len(json.dumps(original)))
        validate_teacher_schemas()

    def test_full_unchanged_output_reservation_is_checked_before_a_new_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = BudgetTransportFixture(Path(tmp) / 'constructed_fixture.sqlite3')
            with self.assertRaises(BudgetError):
                TokenBudgetExecutor(transport, 29).generate('fixture:new', messages=[], thinking=False)
            self.assertEqual(transport.new_generations, 0)
            TokenBudgetExecutor(transport, 30).generate('fixture:new', messages=[], thinking=False)
            self.assertEqual(transport.new_generations, 1)

    def test_unknown_charged_usage_is_not_zero_and_existing_reuse_is_still_permitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            transport = BudgetTransportFixture(Path(tmp) / 'constructed_fixture.sqlite3')
            with transport.transaction() as db:
                db.execute('INSERT INTO calls VALUES (?,?,?,?)',
                           ('fixture:failed', 'executor', 'failed', json.dumps({'error': 'transport failure'})))
                db.execute('INSERT INTO calls VALUES (?,?,?,?)',
                           ('fixture:done', 'executor', 'completed', json.dumps({'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})))
            budgeted = TokenBudgetExecutor(transport, 100)
            with self.assertRaises(BudgetError):
                budgeted.generate('fixture:new', messages=[], thinking=False)
            self.assertTrue(budgeted.generate('fixture:done', messages=[], thinking=False)['cache_hit'])
            self.assertEqual(transport.new_generations, 0)


if __name__ == '__main__':
    unittest.main()
