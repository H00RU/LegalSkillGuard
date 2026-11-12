"""Real failed teacher guards must not turn extraction uncertainty into False."""
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.objects import Skill
from legal_skill_guard.skill_evolution.runtime import execute_helper


class ActualUnknownGuard(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads((Path(__file__).parent / 'fixtures' /
            'skill_evolution_actual_unknown_guard_20261112.json').read_text())
        self.skill = Skill.from_dict(self.fixture['new_skill'])

    def test_actual_current_unresolved_read_rejects_the_model_generated_false_default(self):
        current = self.fixture['unknown_current']
        self.assertEqual(set(current['unresolved_premises']),
                         {'permitted_representative_classes', 'representatives_must_have_bona_fide_need_to_know'})
        with self.assertRaisesRegex(ValueError, 'Partially unresolved bindings'):
            execute_helper(self.skill, current['inputs'], current['premises'],
                           unresolved_premises=current['unresolved_premises'])
        self.assertNotIn('permitted_representative_classes', current['premises'])

    def test_same_real_program_matches_actual_history_when_all_bindings_are_known(self):
        history = self.fixture['known_history']
        self.assertEqual(execute_helper(self.skill, history['inputs'], history['premises']),
                         history['observed_output'])


if __name__ == '__main__':unittest.main()
