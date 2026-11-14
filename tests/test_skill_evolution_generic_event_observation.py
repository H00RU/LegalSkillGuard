"""Real query-as-death failure and exact generic data lowering, without generation."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

import jsonschema

from legal_skill_guard.skill_evolution.generic_event_observation import lower, schema_for


ROOT = Path(__file__).resolve().parents[1]


class GenericEventObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = ROOT / 'artifacts/legal_skill_evolution_observation_reuse_schema1_20261114'
        rows = json.loads((p / 'scored_results.json').read_text())['rows']
        cls.row = next(r for r in rows if r['arm'] == 'ProgramGuided' and 'cd2ab8' in r['source'])
        cls.kernel = next(k for k in json.loads((p / 'kernel_bank.json').read_text()) if k['name'] == cls.row['kernel'])
        sources = json.loads((ROOT / 'artifacts/legal_skill_evolution_native_execution_reuse_20261114/corrected_TRAIN_views.json').read_text())
        cls.public = next(s['views'][0]['public'] for s in sources if s['key'] == cls.row['source'])

    def test_real_question_witness_cannot_be_lowered_to_death_fact(self):
        raw = self.row['observation']['views'][0]['deaths'][1]
        value = {'status': 'complete', 'events': [{'id': 'event', 'types': ['death_'],
            'attributes': [{'predicate': 'agent_', 'value': raw['person']}, {'predicate': 'start_', 'value': raw['date']}],
            'witnesses': raw['witnesses']}], 'givens': []}
        with self.assertRaises(jsonschema.ValidationError):
            lower(value, self.kernel, self.public)

    def test_source_stated_fact_is_only_serialized_without_invented_end_or_answer(self):
        raw = self.row['observation']['views'][0]['deaths'][0]
        value = {'status': 'complete', 'events': [{'id': 'event', 'types': ['death_'],
            'attributes': [{'predicate': 'agent_', 'value': raw['person']}, {'predicate': 'start_', 'value': raw['date']}],
            'witnesses': raw['witnesses']}], 'givens': []}
        result = lower(value, self.kernel, self.public)
        facts = result['bindings'][0]['inputs']['facts']
        self.assertEqual([r['predicate'] for r in facts], ['death_', 'agent_', 'start_'])
        self.assertEqual(facts[1]['arguments'], ['event', 'Alice'])
        self.assertNotIn('answer', result)
        value['status'] = 'unread'
        self.assertEqual(lower(value, self.kernel, self.public)['bindings'], [])


if __name__ == '__main__':
    unittest.main()
