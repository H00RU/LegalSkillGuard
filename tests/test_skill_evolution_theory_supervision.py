"""Finite native-admission/learning tests; fixtures are not legal TRAIN data."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.open_acquisition import execute,fit
from legal_skill_guard.skill_evolution.relational_learning import fit_composition
from legal_skill_guard.skill_evolution.relational_rules import context_identity,language_identity
from legal_skill_guard.skill_evolution.source_observations import fact
from legal_skill_guard.skill_evolution.theory_supervision import admissible_theories,attach_theories,attach_scored_theories,diagnose_inputs
from tests import test_skill_evolution_open_acquisition as fixture_module


class TheorySupervisionTests(unittest.TestCase):
    def setUp(self):
        fixture=fixture_module.OpenAcquisitionTests();fixture.setUp();self.fixture=fixture

    def test_native_admission_leaves_multiple_theories_and_drives_shared_fit(self):
        a=self.fixture.observation('one','Alpha.','first');b=self.fixture.observation('two','Beta.','second')
        yes=lambda out:{'accepted':bool(out['statements']),'reason':'software_native_stub'}
        no=lambda out:{'accepted':not out['statements'],'reason':'software_native_stub'}
        aa=admissible_theories(self.fixture.library,a,yes);bb=admissible_theories(self.fixture.library,b,no)
        self.assertEqual((aa['status'],bb['status']),('complete','complete'))
        self.assertEqual(aa['finite_theory_count'],2);self.assertEqual(len(aa['allowed_theories']),1)
        learned,result=fit(self.fixture.library,[attach_theories(a,aa),attach_theories(b,bb)])
        self.assertEqual(result['status'],'sat');self.assertEqual(learned['selected_rule_ids'],['join'])
        self.assertEqual(len(execute(learned,a)['source_output']['statements']),1)
        self.assertEqual(diagnose_inputs([a,b],[aa,bb],'sat')['decision'],'observed_constraints_satisfied')

    def test_local_empty_language_is_not_a_representation_certificate(self):
        a=self.fixture.observation('one','Alpha.','second')
        impossible=lambda out:{'accepted':False,'reason':'software_no_admissible_output'}
        aa=admissible_theories(self.fixture.library,a,impossible)
        diagnosis=diagnose_inputs([a],[aa],'complete_unsat')
        self.assertEqual(diagnosis['decision'],'local_theory_or_constraint_failure')
        self.assertEqual(diagnosis['representation_certificates'],[])

    def test_residual_native_errors_do_not_block_a_hard_source_consistent_library(self):
        a=self.fixture.observation('one','Alpha.','first');b=self.fixture.observation('two','Beta.','first')
        a['context']['required']=[fact('emit','t1',4)]
        yes=lambda out:{'accepted':bool(out['statements']),'reason':'software_native_stub'}
        no=lambda out:{'accepted':not out['statements'],'reason':'software_native_stub'}
        aa=admissible_theories(self.fixture.library,a,yes);bb=admissible_theories(self.fixture.library,b,no)
        exact,_=fit(self.fixture.library,[attach_theories(a,aa),attach_theories(b,bb)])
        self.assertIsNone(exact['selected_rule_ids'])
        learned,result=fit(self.fixture.library,[attach_scored_theories(a,aa),attach_scored_theories(b,bb)])
        self.assertEqual(result['status'],'sat');self.assertEqual(result['native_loss'],1)
        self.assertFalse(result['all_supplied_native_constraints_satisfied'])
        self.assertTrue(result['all_supplied_partial_constraints_hold_for_every_declared_possible_observation'])
        self.assertTrue(execute(learned,a)['source_output']['statements'])

    def test_native_loss_does_not_relax_a_source_contradiction(self):
        a=self.fixture.observation('one','Alpha.','first')
        a['context']['required']=[fact('emit','t1',4)];a['context']['forbidden']=[fact('emit','t1',4)]
        aa=admissible_theories(self.fixture.library,a,lambda out:{'accepted':True,'reason':'software_stub'})
        _,result=fit(self.fixture.library,[attach_scored_theories(a,aa)])
        self.assertEqual(result['status'],'complete_unsat')

    def test_timeout_cannot_supply_incomplete_allowed_set(self):
        a=self.fixture.observation('one','Alpha.','first')
        aa=admissible_theories(self.fixture.library,a,lambda out:None,timeout_seconds=0.000001)
        self.assertEqual(aa['status'],'timeout')
        with self.assertRaises(ValueError):attach_theories(a,aa)

    def test_new_observations_or_language_invalidates_old_theories(self):
        a=self.fixture.observation('one','Alpha.','first')
        aa=admissible_theories(self.fixture.library,a,lambda out:{'accepted':True,'reason':'software_stub'})
        updated=deepcopy(a);updated['context']['required']=[fact('emit','t1',4)]
        with self.assertRaises(ValueError):attach_theories(updated,aa)
        old=attach_theories(a,aa);language=deepcopy(self.fixture.lang);language['rules'][0]['cost']=3
        with self.assertRaises(ValueError):fit_composition(language,[old['context']])

    def test_prediction_intersection_itself_must_be_native_admissible(self):
        x={'var':'X'}
        def rule(name,pred,body,cost):return {'id':name,'head':fact(pred,x),'body':[body],'cost':cost}
        language={'signatures':{'marked':{'arguments':['node'],'kind':'observed'},
            'node':{'arguments':['node'],'kind':'observed'},
            **{p:{'arguments':['node'],'kind':'output'} for p in ('out_a','out_b','out_c')}},
            'constants':{},'rules':[
                rule('a','out_a',fact('marked',x),1),
                rule('b','out_b',{'predicate':'marked','arguments':[x],'sign':'negative'},1),
                rule('c','out_c',fact('node',x),4)]}
        context={'id':'software','facts':[fact('node','v')],'required':[],'forbidden':[],
            'unknown_groups':[[[fact('marked','v')],[{'predicate':'marked','arguments':['v'],'sign':'negative'}]]]}
        vocabulary=[fact(p,'v') for p in ('out_a','out_b','out_c')]
        context['theory_constraints']={'status':'complete','language_sha256':language_identity(language),
            'context_sha256':context_identity(context),'vocabulary':vocabulary,
            'allowed_theories':[[a for i,a in enumerate(vocabulary) if n&(1<<i)] for n in range(1,8)]}
        result=fit_composition(language,[context])
        self.assertEqual(result['status'],'sat');self.assertEqual(result['selected_rule_ids'],['c'])
        self.assertTrue(any(r.get('reason')=='deployed_cautious_theory_not_admissible' for r in result['countermodels']))

        # Weighted native loss still judges the actual cautious deployment;
        # fitting only a guessed possible world cannot obtain zero loss.
        context['theory_constraints'].update({'optimization':'native_loss','scored_theories':[
            {'theory':[a for i,a in enumerate(vocabulary) if n&(1<<i)],'native_loss':0 if n else 1}
            for n in range(8)]})
        weighted=fit_composition(language,[context])
        self.assertEqual(weighted['selected_rule_ids'],['c']);self.assertEqual(weighted['native_loss'],0)
        self.assertTrue(any(r.get('reason')=='deployed_cautious_native_loss_exceeds_bound' for r in weighted['countermodels']))
