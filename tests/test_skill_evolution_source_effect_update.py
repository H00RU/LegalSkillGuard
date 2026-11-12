"""An acquired delta must remain an executable, source-only external skill."""
import unittest

from legal_skill_guard.skill_evolution.source_effect_update import function_update
from legal_skill_guard.skill_evolution.span_compiler import execute_json


class SourceEffectUpdateChecks(unittest.TestCase):
    def test_actual_helper_delta_preserves_other_functions_and_executes(self):
        old='def helper(x):\n    return x+1\n\ndef apply(inputs,premises):\n    return helper(inputs["x"])\n'
        updated=function_update(old,['def helper(x):\n    return x+2\n'])
        self.assertEqual(execute_json(updated,{'x':4},{},allow_helpers=True),6)
        self.assertEqual(execute_json(old,{'x':4},{},allow_helpers=True),5)

    def test_duplicate_effectful_and_missing_helper_updates_fail(self):
        old='def apply(inputs,premises):\n    return inputs\n'
        for changes in ([old,old],['import os'],['def apply(inputs,premises):\n    return absent(inputs)\n']):
            with self.assertRaises(ValueError):function_update(old,changes)


if __name__=='__main__':unittest.main()
