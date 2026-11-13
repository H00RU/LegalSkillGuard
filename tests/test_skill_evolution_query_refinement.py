"""Finite acquisition and actual-read separation, on software fixtures only."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from legal_skill_guard.skill_evolution.open_acquisition import observe,execute,fit
from legal_skill_guard.skill_evolution.query_refinement import select_query
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,signatures,fact
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_execution,contract_checker


class QueryRefinementTests(unittest.TestCase):
    def setUp(self):
        ops=[{'name':name,'question':'Software '+name+'?', 'examples':[],
              'choices':[{'name':'asserted','meaning':'Asserted fixture'},
                         {'name':'absent','meaning':'Absent fixture'}]} for name in ('noise','signal')]
        q={'var':'Q'};r={'var':'R'}
        self.library={'operations':ops,'scope':'window',
            'planner_program':'def apply(inputs,premises):\n    return {"queries":[]}\n',
            'spec':{'constructors':[{'name':name,'sort':'Norm','arguments':[],'meaning':'Fixture only'}
                                    for name in ('old','new')]},
            'language':{'signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'},
                                      'emit':{'arguments':['query'],'kind':'output'}},
                'constants':{'operation':['signal'],'choice':['asserted']},
                'rules':[{'id':'keep','cost':1,'head':fact('keep_root',r),'body':[fact('legacy_root',r)]},
                         {'id':'emit','cost':1,'head':fact('emit',q),'body':[
                             fact('reader_query',q,'signal'),fact('query_choice',q,'asserted')]}]},
            'renderers':[{'predicate':'emit','term':['new'],'support_arguments':[],
                          'support_from_terms':[],'support_from_queries':[0]}],
            'selected_rule_ids':['keep','emit']}
        self.units=[{'id':4,'text':'Alpha.'}]
        self.query_ids={'noise':'actual_noise','signal':'actual_signal'}
        self.source={'statements':[{'term':['old'],'support_ids':[4]}],'complete':False,'unresolved':[]}
        self.observation=encode_source_observations('fixture',source_text='Alpha.',units=self.units,
            source_output=self.source,operations=ops,queries=[],answers=[],scope='window')

    def score(self,o):return len(execute(self.library,o)['source_output']['statements'])

    def select(self,o=None):
        return select_query(self.library,o or self.observation,self.score,
                            objective_name='unlabeled_core_coverage',query_ids=self.query_ids)

    def test_selects_useful_operation_without_modifying_actual_evidence(self):
        before=deepcopy(self.observation);library=deepcopy(self.library)
        result=self.select()
        self.assertEqual(result['query']['operation'],'signal')
        self.assertEqual(result['baseline_objective'],1)
        self.assertFalse(result['selection_uses_native_labels'])
        self.assertFalse(result['actual_source_semantics_certified'])
        self.assertEqual(self.observation,before);self.assertEqual(self.library,library)
        self.assertEqual(result['new_model_requests'],0)

    def test_requested_read_is_actually_executed_and_unknown_is_terminal(self):
        query=self.select()['query'];calls=[]
        class Client:
            config={'max_tokens':8192,'context_tokens':32768}
            def tokenize(self,*args,**kwargs):return {'count':0,'tokens':[]}
            def generate(self,*args,**kwargs):
                calls.append(kwargs)
                return {'finish_reason':'stop','content':json.dumps({'answers':{
                    query['id']:{'choice':'unknown','evidence_unit_ids':[]}}})}
        actual=observe(Client(),'fixture','fixture',self.library,source_text='Alpha.',
                       units=self.units,source_output=self.source,requested_queries=[query])
        self.assertEqual(len(calls),1);self.assertIs(calls[0]['thinking'],False)
        self.assertEqual(actual['execution']['diagnostic_requested_query_ids'],[query['id']])
        self.assertEqual(self.score(actual),1)
        self.assertEqual(self.select(actual)['status'],'no_useful_current_operation')

    def test_declared_reading_history_reused_without_repeating_model(self):
        query=self.select()['query']
        history=encode_source_observations('fixture',source_text='Alpha.',units=self.units,
            source_output=self.source,operations=self.library['operations'],queries=[{**query,'id':'paid'}],
            answers=[{'id':'paid','choice':'asserted','evidence':[{'unit_id':4,'quote':'Alpha.'}]}],scope='window')
        actual=observe(object(),'fixture','fixture',self.library,source_text='Alpha.',units=self.units,
            source_output=self.source,requested_queries=[query],previous_observation=history)
        self.assertEqual(actual['execution']['new_physical_requests'],0)
        self.assertEqual(self.score(actual),2)

    def test_counterfactuals_cannot_be_reused_or_fit_as_real_evidence(self):
        fake=deepcopy(self.observation);fake['counterfactual_only']=True
        with self.assertRaisesRegex(ValueError,'Counterfactual'):
            observe(object(),'fixture','fixture',self.library,source_text='Alpha.',units=self.units,
                    source_output=self.source,previous_observation=fake)
        with self.assertRaisesRegex(ValueError,'Counterfactual'):fit(self.library,[fake])

    def test_invalid_requested_operation_fails_before_call(self):
        query={**self.select()['query'],'operation':'invented'}
        with self.assertRaisesRegex(ValueError,'Unknown acquired operation'):
            observe(object(),'fixture','fixture',self.library,source_text='Alpha.',units=self.units,
                    source_output=self.source,requested_queries=[query])

    def test_nonuseful_or_nonfinite_objectives_cannot_select_a_request(self):
        result=select_query(self.library,self.observation,lambda o:0,
                            objective_name='lawful_TRAIN_native_correct',query_ids=self.query_ids)
        self.assertIsNone(result['query']);self.assertTrue(result['selection_uses_native_labels'])
        with self.assertRaisesRegex(ValueError,'finite'):
            select_query(self.library,self.observation,lambda o:float('nan'),
                         objective_name='unlabeled_core_coverage',query_ids=self.query_ids)

    def test_unlabeled_execution_has_no_access_to_native_grader(self):
        spec=deepcopy(self.library['spec'])
        spec['decision_program']='def apply(inputs,premises):\n    return {"handled":True,"answer":"Entailment","used_nodes":[0]}\n'
        source={'split':'train','dataset':'ContractNLI','views':[{'id':'fixture',
            'public':{'source_text':'Alpha.','question':'Software fixture?'}}]}
        output=deepcopy(self.source);output['statements'][0]['support_ids']=[0]
        with patch('legal_skill_guard.skill_evolution.native_theory_feedback.grade_view',
                   side_effect=AssertionError('Unlabeled selection read a native label')):
            result=contract_execution(spec,source)(output)
        self.assertEqual(result['reason'],'unscored_execution')
        self.assertFalse(result['accepted']);self.assertFalse(result['native_labels_used'])
        self.assertTrue(result['views'][0]['core_executed']);self.assertIsNone(result['views'][0]['score'])
        with self.assertRaisesRegex(ValueError,'supervision'):contract_checker(spec,source,None)
