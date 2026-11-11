"""Checks of the production external learner, not model/innovation evidence."""
import json
from pathlib import Path
import tempfile
import unittest
from dataclasses import replace

from legal_skill_guard.skill_evolution.objects import Skill, Library, lift, coupled_blocks
from legal_skill_guard.skill_evolution.revisions import ReplayBudget, VersionTable, rank_patterns, observe_transfer


def skill():
    return Skill(id='fixture', intent='fixture only', procedure='def apply(inputs, premises):\n    return min(inputs["x"], premises["limit"]) + premises["extra"] + premises["limit"]\n',
        inputs={}, outputs={}, premises={name: {'mode': 'constant', 'type': 'integer', 'value': value,
        'origin': {'source': 'fixture', 'span': str(value)}} for name, value in [('limit', 5), ('extra', 2)]},
        reads=(), semantic_records=({'id': 'record', 'ports': ['limit', 'extra']},),
        source_obligations=(), source_provenance=({'source': 'fixture'},)).validate()


class ExternalLearningTests(unittest.TestCase):
    def test_allports_keeps_a_single_joint_read_beyond_three_premises(self):
        old = skill()
        premises = {name: {'type': 'integer', 'mode': 'constant', 'value': index,
            'origin': {'source': 'fixture'}} for index, name in enumerate(('a', 'b', 'c', 'd'))}
        old = replace(old, premises=premises, semantic_records=(), procedure='def apply(inputs, premises):\n    return premises["a"] + premises["b"] + premises["c"] + premises["d"]\n').validate()
        reader = {'id': 'all', 'question': 'Current source fields', 'source_locator': 'current source',
            'schema': {'type': 'object'}, 'bindings': {name: name for name in premises}}
        with self.assertRaises(ValueError):lift(old, list(premises), reader)
        new = lift(old, list(premises), reader, all_ports=True)
        self.assertEqual(len(new.reads), 1)
        self.assertEqual(len(new.premises), 4)

    def test_lift_rebinds_repeated_ports_and_preserves_procedure(self):
        old = skill()
        reader = {'id': 'r', 'question': 'Read current source premises', 'source_locator': 'current source',
                  'schema': {'type': 'object'}, 'bindings': {'limit': 'a', 'extra': 'b'}}
        new = lift(old, ['limit', 'extra'], reader)
        self.assertEqual(old.procedure, new.procedure)
        self.assertTrue(all(v['mode'] == 'read' and 'value' not in v for v in new.premises.values()))
        self.assertEqual(old.premises['limit']['value'], 5)
        self.assertEqual(coupled_blocks(old), [('extra', 'limit')])

    def test_unknown_versions_do_not_prove_joint_necessity(self):
        table = VersionTable(('oldnewA', 'oldnewB'), ('trigger',), ('history',))
        for mask, source, value in [(0, 'trigger', 0), (3, 'trigger', 1), (0, 'history', 1), (3, 'history', 1)]:
            table.observe(mask, source, value, {})
        self.assertTrue(table.acceptable(3))
        self.assertEqual(table.minimal_blocks(), [])
        self.assertIsNone(table.choose({3: 0}))
        self.assertFalse(table.export()['complete'])

    def test_true_joint_and_historical_nonregression(self):
        table = VersionTable(('A', 'B'), ('t',), ('h',))
        for mask, grades in enumerate([(0.5, 1), (0.25, 1), (0.5, 1), (1, 1)]):
            for source, grade in zip(('t', 'h'), grades):
                table.observe(mask, source, grade, {'actual': 'test fixture'})
        self.assertEqual(table.classify(), 'joint_needed')
        self.assertEqual(table.minimal_blocks(), [3])
        self.assertEqual(table.choose({m: 0 for m in range(4)}), 3)
        bad = VersionTable(('A',), ('t',), ('h',))
        for mask, grades in enumerate([(0, 1), (1, .5)]):
            for source, grade in zip(('t', 'h'), grades):bad.observe(mask, source, grade, {})
        self.assertFalse(bad.acceptable(1))

    def test_common_selection_ranks_gain_before_edit_count(self):
        table = VersionTable(('A', 'B'), ('t',), ())
        for mask, grade in enumerate([0, .5, 0, 1]):table.observe(mask, 't', grade, {})
        self.assertEqual(table.minimal_blocks(), [1])
        self.assertEqual(table.classify(), 'single_sufficient')
        self.assertEqual(table.choose({m: 0 for m in range(4)}), 3)

    def test_adverse_transfer_updates_the_exact_context(self):
        context = {'upstream': 'preliminary', 'downstream': 'terminal-use'}
        pattern = {'id': 'p', 'verified_relation_fields': {'upstream': 'preliminary'},
                   'counts_by_context': {}, 'observed_read_tokens': 2}
        table = VersionTable(('A', 'B'), ('t',), ())
        for mask, grade in enumerate([0, 1, 0, 1]):table.observe(mask, 't', grade, {})
        self.assertEqual(observe_transfer(pattern, context, table), 'single_sufficient')
        self.assertEqual(rank_patterns([pattern], {'upstream': 'unknown'}), [])
        self.assertEqual(rank_patterns([pattern], context), ['p'])
        self.assertEqual(next(iter(pattern['counts_by_context'].values()))['single_sufficient'], 1)

    def test_library_persistence_and_fixed_search_budget(self):
        library = Library(skills={'fixture': skill()})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'B0.json';library.save(path)
            self.assertEqual(Library.load(path).hash, library.hash)
            value = json.loads(path.read_text());value['skills']['fixture']['intent'] = 'changed'
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):Library.load(path)
        budget = ReplayBudget()
        for _ in range(3):budget.admit_block(3, 8)
        self.assertEqual(budget.logical_executions, 192)
        with self.assertRaises(ValueError):budget.admit_block(1, 1)


if __name__ == '__main__':
    unittest.main()
