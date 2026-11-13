"""The actual source-function teacher wire, compilation and observer path."""
from copy import deepcopy
import json
import unittest

import jsonschema

from experiments.legal_skill_evolution_diagnosed_update_train import SCHEMA
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.acquisition_proposal import compile_proposal
from legal_skill_guard.skill_evolution.open_acquisition import observe, execute
from legal_skill_guard.skill_evolution.source_observations import signatures
from legal_skill_guard.skill_evolution.scoped_grammar import constructors, term_sort


PLAN='def apply(inputs,premises):\n    return {"queries":[]}\n'
OLD='def apply(inputs,premises):\n    return {"statements":[],"complete":False,"unresolved":[]}\n'
NEW="""def apply(inputs,premises):
    return {'statements':[{'term':['norm',inputs['source_spans'][0]['text']],
        'support_ids':[inputs['source_spans'][0]['id']]}],'complete':False,'unresolved':[]}
"""


def fixture(arm):
    previous={'operations':[],'planner_program':PLAN,'source_program':OLD,
        'spec':{'constructors':[{'name':'norm','sort':'Norm','arguments':['text'],'meaning':'Software fixture'}],
                'seeds':[],'decision_program':'def apply(inputs,premises):\n    return {}\n'}}
    language={'signatures':{'keep_root':{'arguments':['term'],'kind':'output'}},'constants':{},
        'rules':[{'id':'keep','cost':1,'head':{'predicate':'keep_root','arguments':[{'var':'R'}],'sign':'positive'},
                  'body':[{'predicate':'legacy_root','arguments':[{'var':'R'}],'sign':'positive'}]}]}
    proposal={'rationale':'Software fixture only','operations':[],'planner_functions':[],
        'composition':json.dumps(language) if arm=='ConstraintAcquire' else
            'def apply(inputs,premises):\n    return inputs["source_output"]\n',
        'renderers_json':'[]','suggested_rule_ids':['keep'] if arm=='ConstraintAcquire' else [],
        'new_constructors':[],'decision_functions':[],'reading_contracts':[], 'source_functions':[NEW]}
    sources={'Example:source_1':{'parent_id':'mother_1','views':[{'public':{'source_text':'Alpha.'}}]}}
    return previous,proposal,sources


class SourceFunctionProtocolTests(unittest.TestCase):
    def test_acquired_choice_domain_is_installed_for_both_architectures(self):
        for arm in ('ConstraintAcquire','FreeUpdate'):
            with self.subTest(arm=arm):
                previous,proposal,sources=fixture(arm)
                previous['spec']['scalar_sorts']={'choice':['inherited']}
                proposal['operations']=[{'name':'material_scope','question':'Which material?',
                    'choices':[{'name':'confidential_information_and_copies',
                                'meaning':'Protected information and its copies.'}], 'examples':[]}]
                proposal['reading_contracts']=[{'operation':'material_scope','scope':'window',
                                               'complete_source_absence_choices':[]}]
                proposal['new_constructors']=[{'name':'source_disposal_material',
                    'sort':'Information','arguments':['choice','text'],
                    'meaning':'The acquired material classification with its exact source.'}]
                snapshot=deepcopy(previous)
                library,receipt=compile_proposal(previous,proposal,arm,sources)
                schema=constructors(library['spec'])
                self.assertEqual(term_sort(['source_disposal_material',
                    'confidential_information_and_copies','Alpha.'],schema),'Information')
                self.assertEqual(schema.scalar_sorts['choice'],
                    ['confidential_information_and_copies','inherited'])
                self.assertEqual(receipt['finite_scalar_sorts_from_actual_acquired_vocabulary'],
                    library['spec']['scalar_sorts'])
                for unsupported in ('unknown','invented_material','Entailment'):
                    with self.assertRaises(ValueError):
                        term_sort(['source_disposal_material',unsupported,'Alpha.'],schema)
                self.assertEqual(previous,snapshot)

    def test_teacher_wire_requires_source_functions_and_is_strict_provider_compatible(self):
        self.assertEqual(strict_output_schema_issues(SCHEMA),[])
        _,proposal,_=fixture('FreeUpdate');jsonschema.validate(proposal,SCHEMA)
        del proposal['source_functions']
        with self.assertRaises(jsonschema.ValidationError):jsonschema.validate(proposal,SCHEMA)

    def test_both_architectures_execute_the_actual_wire_update_before_observing(self):
        for arm in ('ConstraintAcquire','FreeUpdate'):
            with self.subTest(arm=arm):
                previous,proposal,sources=fixture(arm)
                library,receipt=compile_proposal(previous,proposal,arm,sources,
                    source_functions=proposal['source_functions'])
                self.assertEqual(library['source_program_update']['changed_function_names'],['apply'])
                self.assertEqual(receipt['source_functions_installed'],1)
                observed=observe(object(),'fixture','one',library,source_text='Alpha.',
                    units=[{'id':4,'text':'Alpha.'}],source_output={'statements':[],'complete':False,'unresolved':[]})
                self.assertEqual(observed['visible_inputs']['source_output']['statements'],
                    [{'term':['norm','Alpha.'],'support_ids':[4]}])
                self.assertEqual(observed['execution']['new_physical_requests'],0)
                if arm=='ConstraintAcquire':
                    library['selected_rule_ids']=['keep']
                    use=execute(library,observed)['source_output']['composition_uses'][0]
                    self.assertFalse(use['retained_old_root'])

    def test_empty_update_preserves_seed_and_records_no_changed_function(self):
        previous,proposal,sources=fixture('FreeUpdate');proposal['source_functions']=[]
        library,_=compile_proposal(previous,proposal,'FreeUpdate',sources,source_functions=[])
        self.assertEqual(library['source_program'],OLD)
        self.assertEqual(library['source_program_update']['changed_function_names'],[])

    def test_source_identity_and_semantics_changing_extraction_are_rejected(self):
        for change in [NEW.replace("['norm',inputs['source_spans'][0]['text']]","['norm','Example:source_1']"),
                       '@unsupported_decorator\n'+NEW]:
            previous,proposal,sources=fixture('FreeUpdate')
            original=deepcopy(previous)
            with self.assertRaises(ValueError):
                compile_proposal(previous,proposal,'FreeUpdate',sources,source_functions=[change])
            self.assertEqual(previous,original)
