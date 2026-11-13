"""Algorithm checks, not extra legal training data or empirical method gains."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.observation_diagnosis import diagnose_observations


class ObservationDiagnosisTests(unittest.TestCase):
    def call(self,rows,status='not_run',language='b'*64):
        return diagnose_observations(rows,observation_contract_sha256='a'*64,
            theory_language_sha256=language,composition_status=status)

    def row(self,name,allowed,visible=None,status='complete'):
        return {'context_id':name,'visible_inputs':{'known':True} if visible is None else visible,
                'allowed_theories':allowed,'solver_status':status}

    def test_same_observation_incompatible_outputs_certifies_representation_failure(self):
        rows=[self.row('one',['support']),self.row('two',['defeat'])];before=deepcopy(rows)
        r=self.call(rows,'complete_unsat')
        self.assertEqual(r['decision'],'representation_insufficient')
        self.assertEqual(r['representation_certificates'][0]['deletion_minimal_core'],['one','two'])
        self.assertEqual(r['lower_bound_on_complete_nonlocal_classes'],1)
        self.assertEqual(rows,before)

    def test_partial_allowed_outputs_can_have_a_three_context_conflict(self):
        r=self.call([self.row('one',['a','b']),self.row('two',['b','c']),self.row('three',['a','c'])])
        self.assertEqual(r['decision'],'representation_insufficient')
        self.assertEqual(len(r['representation_certificates'][0]['deletion_minimal_core']),3)

    def test_local_infeasibility_does_not_license_predicate_invention(self):
        r=self.call([self.row('one',[]),self.row('two',['a'])])
        self.assertEqual(r['decision'],'local_theory_or_constraint_failure')
        self.assertEqual(r['representation_certificates'],[])

    def test_timeout_is_not_an_impossibility_certificate(self):
        r=self.call([self.row('one',['a']),self.row('two',[],status='timeout')],'complete_unsat')
        self.assertEqual(r['decision'],'unresolved')
        self.assertEqual(r['representation_certificates'],[])

    def test_native_query_and_unknown_state_are_not_discarded_to_create_collisions(self):
        r=self.call([self.row('one',['a'],{'query':'q1','fact':None}),
                     self.row('two',['b'],{'query':'q2','fact':False})],'complete_unsat')
        self.assertEqual(r['decision'],'composition_bias_insufficient')
        self.assertEqual(r['representation_certificates'],[])

    def test_retaining_old_inputs_and_adding_a_discriminating_concept_removes_bound(self):
        rows=[self.row('one',['a'],{'known':True,'new_concept':True}),
              self.row('two',['b'],{'known':True,'new_concept':False})]
        r=self.call(rows,'sat')
        self.assertEqual(r['decision'],'observed_constraints_satisfied')
        self.assertEqual(r['lower_bound_on_complete_nonlocal_classes'],0)

    def test_new_theory_language_invalidates_an_old_empty_intersection(self):
        before=self.call([self.row('one',['a']),self.row('two',['b'])])
        after=self.call([self.row('one',['a','shared']),self.row('two',['b','shared'])],
                        'sat',language='c'*64)
        self.assertEqual(before['decision'],'representation_insufficient')
        self.assertEqual(after['decision'],'observed_constraints_satisfied')

    def test_a_composition_sat_result_cannot_coexist_with_same_language_conflict(self):
        with self.assertRaises(ValueError):
            self.call([self.row('one',['a']),self.row('two',['b'])],'sat')

    def test_local_empty_theory_cannot_be_reported_as_a_satisfying_composition(self):
        with self.assertRaises(ValueError):
            self.call([self.row('one',[])],'sat')
