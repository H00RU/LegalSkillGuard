"""MAUD view isolation and native-codec software regressions, not new data."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.maud_source_feedback import evaluate_view,view_units
from legal_skill_guard.skill_evolution.open_acquisition import observe


def fixture():
    views=[{'id':name,'public':{'source_text':text,'question':name},
            'answer_schema':{'type':'string','enum':labels}}
        for name,text,labels in [('Knowledge Definition-Answer','Alpha.',
                                 ['Actual knowledge','Constructive knowledge']),
                                ('Pandemic fixture','Beta.',['Yes','No'])]]
    source={'key':'MAUD:fixture','parent_id':'fixture_parent','split':'train','dataset':'MAUD','views':views}
    library={'operations':[],'scope':'window',
        'planner_program':'def apply(inputs,premises):\n    return {"queries":[]}\n',
        'source_program':'''def apply(inputs,premises):
    return {'statements':[{'term':['norm',inputs['source_spans'][0]['text']],
        'support_ids':[inputs['source_spans'][0]['id']]}],'complete':False,'unresolved':[]}
''',
        'composition_program':'def apply(inputs,premises):\n    return inputs["source_output"]\n',
        'spec':{'constructors':[{'name':'norm','sort':'Norm','arguments':['text'],'meaning':'Fixture only'}],
            'seeds':[],'decision_program':'''def apply(inputs,premises):
    if inputs['task_id']=='Knowledge Definition-Answer':
        return {'handled':True,'answer':'Actual knowledge','used_nodes':[0]}
    return {'handled':True,'answer':'Yes','used_nodes':[0]}
'''}}
    return library,source


class MAUDSourceFeedbackTests(unittest.TestCase):
    def observation(self,library,source,view):
        return observe(object(),'fixture',source['key'],library,
            source_text=view['public']['source_text'],units=view_units(view),
            source_output={'statements':[],'complete':False,'unresolved':[]})

    def test_distinct_view_materials_execute_individually_without_native_grader(self):
        library,source=fixture()
        with patch('legal_skill_guard.skill_evolution.maud_source_feedback.grade_view',
                   side_effect=AssertionError('Unscored path accessed native labels')):
            for view in source['views']:
                o=self.observation(library,source,view)
                self.assertEqual(o['visible_inputs']['source_output']['statements'][0]['term'],
                                 ['norm',view['public']['source_text']])
                result=evaluate_view(library,o,source,view)
                self.assertEqual(result['feedback']['reason'],'unscored_execution')
                self.assertFalse(result['feedback']['accepted'])
                self.assertIsNone(result['feedback']['views'][0]['score'])

    def test_material_from_another_view_cannot_be_substituted(self):
        library,source=fixture();o=self.observation(library,source,source['views'][0])
        with self.assertRaisesRegex(ValueError,'must not be joined'):
            evaluate_view(library,o,source,source['views'][1])

    def test_original_MAUD_labels_score_without_NLI_conversion(self):
        library,source=fixture();view=source['views'][0];o=self.observation(library,source,view)
        result=evaluate_view(library,o,source,view,{'answer':'Actual knowledge'})
        self.assertTrue(result['feedback']['accepted'])
        library=deepcopy(library)
        library['spec']['decision_program']=library['spec']['decision_program'].replace('Actual knowledge','Entailment')
        rejected=evaluate_view(library,o,source,view,{'answer':'Actual knowledge'})
        self.assertEqual(rejected['feedback']['reason'],'execution_error')

    def test_handled_answer_requires_current_typed_source_proof(self):
        library,source=fixture();view=source['views'][0];o=self.observation(library,source,view)
        for program in [library['spec']['decision_program'].replace('[0]','[]'),
                        library['spec']['decision_program'].replace('[0]','[99]')]:
            bad=deepcopy(library);bad['spec']['decision_program']=program
            result=evaluate_view(bad,o,source,view,{'answer':'Actual knowledge'})
            self.assertEqual(result['feedback']['reason'],'execution_error')

    def test_demonstration_may_quote_actual_second_view_but_never_a_join(self):
        library,source=fixture()
        proposal={'rationale':'Fixture only','source_functions':[],
            'operations':[{'name':'meaning','question':'Software assertion?',
                'choices':[{'name':'present','meaning':'Fixture present'}],
                'examples':[{'source':source['key'],'quote':'Beta.','choice':'present'}]}],
            'planner_functions':[],'composition':library['composition_program'],
            'renderers_json':'[]','suggested_rule_ids':[],'new_constructors':[],
            'decision_functions':[],'reading_contracts':[{'operation':'meaning','scope':'window',
                                                       'complete_source_absence_choices':[]}]}
        compiled,_=compile_proposal(library,proposal,'FreeUpdate',{source['key']:source})
        self.assertEqual(compiled['operations'][0]['examples'][0]['quote'],'Beta.')
        proposal['operations'][0]['examples'][0]['quote']='Alpha. Beta.'
        with self.assertRaisesRegex(ValueError,'does not quote'):
            compile_proposal(library,proposal,'FreeUpdate',{source['key']:source})
