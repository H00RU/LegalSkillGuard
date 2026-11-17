import json
from pathlib import Path
import tempfile
import types
import unittest

from legal_skill_guard.paired_interfaces.control_programs import (
    ControlProgramRuntime, ProgramBudgetExhausted, validate_program)


class FakeExecutor:
    """Transport fixture only; no model/ledger request or experimental claim."""
    def __init__(self):
        self.ledger = types.SimpleNamespace(run_id='constructed_program_test')
        self.calls = []

    def generate(self, call_id, **kwargs):
        self.calls.append((call_id, kwargs))
        return {'content': json.dumps({'value': 'yes'}), 'finish_reason': 'stop',
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1}, 'elapsed_seconds': 0,
                'cache_hit': False}


def program():
    return {'predicates': [{'id': 'positive', 'prompt': 'Is the supplied integer positive?',
                           'schema_mode': 'fixed', 'schema': {'type': 'string', 'enum': ['yes', 'no']}}],
        'extractors': [{'id': 'numbers', 'code':
            "def extract(inputs):\n    return [int(x) for x in re.findall(r'\\d+', inputs['public']['facts'])]\n"}],
        'composition': "def compose(inputs, predict, extractors):\n    values = extractors['numbers'](inputs)\n    answer = predict('positive', sum(values))\n    if answer == 'yes':\n        return sum(values)\n    return 0\n"}


class StrongControlPrograms(unittest.TestCase):
    def setUp(self):
        self.source = {'key': 'constructed_train_mother', 'dataset': 'fixture'}
        self.view = {'id': 'native', 'public': {'facts': '5 and 7'}, 'answer_schema': {'type': 'integer'}}

    def test_regex_extraction_neural_predicate_and_python_composition_all_execute(self):
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as tmp:
            value = ControlProgramRuntime(executor, tmp, max_calls=2).run(program(), self.source, self.view)
            self.assertEqual(value['answer'], 12)
            self.assertTrue(value['core_executed'])
            self.assertFalse(value['fallback_executed'])
            self.assertEqual(value['traces'][0]['input'], 12)
            self.assertEqual(value['traces'][0]['status'], 'validated')
            self.assertFalse(executor.calls[0][1]['thinking'])

    def test_protocol_budget_is_checked_between_physical_callbacks(self):
        value = program()
        value['composition'] = "def compose(inputs, predict, extractors):\n    total = 0\n    for n in extractors['numbers'](inputs):\n        if predict('positive', n) == 'yes':\n            total = total + n\n    return total\n"
        executor = FakeExecutor()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ProgramBudgetExhausted):
                ControlProgramRuntime(executor, tmp, max_calls=1).run(value, self.source, self.view)
            self.assertEqual(len(executor.calls), 1)
            record = json.loads(next(Path(tmp).glob('program_executions/*/result.json')).read_text())
            self.assertIn('ProgramBudgetExhausted', record['error'])
            self.assertEqual(len(record['traces']), 1)

    def test_generated_code_cannot_access_reflection_or_file_io(self):
        for code in ("def compose(inputs, predict, extractors):\n    return inputs.__class__\n",
                     "def compose(inputs, predict, extractors):\n    return open('/etc/passwd').read()\n"):
            with self.subTest(code=code), self.assertRaises(ValueError):
                validate_program({**program(), 'composition': code})


if __name__ == '__main__':
    unittest.main()
