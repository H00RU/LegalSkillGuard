"""Actual contract error directs attention to its failed legal question only."""
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.teacher import trigger_failure_views


class FailureFocusTests(unittest.TestCase):
    def test_actual_MAUD_parent_targets_the_wrong_covenant_not_correct_knowledge(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/skill_evolution_actual_MAUD_failure_focus_20261112.json').read_text())
        parent = fixture['actual_parent']
        result = trigger_failure_views([{'source': parent['source'], 'execution': parent}], [parent['source']])
        self.assertEqual(len(parent['views']), 7)
        self.assertEqual([r['view'] for r in result],
            ['Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)'])
        self.assertEqual(result[0]['grade'], 0)
        self.assertEqual(result[0]['current_answer'], 'Yes')
        self.assertFalse(result[0]['controlled'])
        self.assertEqual(trigger_failure_views([{'source': parent['source'], 'execution': parent}], []), [])


if __name__ == '__main__':unittest.main()
