"""Pure helper code is available to both actual acquisition arms."""
import unittest

from legal_skill_guard.skill_evolution.span_compiler import execute_json, validate_procedure


class SourceProgramChecks(unittest.TestCase):
    def test_plain_helpers_can_emit_source_records_without_native_answer_codec(self):
        code = '''def find_witnesses(spans):
    return [s["id"] for s in spans if "sample" in s["text"].casefold()]
def apply(inputs, premises):
    return {"observations": find_witnesses(inputs["source_spans"]), "unresolved": None}
'''
        self.assertEqual(execute_json(code, {'source_spans': [
            {'id': 0, 'text': 'A SAMPLE occurs.'}, {'id': 1, 'text': 'Unrelated.'}]}, {},
            allow_helpers=True), {'observations': [0], 'unresolved': None})
        with self.assertRaises(ValueError):validate_procedure(code)

    def test_recursive_helpers_cannot_escape_bounded_source_execution(self):
        code = '''def first(value):
    return second(value)
def second(value):
    return first(value)
def apply(inputs, premises):
    return first(inputs)
'''
        with self.assertRaisesRegex(ValueError, 'Recursive'):validate_procedure(code, allow_helpers=True)

    def test_helper_support_retains_effect_and_introspection_checks(self):
        for operation in ['open("x")', '__import__("os")', 'inputs.__class__']:
            code = 'def helper(inputs):\n    return ' + operation + '\ndef apply(inputs, premises):\n    return helper(inputs)\n'
            with self.assertRaises(ValueError):validate_procedure(code, allow_helpers=True)


if __name__ == '__main__': unittest.main()
