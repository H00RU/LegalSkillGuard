"""Prevent future/source-reference leakage and incomplete formal matrices."""
import unittest
from copy import deepcopy

from legal_skill_guard.paired_interfaces.formal_design import assert_pair_access, design, source_roles


class FormalDesignTests(unittest.TestCase):
    def locks(self):
        counts = {'OpenExempt': 32, 'SARA_v2_Binary': 24, 'ContractNLI': 24,
                  'RuleArena_Airline': 24, 'MAUD': 24}
        sources = [name + ':' + str(i) for name, count in counts.items() for i in range(count)]
        rows = [{'key': source, 'role': role} for source, role in zip(sources[:32],
                ['development'] * 8 + ['calibration'] * 16 + ['structure_evaluation'] * 8)]
        # Spread the fixed32 across datasets as in the actual pilot.
        chosen = []; roles = ['development'] * 8 + ['calibration'] * 16 + ['structure_evaluation'] * 8
        for i in range(8):
            for name in counts:
                if i < (4 if name in ('OpenExempt', 'RuleArena_Airline') else 8):
                    chosen.append(name + ':' + str(i))
        rows = [{'key': source, 'role': role} for source, role in zip(chosen, roles)]
        source_lock = {'training_batches': [sources[i:i+16] for i in range(0, 128, 16)],
            'sources': {'train': sources, 'dev': ['freshDEV:' + str(i) for i in range(72)],
                        'test': ['freshTEST:' + str(i) for i in range(136)]}}
        return source_lock, {'rows': rows}

    def test_roles_do_not_depend_on_input_order_and_preserve_original_pilot(self):
        lock, pilot = self.locks()
        first = source_roles(lock, pilot)
        reordered = deepcopy(pilot); reordered['rows'].reverse()
        self.assertEqual(first, source_roles(lock, reordered))
        old = {row['key']: row['role'] for row in pilot['rows']}
        self.assertTrue(all(row['role'] == old[row['source']] for row in first if row['source'] in old))
        self.assertEqual(sum(row['role'] == 'reference_only' for row in first), 24)

    def test_primary_fitting_cannot_use_future_or_unpaired_reference_worlds(self):
        lock, pilot = self.locks(); rows = source_roles(lock, pilot)
        one = next(row for row in rows if row['role'] == 'reference_only')
        with self.assertRaisesRegex(ValueError, 'reference-only'):
            assert_pair_access(rows, [one['source']], 8)
        one = next(row for row in rows if row['batch'] == 8 and row['role'] in ('development', 'calibration'))
        with self.assertRaises(ValueError):
            assert_pair_access(rows, [one['source']], 1)
        assert_pair_access(rows, [one['source']], 8)

    def test_all_seven_arms_checkpoints_and_original_test_cohort_are_required(self):
        lock, pilot = self.locks(); result = design(lock, pilot)
        self.assertEqual(len(result['curve_matrix']), 28)
        self.assertEqual(len(result['final_test_matrix']), 7)
        self.assertEqual(result['primary_paired_mothers'], 96)
        self.assertEqual(result['transfer_controls']['mothers'], 12)
        lock['sources']['test'].pop()
        with self.assertRaisesRegex(ValueError, 'fresh'):
            design(lock, pilot)


if __name__ == '__main__':
    unittest.main()
