"""Real fixed-TRAIN bound proof and source-faithful OR counterexamples."""
from copy import deepcopy
import unittest

from experiments import legal_skill_evolution_source_library_train as study
from legal_skill_guard.skill_evolution.source_selection_certificate import certify_unchanged_selection
from legal_skill_guard.skill_evolution.source_disposal_review import with_disposal_review, validate_reviewed_disposal


class SourceSelectionCertificateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = study.read(study.OUT / 'B5/teacher_task.json')
        cls.library = cls.task['current_libraries']['ConstraintAcquire']
        cls.public = {s['key']: s for s in study.read(study.parent.PREPARED / 'public.json')}
        cls.grading = study.read(study.parent.PREPARED / 'grading.json')
        cls.reviews = study.read(study.OUT / 'B5/shared_source_disposal_reviews.json')
        cls.rows = [study.read(study.OUT / 'B5/ConstraintAcquire/pre_update_seen' /
            study.previous.old.name_for(t['source_id'])) for t in cls.task['tasks']]

    def checker(self, sid):
        native = study.previous.old.previous.prior.prior.checker(self.library, self.public[sid], self.grading[sid])
        return with_disposal_review(native, sid, self.reviews, self.library['spec']['decision_program'])

    def profile(self, sid, observation):
        return study.read(study.OUT / 'B5/pre_update_source_checked_profiles' / study.previous.old.name_for(sid))

    def test_actual_incumbent_attains_joint_nonzero_loss_bound_without_enumerating_correct_contexts(self):
        visited = []
        def profile(sid, observation):
            visited.append(sid)
            return self.profile(sid, observation)
        result = certify_unchanged_selection(self.library, self.library['selected_rule_ids'], self.rows, self.checker, profile)
        self.assertTrue(result['certified'])
        self.assertEqual((result['native_loss'], result['native_loss_lower_bound']), (3, 3))
        self.assertEqual(len(visited), 3)
        self.assertEqual(result['selection_edits'], 0)

    def test_partial_search_and_mismatched_profiles_never_certify(self):
        def partial(sid, observation):
            return {**self.profile(sid, observation), 'status': 'timeout'}
        self.assertFalse(certify_unchanged_selection(self.library, self.library['selected_rule_ids'],
            self.rows, self.checker, partial)['certified'])
        def mismatched(sid, observation):
            return {**self.profile(sid, observation), 'context_sha256': '0' * 64}
        with self.assertRaises(ValueError):
            certify_unchanged_selection(self.library, self.library['selected_rule_ids'], self.rows, self.checker, mismatched)

    def test_real_review_rejects_omitting_or_strengthening_the_disposal_alternative(self):
        sid = next(r['source'] for r in self.rows if 'de427b' in r['source'])
        row = next(r for r in self.rows if r['source'] == sid)
        output = row['actual']['execution']['source_output']
        reviews = [r for r in self.reviews if r['source'] == sid]
        self.assertFalse(validate_reviewed_disposal(output, reviews, self.library['spec']['decision_program']))
        omitted = deepcopy(output)
        omitted['statements'] = [r for r in omitted['statements'] if r['term'][0] != 'disposal_obligation']
        self.assertTrue(validate_reviewed_disposal(omitted, reviews, self.library['spec']['decision_program']))
        strengthened = deepcopy(output)
        alternative = next(r for r in strengthened['statements'] if r['term'][0] == 'disposal_obligation'
            and r['term'][2][0] in ('action_alternative', 'acquired_action_alternative_v3'))
        atomic = deepcopy(alternative)
        atomic['term'][2] = deepcopy(atomic['term'][2][1])
        strengthened['statements'].append(atomic)
        self.assertTrue(any('strengthened' in r['violation'] for r in validate_reviewed_disposal(strengthened, reviews, self.library['spec']['decision_program'])))


if __name__ == '__main__':
    unittest.main()
