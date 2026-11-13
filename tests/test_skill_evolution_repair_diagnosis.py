"""Software regressions for diagnosis on genuine executed-profile shapes."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.direct_composition_profiles import admissible_direct_compositions
from legal_skill_guard.skill_evolution.repair_diagnosis import diagnose_repairs
from tests.test_skill_evolution_direct_composition_profiles import fixture


def feedback(correct):
    return {'reason': 'native_constraints_satisfied' if correct else 'native_mismatch_or_uncovered',
        'accepted': correct, 'views': [{'view': 'target', 'core_executed': True,
            'execution': {'value': {'handled': True, 'answer': correct}}, 'score': {'correct': correct}}]}


class RepairDiagnosisTests(unittest.TestCase):
    def record(self, *, possible=True):
        library, observation, original_check = fixture(2)
        profile = admissible_direct_compositions(library, observation,
            lambda output: feedback(original_check(output)['accepted'] and possible))
        return library, {'observation': observation, 'profile': profile, 'feedback': feedback(False)}

    def test_existing_composition_witness_prevents_missing_concept_claim(self):
        library, record = self.record()
        result = diagnose_repairs(library, [record])
        self.assertEqual(result['source_specific_candidate_loss_lower_bound'], 0)
        self.assertEqual(result['next_operation'], 'shared_composition_refinement')
        self.assertEqual(result['sources'][0]['residuals'][0]['correcting_candidate_witnesses'], [['many']])
        self.assertEqual(result['representation_conflict_certificates'], [])

    def test_exhausted_current_candidates_route_to_open_refinement_without_semantic_claim(self):
        library, record = self.record(possible=False)
        result = diagnose_repairs(library, [record])
        self.assertEqual(result['source_specific_candidate_loss_lower_bound'], 1)
        self.assertEqual(result['next_operation'], 'open_reading_language_or_consumer_refinement')
        self.assertFalse(result['sources'][0]['residuals'][0]['missing_source_concept_certified'])

    def test_timeout_stale_or_incomplete_profile_cannot_route_a_repair(self):
        library, record = self.record()
        for mutation in ('timeout', 'stale', 'incomplete'):
            changed = deepcopy(record)
            if mutation == 'timeout': changed['profile']['status'] = 'timeout'
            elif mutation == 'stale': changed['observation']['context']['facts'].pop()
            else: changed['profile']['evaluations'].pop()
            with self.assertRaises(ValueError): diagnose_repairs(library, [changed])

    def test_execution_fault_and_duplicate_source_do_not_become_legal_negatives(self):
        library, record = self.record()
        with self.assertRaisesRegex(ValueError, 'twice'): diagnose_repairs(library, [record, record])
        record['feedback']['reason'] = 'execution_error'
        with self.assertRaisesRegex(ValueError, 'execution fault'): diagnose_repairs(library, [record])
