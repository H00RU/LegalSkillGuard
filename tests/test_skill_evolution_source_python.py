import unittest
from legal_skill_guard.skill_evolution.source_python import execute,validate,probe_program,finish
from test_skill_evolution_semantic_execution import PROGRAM,UNITS

class SourcePythonTests(unittest.TestCase):
    def test_nested_pure_recursion_and_setdefault_execute_without_rewriting(self):
        code='''def apply(inputs,premises):
    def depth(x):
        if isinstance(x,list):
            return 1+max([depth(y) for y in x]+[0])
        return 0
    value={}
    value.setdefault('d',[]).append(depth(inputs['x']))
    return value
'''
        self.assertEqual(execute(code,{'x':[['a']]}),{'d':[2]})

    def test_effectful_or_reflective_calls_remain_forbidden(self):
        for code in ['def apply(inputs,premises):\n    import os\n    return {}',
                     'def apply(inputs,premises):\n    return open("x").read()',
                     'def apply(inputs,premises):\n    return re.__dict__']:
            with self.assertRaises(ValueError):validate(code)

    def test_observation_probe_preserves_actual_complete_input_behavior(self):
        probe=probe_program(PROGRAM,'take')
        answers=[{'id':'gate','choice':'need'},{'id':'value','choice':'found'}]
        self.assertEqual(finish(probe,'',UNITS,answers),finish(PROGRAM,'',UNITS,answers))
