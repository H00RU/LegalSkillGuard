import ast
import unittest

from experiments.legal_skill_evolution_residual_validation import linked_monitor
from legal_skill_guard.skill_evolution.source_python import execute


class ResidualMaterializationTests(unittest.TestCase):
    def test_inherited_dependency_is_copied_exactly(self):
        inherited="def inherited_test(x):\n    return x == 'retained'\n\ndef apply(inputs,premises):\n    return None\n"
        raw="def apply(inputs,premises):\n    return inherited_test(inputs['word'])\n"
        code,receipt=linked_monitor([raw],inherited)
        before=ast.parse(inherited).body[0]
        after=next(n for n in ast.parse(code).body if n.name=='inherited_test')
        self.assertEqual(ast.dump(before),ast.dump(after))
        self.assertEqual(receipt[0]['function'],'inherited_test')
        self.assertTrue(execute(code,{'word':'retained'}))

    def test_missing_semantics_are_not_synthesized(self):
        raw="def apply(inputs,premises):\n    return invented_rule(inputs)\n"
        with self.assertRaisesRegex(ValueError,'No inherited helper'):
            linked_monitor([raw],"def apply(inputs,premises):\n    return None\n")


if __name__=='__main__':unittest.main()
