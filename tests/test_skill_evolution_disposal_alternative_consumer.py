"""Source-faithful OR semantics from an actual TRAIN consumer failure."""
from copy import deepcopy
import ast
import unittest

from experiments import legal_skill_evolution_source_disposal_consumer as study
from legal_skill_guard.skill_evolution.span_compiler import execute_json


class DisposalAlternativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = study.train.read(study.train.OUT / 'B3/ConstraintAcquire/library.json')
        code = study.repair(library['spec']['decision_program'])
        definitions = [ast.get_source_segment(code, n) for n in ast.parse(code).body if n.name != 'apply']
        cls.probe = '\n\n'.join(definitions) + '\n\ndef apply(inputs,premises):\n    return {"full":d_full_disposal(inputs["action"])}\n'
        sid = next(s for s in study.train.prepare()['sources'] if 'd50f9b' in s)
        row = study.train.read(study.train.OUT / 'B4/ConstraintAcquire/initial' / study.train.previous.old.name_for(sid))
        cls.action = next(r['term'][2] for r in row['actual']['execution']['source_output']['statements']
            if r['term'][0] == 'disposal_obligation' and r['term'][2][0] == 'action_alternative')

    def result(self, action):
        return execute_json(self.probe, {'action': action}, {}, allow_helpers=True)['full']

    def test_real_all_copies_return_or_destroy_has_common_disposal_effect(self):
        self.assertTrue(self.result(self.action))

    def test_one_partial_branch_does_not_prove_all_copies_disposed(self):
        action = deepcopy(self.action)
        action[2][1] = ['confidential_information']
        self.assertFalse(self.result(action))

    def test_metadata_does_not_become_an_action_or_material_assertion(self):
        action = ['acquired_action_alternative_v3',
            ['return_to', ['confidential_information'], ['disclosing_party']],
            ['destroy', ['confidential_information']], 'return or destroy ALL COPIES']
        self.assertFalse(self.result(action))


if __name__ == '__main__':
    unittest.main()
