import unittest
from legal_skill_guard.skill_evolution.refutation_learning import fit,canonical_evidence
import json


class RefutationLearningTests(unittest.TestCase):
    def test_protect_positive_and_cover_negative_from_measured_checks(self):
        tests=[{'name':n,'question_template':n} for n in ['bad','a','b']]
        cases=[{'id':'p','status':'supported'},{'id':'n','status':'rejected'}]
        values={'bad':['refuted','refuted'],'a':['supported','refuted'],'b':['unknown','unknown']}
        rows=[{'case':c['id'],'test':n,'verdict':values[n][i],
               'exclude_candidate':values[n][i]=='refuted'} for n in values for i,c in enumerate(cases)]
        result=fit(tests,cases,rows)
        self.assertEqual(result['selected_tests'],['a'])
        self.assertEqual(result['objective'][:2],[0,0])

    def test_unknown_does_not_exclude_and_incomplete_measurements_fail(self):
        t=[{'name':'t','question_template':'q'}];c=[{'id':'n','status':'rejected'}]
        rows=[{'case':'n','test':'t','verdict':'unknown','exclude_candidate':False}]
        result=fit(t,c,rows)
        self.assertEqual(result['selected_tests'],[])
        self.assertEqual(result['objective'][:2],[0,1])
        with self.assertRaises(ValueError):fit(t,c,[])

    def test_identity_adaptation_preserves_semantics_and_rejects_conflicting_keys(self):
        raw='{"answers":{"q":{"choice":"supported","support_ids":[3,3,8,3]}}}'
        result,receipt=canonical_evidence(raw)
        self.assertEqual(json.loads(result)['answers']['q'],{'choice':'supported','support_ids':[3,8]})
        self.assertTrue(receipt[0]['same_witness_identity_set'])
        with self.assertRaises(ValueError):canonical_evidence('{"answers":{},"answers":{}}')


if __name__=='__main__':unittest.main()
