"""Public-context specialization keeps multi-output and unknown distinctions."""
import ast
import unittest

from legal_skill_guard.paired_interfaces.program_residual import specialize, static_input_fields


class ProgramResidualTests(unittest.TestCase):
    def test_context_pruning_does_not_delete_another_output_or_live_duration(self):
        source = '''def apply(inputs, premises):
    if inputs["regime"] == "order":
        value = inputs["start"] < inputs["end"]
    else:
        value = inputs["end"] - inputs["start"] >= premises["duration"]
    return {"answer": value, "other": inputs["binding"]}
'''
        result = specialize(source, {'regime': 'order'}, allowed_context_fields={'regime'})
        self.assertEqual(result['input_fields'], ['binding', 'end', 'start'])
        self.assertIn('inputs[\'binding\']', result['procedure'])
        self.assertNotIn('duration', result['procedure'])
        duration = specialize(source, {'regime': 'duration'}, allowed_context_fields={'regime'})
        self.assertIn('duration', duration['procedure'])
        self.assertEqual(duration['input_fields'], ['binding', 'end', 'start'])

    def test_unknown_factual_booleans_are_not_constant_folded_to_false(self):
        source = '''def apply(inputs, premises):
    if inputs["regime"] == "A" or inputs["regime"] == "B":
        if inputs["owns"]:
            return {"answer": inputs["value"]}
    return {"answer": None}
'''
        result = specialize(source, {'regime': 'A'}, allowed_context_fields={'regime'})
        self.assertEqual(result['input_fields'], ['owns', 'value'])
        self.assertIn("if inputs['owns']", result['procedure'])
        self.assertFalse(result['certificate']['noncontext_facts_or_arithmetic_rewritten'])

    def test_context_is_explicit_and_nonescaping_static_reads_are_required(self):
        source = 'def apply(inputs, premises):\n    return {"answer": inputs["fact"]}\n'
        with self.assertRaisesRegex(ValueError, 'permitted'):
            specialize(source, {'fact': True}, allowed_context_fields={'regime'})
        with self.assertRaisesRegex(ValueError, 'nonescaping'):
            static_input_fields(ast.parse('x = inputs.get("fact")'))


if __name__ == '__main__':
    unittest.main()
