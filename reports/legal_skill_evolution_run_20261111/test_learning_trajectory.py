"""Pairing regressions, using artificial metadata rather than native labels."""
from copy import deepcopy
import unittest

from .formal_cost_footprints import evidence_batch
from .learning_trajectory import paired_initial
from .native_statistics import DATASETS
from .test_native_statistics import parent


class LearningTrajectoryTests(unittest.TestCase):
    def test_batch_identity_survives_checkpoint_nesting(self):
        for path in ('Full/initial_B3/aabb.json', 'Full/B2_candidates/0.json',
                     'Full/update_context_B4.json', 'dev/Full/B0.json', 'Full/teacher_B8.json'):
            self.assertEqual(evidence_batch(path), int(next(c for c in path.split('B')[-1] if c.isdigit())))
        with self.assertRaises(ValueError):evidence_batch('initial_B3/B2.json')

    def test_native_views_stay_in_their_parent_and_unknown_difference_is_not_imputed(self):
        left = [parent(d, [1, 0]) for d in DATASETS]
        right = [parent(d, [.5, 0]) for d in DATASETS]
        summary, paired = paired_initial(left, right)
        self.assertAlmostEqual(summary['equal_five_dataset_macro'], .5)
        self.assertAlmostEqual(paired['equal_five_dataset_difference'], .25)
        left[0] = parent(DATASETS[0], [None, 0])
        self.assertIsNone(paired_initial(left, right)[1]['equal_five_dataset_difference'])

    def test_mismatched_parent_or_native_view_cannot_be_paired(self):
        left = [parent(d, [1, 0]) for d in DATASETS]
        right = deepcopy(left);right[0]['source'] += '-other'
        with self.assertRaisesRegex(ValueError, 'identical parents'):paired_initial(left, right)
        right = deepcopy(left);right[0]['views'][1]['view'] = 'other-view'
        with self.assertRaisesRegex(ValueError, 'every native view'):paired_initial(left, right)


if __name__ == '__main__':unittest.main()
