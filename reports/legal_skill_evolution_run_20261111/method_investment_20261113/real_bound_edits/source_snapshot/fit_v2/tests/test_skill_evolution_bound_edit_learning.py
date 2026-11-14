"""Exact finite learner checked against exhaustive combinations, software only."""
import itertools
import json
import random
import unittest

from legal_skill_guard.skill_evolution.bound_edit_learning import learn_effects


class BoundEffectLearningTests(unittest.TestCase):
    def test_dictionary_matches_exhaustive_objective_and_preserves_explicit_negative(self):
        rng = random.Random(45)
        for _ in range(20):
            entries = [{'id': str(i), 'policy': {'shape': 'x' * (i + 1)}} for i in range(6)]
            effects = [{'s': [i for i in range(5) if rng.randrange(2)]} for _ in entries]
            proofs = [{'source': 's', 'root_indices': [i]} for i in range(3)]
            protected = {'s': [4]}
            possible = []
            for n in range(7):
                for selected in itertools.combinations(range(6), n):
                    roots = {i for k in selected for i in effects[k]['s']}
                    if 4 in roots or not {0, 1, 2} <= roots:
                        continue
                    cost = (n, sum(len(set(effects[k]['s'])) for k in selected),
                        sum(len(json.dumps(entries[k]['policy'], sort_keys=True, separators=(',', ':')).encode()) for k in selected),
                        tuple(entries[k]['id'] for k in selected))
                    possible.append((cost, selected))
            actual = learn_effects(entries, effects, proofs, protected)
            if possible:
                cost, selected = min(possible)
                self.assertEqual(actual['objective'], list(cost[:3]))
                self.assertEqual([r['id'] for r in actual['entries']], [entries[k]['id'] for k in selected])
            else:
                self.assertEqual(actual['status'], 'not_expressible')

    def test_uneditable_erroneous_conclusion_is_not_a_success(self):
        with self.assertRaisesRegex(ValueError, 'not a witnessed'):
            learn_effects([{'id': 'a', 'policy': {}}], [{'s': [0]}],
                [{'source': 's', 'root_indices': []}], {})
