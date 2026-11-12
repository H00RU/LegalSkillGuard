import unittest

from legal_skill_guard.skill_evolution.binding_learning import learn,resolve,fit_dnf


class BindingLearningTests(unittest.TestCase):
    schema={name:{'name':name,'sort':sort,'arguments':args,'meaning':'Neutral test constructor '+name}
            for name,sort,args in [('a','A',['text']),('b','B',['text']),('pair','Pair',['A','B']),('twice','Pair',['A','A'])]}

    def case(self,unit,other_a,other_b):
        fragments=[{'id':0,'kind':'claim','unit':unit,'header':None,'support_ids':[unit],
            'term':['pair',{'slot':'x','sort':'A'},{'slot':'y','sort':'B'}],'requires':[]}]
        for i,(op,u) in enumerate([('a',0),('b',0),('a',other_a),('b',other_b)],1):
            fragments.append({'id':i,'kind':'value','unit':u,'header':None,'support_ids':[u],
                'term':[op,str(i)],'requires':[]})
        return {'fragments':fragments,'bindings':[
            {'claim':0,'providers':{'x':x,'y':y},'positive':x==1 and y==2}
            for x in (1,3) for y in (2,4)]}

    def test_joint_binding_learns_relation_and_reuses_on_new_positions(self):
        model=learn([self.case(3,1,2),self.case(4,2,3)],self.schema)
        case=self.case(5,3,4)
        actual=resolve(model,case['fragments'],self.schema)
        nearest=resolve(model,case['fragments'],self.schema,nearest=True)
        self.assertEqual(actual['statements'][0]['term'],['pair',['a','1'],['b','2']])
        self.assertNotEqual(actual['statements'],nearest['statements'])
        self.assertTrue(actual['binding_uses'][0]['learned_binding_policy_used'])
        self.assertEqual(actual['statements'][0]['support_ids'],[0,5])

    def test_independent_slots_cannot_resolve_identical_local_features(self):
        model=learn([self.case(3,1,2),self.case(4,2,3)],self.schema,cross_slot=False)
        self.assertTrue(model['rejected_families'])
        result=resolve(model,self.case(5,3,4)['fragments'],self.schema)
        self.assertEqual(result['statements'],[])
        self.assertTrue(result['unresolved'])

    def test_unseparable_observations_do_not_create_source_ids_or_defaults(self):
        with self.assertRaisesRegex(ValueError,'No consistent'):
            fit_dnf([{'features':{'same':True},'positive':True},
                     {'features':{'same':True},'positive':False}])

    def test_repeated_slot_reuses_one_source_value(self):
        case=self.case(0,1,2)
        case['fragments'][0]['term']=['twice',{'slot':'x','sort':'A'},{'slot':'x','sort':'A'}]
        case['bindings']=[{'claim':0,'providers':{'x':1},'positive':True},
                          {'claim':0,'providers':{'x':3},'positive':False}]
        model=learn([case],self.schema)
        result=resolve(model,case['fragments'],self.schema)
        self.assertEqual(result['statements'][0]['term'],['twice',['a','1'],['a','1']])
        self.assertEqual(result['binding_uses'][0]['assignments'],[{'v0':1}])

    def test_variable_names_do_not_prevent_transfer(self):
        model=learn([self.case(3,1,2),self.case(4,2,3)],self.schema)
        case=self.case(5,3,4)
        case['fragments'][0]['term']=['pair',{'slot':'other_name','sort':'A'}, {'slot':'different_name','sort':'B'}]
        result=resolve(model,case['fragments'],self.schema)
        self.assertEqual(result['statements'][0]['term'],['pair',['a','1'],['b','2']])

    def test_unobserved_assignments_are_not_automatically_negative(self):
        case=self.case(3,1,2);case['bindings']=[case['bindings'][0]]
        model=learn([case],self.schema)
        self.assertEqual(next(iter(model['policies'].values()))['negative_assignments'],0)
        self.assertEqual(resolve(model,case['fragments'],self.schema)['statements'],[])

    def test_partial_target_type_is_checked_before_learning(self):
        case=self.case(3,1,2)
        case['fragments'][0]['term']=['pair',{'slot':'x','sort':'A'},{'slot':'x','sort':'A'}]
        # A malformed target type is rejected during actual output checking.
        case['bindings'][0]['providers']={'x':1}
        with self.assertRaisesRegex(ValueError,'sort mismatch'):
            learn([case],self.schema)

    def test_runtime_decoder_terms_bind_and_preserve_all_source_witnesses(self):
        from experiments.legal_skill_evolution_binding_TRAIN import decode
        raw={'fragments':[
            {'kind':'value','quote':'alpha.','support_ids':[0],'term':['a','alpha'],'requires':[]},
            {'kind':'value','quote':'beta.','support_ids':[1],'term':['b','beta'],'requires':[]},
            {'kind':'claim','quote':'join.','support_ids':[2],
             'term':['pair',{'slot':'first','sort':'A'},{'slot':'second','sort':'B'}],'requires':[]}],
            'unresolved':[]}
        compiled={'spec':{'constructors':list(self.schema.values())},
                  'program':'def apply(inputs,premises):\n    return '+repr(raw)}
        source={'key':'test-only','views':[{'public':{'source_text':'alpha.\nbeta.\njoin.',
            'sentence_spans':[[0,6],[7,12],[13,18]]}}]}
        case=decode(compiled,source)
        case['bindings']=[{'claim':2,'providers':{'first':0,'second':1},'positive':True}]
        model=learn([case],self.schema)
        result=resolve(model,case['fragments'],self.schema)
        self.assertEqual(result['statements'],[{'term':['pair',['a','alpha'],['b','beta']],
                                               'support_ids':[0,1,2]}])

    def test_teacher_frontend_transport_is_text_and_round_trips_without_dispatch(self):
        import json
        from pathlib import Path
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        from experiments import legal_skill_evolution_binding_TRAIN as experiment
        from legal_skill_guard.skill_evolution.teacher_transport import unpack
        payload={'source':'example','repeated':['same'*100,'same'*100]}
        seen=[]
        class FakeTeacher:
            def __init__(self,*args):pass
            def propose(self,*args,**kwargs):
                prompt=kwargs['user_prompt']
                self_test.assertIsInstance(prompt,str)
                self_test.assertEqual(unpack(json.loads(prompt)),payload)
                seen.append(prompt)
                return {'mock_transport_only':True}
        self_test=self
        with TemporaryDirectory() as tmp:
            state=(Path(tmp),{'teacher_profile':{},'teacher_sources':[]},None,{})
            with patch.object(experiment,'setup',return_value=state), \
                 patch.object(experiment,'packed_training',return_value=payload), \
                 patch.object(experiment,'FrozenTeacher',FakeTeacher):
                experiment.frontend(Path(tmp))
        self.assertEqual(len(seen),1)


if __name__=='__main__':unittest.main()
