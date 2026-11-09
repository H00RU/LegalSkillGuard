"""Safety and generalization checks using the recorded, real TRAIN trajectories."""
import math
import unittest
from legal_skill_guard.rr.semantic_learning import (H, Y, context, compile_skill, run_skill, fit_channels,
    forecasts, transform, decode_joint)

ROWS = [
    {'case_id':'71original','mother':'71','weight':.5,'h':[1,1],'y':[1,1,1,1],'context':[1,0]},
    {'case_id':'71controlled','mother':'71','weight':.5,'h':[0,1],'y':[1,1,0,1],'context':[1,0]},
    {'case_id':'79original','mother':'79','weight':.5,'h':[0,2],'y':[0,0,2,2],'context':[0,0]},
    {'case_id':'79controlled','mother':'79','weight':.5,'h':[0,1],'y':[0,1,0,0],'context':[1,0]},
]


class LearningRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.models = fit_channels(ROWS)

    def test_real_training_confusions_retained(self):
        skill = compile_skill(ROWS)
        self.assertFalse(skill['empty'])
        self.assertEqual(len(skill['training_errors']), 3)
        self.assertEqual(skill['objective'][0], 0)
        for r in ROWS: self.assertEqual(run_skill(skill, r['y'])['prediction'], r['h'])

    def test_no_confusion_cannot_create_skill(self):
        self.assertTrue(compile_skill([ROWS[0]])['empty'])

    def test_learned_program_is_entity_and_amount_free(self):
        skill = str(compile_skill(ROWS)['tree'])
        self.assertNotIn('71', skill); self.assertNotIn('Alice', skill)

    def test_distributions_are_normalized_and_full_support(self):
        for h in H:
            for p in forecasts(self.models, h, [1,0]).values():
                self.assertAlmostEqual(sum(p), 1., places=10)
                self.assertTrue(all(v > 0 for v in p))

    def test_copy_and_unknown_do_not_invent_a_truth(self):
        self.assertEqual(transform([0,1], ('other','self','self','self')), [1,1,0,1])
        self.assertEqual(transform([0,2], ('self','unknown_as_false','erase','self')), [0,0,2,2])

    def test_no_model_prediction_becomes_a_semantic_anchor(self):
        fs = [forecasts(self.models, h, [1,0]) for h in H]
        for v in decode_joint(fs, [1,1,1,1]).values():
            self.assertIsNone(v['semantic_answer']); self.assertTrue(v['unresolved'])
            self.assertEqual(len(v['compatible_h_with_residual']), 9)

    def test_context_uses_text_not_variant_identity(self):
        self.assertEqual(context('Alice paid $20 in hay to Bob.'), context('X paid $900 in hay to Y.'))
        self.assertEqual(context('Alice paid $20 to Bob.'), [0,0])


if __name__ == '__main__': unittest.main()
