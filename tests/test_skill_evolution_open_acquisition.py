"""Learning-path regressions on software fixtures, not extra legal TRAIN."""
from copy import deepcopy
import json
import unittest

from legal_skill_guard.skill_evolution.open_acquisition import compile_update,execute,fit,observe
from legal_skill_guard.skill_evolution.source_composition import validate_renderers
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,fact,signatures


PLANNER='''def apply(inputs,premises):
    return {'queries':[{'id':'q','operation':'meaning','unit_ids':[inputs['source_spans'][0]['id']]}]}
'''


class FixtureClient:
    """No-model fixtures exercise transport, not real token accounting."""
    config = {'max_tokens': 8192, 'context_tokens': 32768}
    def tokenize(self, messages, *, thinking):
        assert thinking is False
        return {'count': 0, 'tokens': []}


class OpenAcquisitionTests(unittest.TestCase):
    def setUp(self):
        op={'name':'meaning','question':'Which asserted meaning?',
            'choices':[{'name':'first','meaning':'First meaning'},{'name':'second','meaning':'Second meaning'}],
            'examples':[]}
        self.spec={'constructors':[
            {'name':name,'sort':sort,'arguments':args,'meaning':name+' software fixture'}
            for name,sort,args in [('old_ctor','Norm',['Actor']),('new_norm','Norm',['Actor']),('actor','Actor',['text'])]]}
        self.old={'operations':[op],'planner_program':PLANNER,'spec':self.spec}
        r,t,u,q=({'var':n} for n in ('R','T','U','Q'))
        self.lang={'signatures':{**signatures(),'emit':{'arguments':['term','unit'],'kind':'output'}},
            'constants':{'position':[0],'operation':['meaning'],'choice':['first']},
            'rules':[{'id':'join','head':fact('emit',t,u),'cost':2,'body':[
                fact('legacy_root',r),fact('term_child',r,0,t),fact('root_support',r,u),
                fact('reader_query',q,'meaning'),fact('query_focus',q,u),fact('query_choice',q,'first')]},
                {'id':'broad','head':fact('emit',t,u),'cost':1,'body':[
                fact('legacy_root',r),fact('term_child',r,0,t),fact('root_support',r,u)]}]}
        self.renderer={'predicate':'emit','term':['new_norm',{'term_argument':0}],
            'support_arguments':[1],'support_from_terms':[0]}
        self.proposal={'operations':[op],'planner_functions':[],'language':self.lang,
            'renderers':[self.renderer],'scope':'focus_last','rationale':'Software path check only'}
        self.library=compile_update(self.old,self.proposal,{'fixture':'Alpha. Beta.'})

    def observation(self,name,text,choice):
        return encode_source_observations(name,source_text=text,units=[{'id':4,'text':text}],
            source_output={'statements':[{'term':['old_ctor',['actor','Alice']],'support_ids':[4]}],
                'complete':False,'unresolved':[]},operations=self.library['operations'],
            queries=[{'id':'q','operation':'meaning','unit_ids':[4]}],
            answers=[{'id':'q','choice':choice,'evidence':[] if choice=='unknown' else [{'unit_id':4,'quote':text}]}],
            scope='focus_last')

    def test_actual_observation_to_global_fit_to_typed_rendering(self):
        a=self.observation('one','Alpha.','first');b=self.observation('two','Beta.','second')
        a['context']['required']=[fact('emit','t1',4)];b['context']['forbidden']=[fact('emit','t1',4)]
        original=deepcopy(self.library);learned,result=fit(self.library,[a,b])
        self.assertEqual(result['status'],'sat');self.assertEqual(learned['selected_rule_ids'],['join'])
        self.assertEqual(self.library,original)
        value=execute(learned,a)['source_output']
        self.assertEqual(value['statements'],[{'term':['new_norm',['actor','Alice']],'support_ids':[4]}])
        self.assertEqual(execute(learned,b)['source_output']['statements'],[])
        self.assertFalse(value['source_semantics_verified'])

    def test_unknown_reused_without_a_model_retry(self):
        previous=self.observation('one','Alpha.','unknown')
        class NoCall:
            def generate(self,*args,**kwargs):raise AssertionError('Unchanged unknown was retried')
        got=observe(NoCall(),'fixture','one',self.library,
            source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
            source_output=previous['visible_inputs']['source_output'],previous_observation=previous)
        self.assertEqual(got['execution']['new_physical_requests'],0)
        self.assertEqual(got['execution']['reused_query_ids'],['q'])
        self.assertEqual(got['visible_inputs']['answers'][0]['choice'],'unknown')

    def test_actual_histories_from_both_arms_reuse_the_exact_matching_reading(self):
        first=self.observation('one','Alpha.','first')
        first['visible_inputs']['operations'][0]['question']='A genuinely different old meaning'
        second=self.observation('one','Alpha.','unknown')
        class NoCall:
            def generate(self,*args,**kwargs):raise AssertionError('A paid exact reading was repeated')
        got=observe(NoCall(),'fixture','one',self.library,source_text='Alpha.',
            units=[{'id':4,'text':'Alpha.'}],source_output=second['visible_inputs']['source_output'],
            previous_observations=[first,second])
        self.assertEqual(got['visible_inputs']['answers'][0]['choice'],'unknown')
        self.assertEqual(len(got['execution']['reuse_history_inputs_sha256']),2)
        self.assertEqual(got['execution']['new_physical_requests'],0)

    def test_conflicting_paid_readings_are_not_selected_using_training_answers(self):
        first=self.observation('one','Alpha.','first');second=self.observation('one','Alpha.','second')
        class NoCall:
            def generate(self,*args,**kwargs):raise AssertionError('Conflicting old readings triggered a retry')
        with self.assertRaisesRegex(ValueError,'Conflicting actual prior'):
            observe(NoCall(),'fixture','one',self.library,source_text='Alpha.',
                units=[{'id':4,'text':'Alpha.'}],source_output=first['visible_inputs']['source_output'],
                previous_observations=[first,second])

    def test_changed_concept_requires_a_new_real_read_and_thinking_is_off(self):
        previous=self.observation('one','Alpha.','unknown');library=deepcopy(self.library)
        library['operations'][0]['question']='A changed meaning?'
        calls=[]
        class RecordedClient(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append((args,kwargs))
                return {'finish_reason':'stop','content':json.dumps({'answers':{'q':{'choice':'first',
                    'evidence_unit_ids':[4]}}})}
        got=observe(RecordedClient(),'fixture','one',library,
            source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
            source_output=previous['visible_inputs']['source_output'],previous_observation=previous)
        self.assertEqual(len(calls),1);self.assertIs(calls[0][1]['thinking'],False)
        self.assertEqual(got['execution']['new_physical_requests'],1)
        self.assertEqual(got['visible_inputs']['answers'][0]['choice'],'first')

    def test_invalid_response_saved_before_failure_no_hidden_retry(self):
        saved=[];calls=[]
        class Incomplete(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append(args);return {'finish_reason':'length','content':'{"truncated":'}
        previous=self.observation('one','Alpha.','first')
        with self.assertRaises(ValueError):
            observe(Incomplete(),'fixture','one',self.library,source_text='Alpha.',
                units=[{'id':4,'text':'Alpha.'}],source_output=previous['visible_inputs']['source_output'],
                save_event=saved.append)
        self.assertEqual(len(saved),1);self.assertEqual(len(calls),1)

    def test_new_facts_cannot_be_supplied_without_an_executable_reader(self):
        proposal=deepcopy(self.proposal)
        proposal['language']['signatures']['imagined_legal_rule']={'arguments':['term'],'kind':'observed'}
        with self.assertRaises(ValueError):compile_update(self.old,proposal,{'fixture':'Alpha.'})

    def test_source_constant_cannot_be_hidden_in_output_renderer(self):
        renderer=deepcopy(self.renderer);renderer['term']=['new_norm',['actor','Old Contract Party']]
        with self.assertRaises(ValueError):validate_renderers(self.lang,[renderer])

    def test_incomplete_hypothesis_never_becomes_a_default_output(self):
        with self.assertRaises(ValueError):execute(self.library,self.observation('one','Alpha.','first'))

    def test_semantic_scout_can_plan_a_second_read_from_actual_answers(self):
        library=deepcopy(self.library)
        library['planner_program']='''def apply(inputs,premises):
    answers=inputs.get('semantic_answers',[])
    if not answers:
        return {'queries':[{'id':'scout','operation':'meaning','unit_ids':[4]}]}
    if answers[0]['choice']=='first':
        return {'queries':[{'id':'detail','operation':'meaning','unit_ids':[9]}]}
    return {'queries':[]}
'''
        calls=[]
        class RecordedClient(FixtureClient):
            def generate(self,*args,**kwargs):
                current=json.loads(kwargs['messages'][1]['content'])['current_queries'];calls.append(current)
                return {'finish_reason':'stop','content':json.dumps({'answers':{q['id']:{'choice':'first',
                    'evidence_unit_ids':[q['unit_ids'][-1]]} for q in current}})}
        original=self.observation('one','Alpha.','first')['visible_inputs']['source_output']
        got=observe(RecordedClient(),'fixture','one',library,source_text='Alpha. Beta.',
            units=[{'id':4,'text':'Alpha.'},{'id':9,'text':'Beta.'}],source_output=original)
        self.assertEqual(len(calls),2);self.assertEqual(got['execution']['planning_rounds'],[['scout'],['detail']])
        self.assertEqual([q['id'] for q in got['visible_inputs']['queries']],['scout','detail'])

    def test_renaming_an_identical_unknown_query_does_not_spend_a_request(self):
        old=self.observation('one','Alpha.','unknown');library=deepcopy(self.library)
        library['planner_program']=PLANNER.replace("'q'","'renamed'")
        class NoCall:
            def generate(self,*args,**kwargs):raise AssertionError('An unchanged semantic question was repeated')
        got=observe(NoCall(),'fixture','one',library,source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
            source_output=old['visible_inputs']['source_output'],previous_observation=old)
        self.assertEqual(got['visible_inputs']['answers'][0]['id'],'renamed')
        self.assertEqual(got['visible_inputs']['answers'][0]['choice'],'unknown')
        self.assertEqual(got['execution']['new_physical_requests'],0)

    def test_query_id_churn_cannot_make_unknown_retries(self):
        library=deepcopy(self.library);library['planner_program']='''def apply(inputs,premises):
    return {'queries':[{'id':'q'+str(len(inputs.get('semantic_answers',[]))),'operation':'meaning','unit_ids':[4]}]}
'''
        calls=[]
        class Unknown(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append(args);return {'finish_reason':'stop','content':json.dumps({'answers':{'q0':{'choice':'unknown','evidence_unit_ids':[]}}})}
        old=self.observation('one','Alpha.','unknown')
        with self.assertRaisesRegex(ValueError,'Query ID churn'):
            observe(Unknown(),'fixture','one',library,source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
                source_output=old['visible_inputs']['source_output'])
        self.assertEqual(len(calls),1)

    def test_actual_new_semantic_type_can_extend_the_seed_without_an_alias(self):
        previous=deepcopy(self.old);previous['spec']['decision_program']='def apply(inputs,premises):\n    return {}\n'
        added={'name':'source_event','sort':'Trigger','arguments':['text'],'meaning':'An actual source-stated event, not a preset endpoint.'}
        semantic={'constructors':[added],'decision_functions':[]}
        library=compile_update(previous,self.proposal,{'fixture':'Alpha. Beta.'},semantic_update=semantic)
        self.assertIn(added,library['spec']['constructors']);self.assertNotIn(added,previous['spec']['constructors'])
        with self.assertRaises(ValueError):
            compile_update(previous,self.proposal,{'fixture':'Alpha. Beta.'},semantic_update={
                'constructors':[previous['spec']['constructors'][0]],'decision_functions':[]})

    def test_complete_source_scout_and_local_detail_keep_different_actual_scopes(self):
        library=deepcopy(self.library);scout=deepcopy(library['operations'][0]);scout['name']='scout'
        library['operations'].append(scout);library['operation_scopes']={'scout':'window','meaning':'focus_last'}
        library['planner_program']='''def apply(inputs,premises):
    return {'queries':[{'id':'s','operation':'scout','unit_ids':[4,9]},
                       {'id':'d','operation':'meaning','unit_ids':[4,9]}]}
'''
        calls=[]
        class Client(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append(kwargs['messages']);current=json.loads(kwargs['messages'][1]['content'])['current_queries']
                return {'finish_reason':'stop','content':json.dumps({'answers':{q['id']:{'choice':'first',
                    'evidence_unit_ids':[9]} for q in current}})}
        source=self.observation('one','Alpha.','first')['visible_inputs']['source_output']
        result=observe(Client(),'fixture','one',library,source_text='Alpha. Beta.',
            units=[{'id':4,'text':'Alpha.'},{'id':9,'text':'Beta.'}],source_output=source)
        self.assertNotIn('focus_unit_id',calls[0][0]['content']);self.assertIn('focus_unit_id',calls[1][0]['content'])
        self.assertEqual(result['visible_inputs']['query_scopes'],{'s':'window','d':'focus_last'})
        self.assertNotIn(fact('query_focus','s',9),result['context']['facts'])
        self.assertIn(fact('query_focus','d',9),result['context']['facts'])

    def test_complete_source_absence_survives_encoder_revalidation_and_lossless_roundtrip(self):
        from legal_skill_guard.skill_evolution.source_observations import decode_visible_inputs
        library=deepcopy(self.library)
        library['operations'][0]['choices'].append({'name':'absent','meaning':'Absent after inspecting the complete source.'})
        library['complete_source_absence_choices']={'meaning':['absent']}
        library['scope']='focus_last';library['operation_scopes']={'meaning':'window'}
        library['planner_program']="def apply(inputs,premises):\n    return {'queries':[{'id':'q','operation':'meaning','unit_ids':[4,9]}]}\n"
        calls=[]
        class Client(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append(args)
                return {'finish_reason':'stop','content':json.dumps({'answers':{'q':{'choice':'absent','evidence_unit_ids':[]}}})}
        source=self.observation('one','Alpha.','first')['visible_inputs']['source_output']
        result=observe(Client(),'fixture','one',library,source_text='Alpha. Beta.',
            units=[{'id':4,'text':'Alpha.'},{'id':9,'text':'Beta.'}],source_output=source)
        self.assertEqual(len(calls),1)
        self.assertEqual(result['visible_inputs'],decode_visible_inputs(result))
        answer=result['visible_inputs']['answers'][0]
        self.assertEqual(answer['choice'],'absent');self.assertEqual(answer['evidence'],[])
        self.assertEqual(answer['complete_source_evidence']['unit_ids'],[4,9])
        self.assertIn(fact('query_choice','q','absent'),result['context']['facts'])
        self.assertNotIn(fact('query_focus','q',9),result['context']['facts'])
        self.assertFalse(answer['source_semantics_verified'])

        # The encoder cannot trust a prior claim of completeness when the
        # actual current query or its scope is different.
        visible=result['visible_inputs']
        for queries,scopes in [([{**visible['queries'][0],'unit_ids':[4]}],{'q':'window'}),
                               (visible['queries'],{'q':'focus_last'})]:
            with self.subTest(scopes=scopes,queries=queries),self.assertRaisesRegex(ValueError,'complete current source'):
                encode_source_observations('one',source_text=visible['source_text'],units=visible['units'],
                    source_output=source,operations=visible['operations'],queries=queries,
                    answers=visible['answers'],scope='focus_last',query_scopes=scopes,
                    complete_source_absence_choices=library['complete_source_absence_choices'])

    def test_changed_scope_cannot_reuse_a_different_previous_interpretation(self):
        old=self.observation('one','Alpha.','unknown');library=deepcopy(self.library)
        library['operation_scopes']={'meaning':'window'};calls=[]
        class Client(FixtureClient):
            def generate(self,*args,**kwargs):
                calls.append(args);return {'finish_reason':'stop','content':json.dumps({'answers':{'q':{'choice':'unknown','evidence_unit_ids':[]}}})}
        result=observe(Client(),'fixture','one',library,source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
            source_output=old['visible_inputs']['source_output'],previous_observation=old)
        self.assertEqual(len(calls),1);self.assertEqual(result['execution']['new_physical_requests'],1)
