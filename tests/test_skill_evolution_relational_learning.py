"""Solver/learner checks, not extra legal TRAIN examples or method scores."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.relational_learning import execute_composition,fit_composition
from legal_skill_guard.skill_evolution.relational_rules import validate_language


def atom(name,*args,negative=False):
    return {'predicate':name,'arguments':list(args),'sign':'negative' if negative else 'positive'}


def rule(name,head,*body,cost=1):
    return {'id':name,'head':head,'body':list(body),'cost':cost}


def context(name,facts,required=(),forbidden=(),unknown=()):
    return {'id':name,'facts':list(facts),'required':list(required),'forbidden':list(forbidden),
            'unknown_groups':list(unknown)}


class RelationalLearningTests(unittest.TestCase):
    def setUp(self):
        self.x={'var':'X'};self.y={'var':'Y'};self.z={'var':'Z'}
        self.lang={'signatures':{'edge':{'arguments':['node','node'],'kind':'observed'},
            'kind':{'arguments':['node','category'],'kind':'observed'},
            'marked':{'arguments':['node'],'kind':'observed'},
            'path':{'arguments':['node','node'],'kind':'derived'},
            'out':{'arguments':['node'],'kind':'output'}},
            'constants':{'category':['target','other']},'rules':[]}

    def test_global_fit_learns_a_relational_join_and_keeps_laws_isolated(self):
        x,y=self.x,self.y
        self.lang['rules']=[rule('join',atom('out',x),atom('edge',x,y),atom('kind',y,'target')),
            rule('too_broad',atom('out',x),atom('edge',x,y))]
        rows=[context('one',[atom('edge','a','b'),atom('kind','b','target')],[atom('out','a')]),
              context('two',[atom('edge','a','b'),atom('kind','b','other')],forbidden=[atom('out','a')])]
        original=deepcopy(rows);fit=fit_composition(self.lang,rows)
        self.assertEqual(fit['status'],'sat');self.assertEqual(fit['selected_rule_ids'],['join'])
        self.assertEqual(execute_composition(self.lang,['join'],rows[1])['certain_outputs'],[])
        self.assertEqual(rows,original)

    def test_explicit_negative_observation(self):
        x,y,z=self.x,self.y,self.z
        self.lang['rules']=[rule('base',atom('path',x,y),atom('edge',x,y)),
            rule('chain',atom('path',x,z),atom('path',x,y),atom('edge',y,z)),
            rule('read_negative',atom('out',x),atom('marked',x,negative=True))]
        c=context('one',[atom('edge','a','b'),atom('edge','b','c'),atom('marked','a',negative=True)],
                  required=[atom('out','a')])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['selected_rule_ids'],['read_negative'])
        self.assertEqual(execute_composition(self.lang,['read_negative'],c)['certain_outputs'][0]['arguments'],['a'])

    def test_recursive_composition_really_needs_the_intermediate_relation(self):
        x,y,z=self.x,self.y,self.z
        self.lang['rules']=[rule('base',atom('path',x,y),atom('edge',x,y)),
            rule('chain',atom('path',x,z),atom('path',x,y),atom('edge',y,z)),
            rule('emit',atom('out',x),atom('path',x,y),atom('kind',y,'target'))]
        c=context('one',[atom('edge','a','b'),atom('edge','b','c'),atom('kind','c','target')],
                  required=[atom('out','a')])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['selected_rule_ids'],['base','chain','emit'])
        got=execute_composition(self.lang,fit['selected_rule_ids'],c)['certain_outputs']
        self.assertIn(['a'],[r['arguments'] for r in got])
        without=execute_composition(self.lang,['base','emit'],c)['certain_outputs']
        self.assertNotIn(['a'],[r['arguments'] for r in without])

    def test_countermodel_loop_rejects_each_one_world_shortcut(self):
        x=self.x
        self.lang['rules']=[rule('positive',atom('out',x),atom('marked',x)),
            rule('negative',atom('out',x),atom('marked',x,negative=True))]
        c=context('one',[],required=[atom('out','a')],
                  unknown=[[[atom('marked','a')],[atom('marked','a',negative=True)]]])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['status'],'sat')
        self.assertEqual(fit['selected_rule_ids'],['negative','positive'])
        self.assertTrue(fit['countermodels'])
        self.assertTrue(fit['all_supplied_partial_constraints_hold_for_every_declared_possible_observation'])

    def test_unknown_is_not_default_false_and_requires_robust_training(self):
        x,y=self.x,self.y
        self.lang['rules']=[rule('unsafe_shortcut',atom('out',x),atom('marked',x),cost=1),
            rule('supported',atom('out',x),atom('edge',x,y),atom('kind',y,'target'),cost=2)]
        c=context('one',[atom('edge','a','b'),atom('kind','b','target')],required=[atom('out','a')],
            unknown=[[[atom('marked','a')],[atom('marked','a',negative=True)]]])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['status'],'sat')
        self.assertEqual(fit['selected_rule_ids'],['supported'])
        raw=execute_composition(self.lang,['unsafe_shortcut'],c)
        self.assertEqual(raw['certain_outputs'],[]);self.assertEqual(len(raw['possible_outputs']),1)
        self.assertEqual(raw['unknown_observations_preserved'],c['unknown_groups'])

    def test_impossible_bias_is_complete_unsat_instead_of_a_factual_negative(self):
        self.lang['rules']=[rule('only',atom('out',self.x),atom('marked',self.x))]
        c=context('one',[],required=[atom('out','a')])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['status'],'complete_unsat')
        self.assertIsNone(fit['selected_rule_ids'])

    def test_an_inconsistent_observation_is_not_diagnosed_as_bad_composition(self):
        c=context('one',[atom('marked','a'),atom('marked','a',negative=True)])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['status'],'inconsistent_observations')

    def test_no_cross_type_join_unbound_head_or_memorized_context_constant(self):
        x=self.x
        for r in [rule('typed',atom('out',x),atom('kind',x,x)),
                  rule('unsafe',atom('out',self.y),atom('marked',x)),
                  rule('case_id',atom('out','original_contract_id'),atom('marked',x))]:
            self.lang['rules']=[r]
            with self.assertRaises(ValueError):validate_language(self.lang)

    def test_derived_absence_is_never_an_explicit_negative_fact(self):
        self.lang['rules']=[rule('no',atom('out',self.x),atom('path',self.x,self.y,negative=True))]
        with self.assertRaises(ValueError):validate_language(self.lang)

    def test_unknown_context_cannot_be_replaced_by_derived_gold(self):
        c=context('one',[atom('out','a')])
        with self.assertRaises(ValueError):fit_composition(self.lang,[c])

    def test_strings_are_data_not_solver_instructions(self):
        self.lang['rules']=[rule('copy',atom('out',self.x),atom('marked',self.x))]
        text='a\"). bad. #script (python)'
        c=context('one',[atom('marked',text)],required=[atom('out',text)])
        fit=fit_composition(self.lang,[c]);self.assertEqual(fit['status'],'sat')
        self.assertEqual(execute_composition(self.lang,fit['selected_rule_ids'],c)['certain_outputs'][0]['arguments'],[text])
