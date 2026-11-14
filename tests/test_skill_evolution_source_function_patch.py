"""Protect actual acquired source modules during narrow teacher updates."""
import ast
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.source_function_patch import apply_function_edits, function_bytes


ROOT = Path(__file__).resolve().parents[1]


class SourceFunctionPatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = ROOT / 'artifacts/legal_skill_evolution_source_gap_20261114/unbound_provenance_replay/library.json'
        cls.actual = json.loads(path.read_text())['source_program']

    def test_identity_update_preserves_the_actual_complete_program(self):
        updated, receipt = apply_function_edits(self.actual, [])
        self.assertEqual(updated, self.actual)
        self.assertEqual(receipt['before_program_sha256'], receipt['after_program_sha256'])

    def test_local_definition_edit_preserves_all_other_actual_functions(self):
        old = function_bytes(self.actual)
        helper = 'sp_low'
        code = old[helper].rstrip() + '\n'
        updated, receipt = apply_function_edits(self.actual, [{'name': helper, 'code': code}])
        now = function_bytes(updated)
        self.assertTrue(all(now[name] == value for name, value in old.items() if name != helper))
        self.assertEqual(set(receipt['untouched_functions_byte_equal']), set(old) - {helper})

    def test_wrong_name_duplicate_and_effectful_edits_are_rejected(self):
        with self.assertRaises(ValueError):
            apply_function_edits(self.actual, [{'name': 'sp_low', 'code': 'def other(x):\n    return x\n'}])
        edit = {'name': 'sp_low', 'code': 'def sp_low(x):\n    return x\n'}
        with self.assertRaises(ValueError):
            apply_function_edits(self.actual, [edit, edit])
        with self.assertRaises(ValueError):
            apply_function_edits(self.actual, [{'name': 'sp_low', 'code': 'def sp_low(x):\n    import os\n    return x\n'}])


if __name__ == '__main__':
    unittest.main()
