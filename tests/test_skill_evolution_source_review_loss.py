"""Explicit source counterevidence cannot become a zero-loss candidate."""
import unittest

from legal_skill_guard.skill_evolution.theory_supervision import native_loss


class SourceReviewLossTests(unittest.TestCase):
    def feedback(self, passed, correct):
        return {'reason': 'source_review' if not passed else 'native_score',
            'source_review_passed': passed,
            'views': [{'core_executed': True, 'score': {'correct': correct}}]}

    def test_native_correct_but_source_rejected_has_no_admissible_loss(self):
        self.assertIsNone(native_loss(self.feedback(False, True)))

    def test_source_pass_does_not_erase_native_error(self):
        self.assertEqual(native_loss(self.feedback(True, False)), 1)
        self.assertEqual(native_loss(self.feedback(True, True)), 0)

    def test_unreviewed_feedback_keeps_its_existing_native_scoring(self):
        value = self.feedback(True, False)
        del value['source_review_passed']
        self.assertEqual(native_loss(value), 1)


if __name__ == '__main__':
    unittest.main()
