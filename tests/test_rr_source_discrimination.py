"""Regression of the finite source-bound learner, not semantic efficacy proof."""
import unittest
from legal_skill_guard.rr.source_discrimination import (learn_selector,execute_selector,
    compile_discrimination,constrain_bindings,plan_questions)
from reports.method_redesign_20261109.evaluate_source_bound_program import training_examples


class SourceDiscriminationRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.examples=training_examples();cls.program=learn_selector(cls.examples)
        cls.skill=compile_discrimination(cls.examples)

    def test_induction_uses_source_relations(self):
        for e in self.examples:
            result=execute_selector(self.program,e['facts'],{'payer':e['frame']['payer'],'payee':e['frame']['payee']})
            self.assertTrue(any(all(c['values'][r]==e['frame'][r] for r in ('payer','payee','work_activity','payment_medium')) for c in result['candidates']))

    def test_unknown_material_does_not_become_false(self):
        e=self.examples[0];text=e['facts'].replace('hay','an unidentified substance')
        result=execute_selector(self.program,text,{'payer':'Alice','payee':'Bob'})
        self.assertEqual(result['prediction'],[1,2])
        self.assertFalse(result['source_meaning_proved'])

    def test_an_entity_mentioned_elsewhere_is_not_forced_into_the_event(self):
        result=execute_selector(self.program,'Alice left. Bob was paid for domestic service.',{'payer':'Alice','payee':'Bob'})
        self.assertEqual(result['candidates'],[]);self.assertTrue(result['unresolved'])

    def test_multiple_supported_activities_stay_multiple(self):
        text='Alice paid to Bob for domestic service and for agricultural labor.'
        result=execute_selector(self.program,text,{'payer':'Alice','payee':'Bob'})
        self.assertEqual(len(result['candidates']),2);self.assertEqual(result['prediction'],[2,2])

    def test_teacher_questions_compile_without_entity_memorization(self):
        self.assertEqual({a['role'] for a in self.skill['question_actions']},{'work_activity','payment_medium'})
        for a in self.skill['question_actions']:
            self.assertNotIn('Alice',a['question_template']);self.assertNotIn('3200',a['question_template'])

    def test_unknown_answer_never_prunes_and_unissued_question_has_no_cache(self):
        text='Alice paid to Bob for domestic service and for agricultural labor.'
        candidates=execute_selector(self.program,text,{'payer':'Alice','payee':'Bob'})['candidates']
        plan=plan_questions(self.skill,candidates,{'payer':'Alice','payee':'Bob'})
        self.assertTrue(plan['actions']);self.assertTrue(plan['all_unissued_questions_unobserved'])
        self.assertEqual(constrain_bindings(candidates,'work_activity',{'span':None},text)['retained'],candidates)
        result=constrain_bindings(candidates,'work_activity',{'span':'domestic service'},text)
        self.assertEqual(len(result['retained']),1);self.assertFalse(result['semantic_certificate'])
        with self.assertRaises(ValueError):constrain_bindings(candidates,'work_activity',{'span':'a new activity'},text)

    def test_entity_and_amount_change_preserves_structure(self):
        e=self.examples[0];text=e['facts'].replace('Alice','Debtor').replace('Bob','Worker').replace('2325','8999')
        result=execute_selector(self.program,text,{'payer':'Debtor','payee':'Worker'})
        self.assertEqual(result['prediction'],[1,1])


if __name__=='__main__':unittest.main()
