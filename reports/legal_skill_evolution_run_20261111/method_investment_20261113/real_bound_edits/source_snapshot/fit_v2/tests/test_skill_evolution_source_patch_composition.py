"""Current-unit evidence binds retirement; matching text alone is insufficient."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.source_patch_composition import retirement_effects


class SourceBoundRetirementTests(unittest.TestCase):
    def test_repeated_quote_at_another_unit_does_not_retire_the_current_clause(self):
        before = [{'term': ['old', 'real repeated clause'], 'support_ids': [1]}]
        new = [{'term': ['new', 'real repeated clause'], 'support_ids': [2]}]
        units = [{'id': 1, 'text': 'real repeated clause'}, {'id': 2, 'text': 'real repeated clause'}]
        policy = {'old_constructor': 'old', 'old_quote_position': 1,
            'new_constructor': 'new', 'new_quote_position': 1}
        snapshot = deepcopy((before, new, policy))
        self.assertEqual(retirement_effects(before, new, units, [policy]), [[]])
        new[0]['support_ids'] = [1]
        self.assertEqual(retirement_effects(before, new, units, [policy]), [[0]])
        self.assertEqual((before, policy), (snapshot[0], snapshot[2]))

    def test_scope_guard_must_bind_the_same_current_object(self):
        before = [{'term': ['old', 'action clause'], 'support_ids': [7]}]
        action = {'term': ['action', 'scope_a', 'action clause'], 'support_ids': [7]}
        guard = {'term': ['qualifier', 'scope_b', ['kind', 'written_required']], 'support_ids': [8]}
        units = [{'id': 7, 'text': 'action clause'}, {'id': 8, 'text': 'qualification clause'}]
        policy = {'old_constructor': 'old', 'old_quote_position': 1,
            'new_constructor': 'action', 'new_quote_position': 2,
            'guards': [{'constructor': 'qualifier', 'anchor_path': [1], 'witness_path': [1],
                'checks': [{'path': [2, 1], 'value': 'written_required'}]}]}
        self.assertEqual(retirement_effects(before, [action, guard], units, [policy]), [[]])
        guard['term'][1] = 'scope_a'
        self.assertEqual(retirement_effects(before, [action, guard], units, [policy]), [[0]])
        guard['term'][2][1] = 'not_stated'
        self.assertEqual(retirement_effects(before, [action, guard], units, [policy]), [[]])

    def test_ambiguous_unit_binding_is_preserved_without_retraction(self):
        before = [{'term': ['old', 'same'], 'support_ids': [1, 2]}]
        current = [{'term': ['new', 'same'], 'support_ids': [1]}]
        policy = {'old_constructor': 'old', 'old_quote_position': 1,
            'new_constructor': 'new', 'new_quote_position': 1}
        self.assertEqual(retirement_effects(before, current,
            [{'id': 1, 'text': 'same'}, {'id': 2, 'text': 'same'}], [policy]), [[]])
