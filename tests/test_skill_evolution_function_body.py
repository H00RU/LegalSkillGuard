"""Regression from actual teacher output, without model calls or new law."""
import ast
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.teacher import compile_block, wrap_explicit_function_body
from legal_skill_guard.skill_evolution.objects import Library, premise_uses


class FunctionBodyTests(unittest.TestCase):
    def test_actual_failed_free_response_compiles_with_unchanged_body_and_values(self):
        fixture = json.loads((Path(__file__).parent / 'fixtures/skill_evolution_actual_body_only_20261112.json').read_text())
        block = fixture['raw_proposal']['blocks'][0]
        for proposal in block['revisions']:
            with self.assertRaises(ValueError):premise_uses(proposal['skill']['procedure'])
        revisions = compile_block(block, Library(), fixture['sources'], 'FreeEvolution')
        self.assertEqual(len(revisions), 3)
        for before, revision in zip(block['revisions'], revisions):
            body = ast.parse(before['skill']['procedure'])
            function = ast.parse(revision['new']['procedure']).body[0]
            self.assertEqual(ast.dump(body), ast.dump(ast.Module(body=function.body, type_ignores=[])))
            for premise in before['skill']['premises']:
                self.assertEqual(revision['new']['premises'][premise['name']]['value'], premise['value'])
            self.assertTrue(revision['representation_adaptation']['function_body_wrapper']['body_AST_unchanged'])

    def test_multiline_literal_content_is_preserved(self):
        body = 'value = """first\nsecond"""\nreturn {"answer": value}\n'
        wrapped, receipt = wrap_explicit_function_body(body)
        self.assertEqual(ast.literal_eval(ast.parse(wrapped).body[0].body[0].value), 'first\nsecond')
        self.assertTrue(receipt['body_AST_unchanged'])

    def test_missing_return_mixed_definitions_and_effects_are_not_repaired(self):
        for body in ('value = inputs["x"]', 'def helper():\n    return 1\nreturn helper()'):
            with self.assertRaises(ValueError):wrap_explicit_function_body(body)
        wrapped, _ = wrap_explicit_function_body('import os\nreturn {"answer": 1}')
        with self.assertRaises(ValueError):premise_uses(wrapped)
        wrapped, _ = wrap_explicit_function_body('return {"answer": invented_legal_rule(inputs)}')
        with self.assertRaises(ValueError):premise_uses(wrapped)

    def test_existing_full_procedure_is_byte_identical(self):
        full = 'def apply(inputs, premises):\n    return {"answer": True}\n'
        self.assertEqual(wrap_explicit_function_body(full), (full, None))


if __name__ == '__main__':unittest.main()
