"""Actual before/after guard attachment, including swapped and mixed-scope failures."""
from copy import deepcopy
import unittest

from experiments import legal_skill_evolution_source_checkpoints as checkpoints


class BranchScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        train = checkpoints.train
        cls.issue = train.read(train.OUT/'B5/checkpoint.json')['pending_source_semantics'][0]
        name = train.previous.old.name_for(cls.issue['source'])
        cls.old = train.read(train.OUT/'B6/ConstraintAcquire/candidate_results'/name)
        cls.new = train.read(train.OUT/'B6/source_parser_correction/ConstraintAcquire/fitted_results'/name)

    def remaining(self, row):
        return checkpoints.remaining([self.issue], {'ConstraintAcquire':[row]})

    def norm(self, row):
        return next(s for s in row['actual']['execution']['source_output']['statements']
            if s['term'][0]=='disposal_obligation' and 32 in s['support_ids'])

    def test_old_missing_scope_stays_pending_real_repaired_joint_scope_clears(self):
        self.assertTrue(self.remaining(self.old))
        self.assertFalse(self.remaining(self.new))

    def test_return_authorization_cannot_replace_destruction_authorization(self):
        row = deepcopy(self.new)
        scope = self.norm(row)['term'][4]
        scope[1:4], scope[4:7] = scope[4:7], scope[1:4]
        self.assertTrue(self.remaining(row))

    def test_correct_guard_cannot_hide_additional_plain_alternative(self):
        row = deepcopy(self.new)
        plain = deepcopy(self.norm(row))
        plain['term'][4] = ['acquired_joint_exception_scope_v3','no_acquired_exception','','','no_acquired_exception','','']
        row['actual']['execution']['source_output']['statements'].append(plain)
        self.assertTrue(self.remaining(row))

    def test_same_review_is_a_shared_hard_check_not_a_native_answer_rule(self):
        from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review
        from legal_skill_guard.skill_evolution.theory_supervision import native_loss
        train = checkpoints.train
        library = train.read(train.OUT/'B6/source_parser_correction/ConstraintAcquire/library.json')
        check = with_disposal_review(lambda output: {'accepted':True,'reason':'software_fixture'},
            self.issue['source'], [], library['spec']['decision_program'], authorization_review=self.issue)
        self.assertIsNone(native_loss(check(self.old['actual']['execution']['source_output'])))
        self.assertEqual(native_loss(check(self.new['actual']['execution']['source_output'])),0)


if __name__ == '__main__':
    unittest.main()
