"""Interface regressions, not new legal training data or contribution scores."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.relational_learning import execute_composition
from legal_skill_guard.skill_evolution.source_observations import (
    decode_visible_inputs, encode_source_observations, fact, retain_legacy_roots, signatures)
from legal_skill_guard.skill_evolution.source_composition import render_composition


class SourceObservationTests(unittest.TestCase):
    def setUp(self):
        self.inputs={'source_text':'Alpha. Beta.',
            'units':[{'id':4,'text':'Alpha.'},{'id':9,'text':'Beta.'}],
            'source_output':{'statements':[{'term':['old_ctor',['nested','Actor']],'support_ids':[4]}],
                             'complete':False,'unresolved':['unrepresented qualification']},
            'operations':[{'name':'meaning','question':'What meaning is asserted?',
                'choices':[{'name':'first','meaning':'First meaning'},{'name':'second','meaning':'Second meaning'}],
                'examples':[]}],
            'queries':[{'id':'q1','operation':'meaning','unit_ids':[4,9]},
                       {'id':'q2','operation':'meaning','unit_ids':[4]}],
            'answers':[{'id':'q1','choice':'first','evidence':[{'unit_id':9,'quote':'Beta.'}]}],
            'scope':'focus_last'}

    def test_roundtrip_retains_entire_input_and_original_is_not_modified(self):
        original=deepcopy(self.inputs);encoded=encode_source_observations('one',**self.inputs)
        self.assertEqual(decode_visible_inputs(encoded),encoded['visible_inputs'])
        self.assertEqual(self.inputs,original)
        self.assertEqual(decode_visible_inputs(encoded)['source_output']['unresolved'],['unrepresented qualification'])
        self.assertIn(fact('next_unit',4,9),encoded['context']['facts'])
        self.assertIn(fact('query_focus','q1',9),encoded['context']['facts'])
        self.assertNotIn(fact('query_focus','q1',4),encoded['context']['facts'])

    def test_grounded_is_fallible_and_unread_is_not_a_definite_value(self):
        encoded=encode_source_observations('one',**self.inputs)
        self.assertFalse(encoded['visible_inputs']['answers'][0]['source_semantics_verified'])
        self.assertEqual(len(encoded['context']['unknown_groups']),1)
        self.assertEqual(encoded['context']['unknown_groups'][0][-1],[])
        self.assertNotIn(fact('query_choice','q2','second'),encoded['context']['facts'])

    def test_unknown_choice_is_never_default_false_or_retried(self):
        self.inputs['answers'][0]['choice']='unknown';self.inputs['answers'][0]['evidence']=[]
        encoded=encode_source_observations('one',**self.inputs)
        self.assertIn(fact('query_unknown','q1'),encoded['context']['facts'])
        self.assertEqual(len(encoded['context']['unknown_groups']),2)
        self.assertFalse(any(a['predicate']=='query_choice' for a in encoded['context']['facts']))

    def test_current_evidence_and_query_contract_are_checked(self):
        self.inputs['answers'][0]['evidence'][0]['quote']='Invented'
        with self.assertRaises(ValueError):encode_source_observations('one',**self.inputs)
        self.inputs['answers'][0]['evidence'][0]['quote']='Beta.'
        self.inputs['queries'][0]['unit_ids']=[4]
        with self.assertRaises(ValueError):encode_source_observations('one',**self.inputs)

    def test_window_contract_does_not_invent_a_focus(self):
        self.inputs['scope']='window';encoded=encode_source_observations('one',**self.inputs)
        self.assertFalse(any(a['predicate']=='query_focus' for a in encoded['context']['facts']))

    def test_preserving_old_roots_does_not_claim_their_semantic_correctness(self):
        encoded=encode_source_observations('one',**self.inputs);x={'var':'X'}
        lang={'signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
            'constants':{},'rules':[{'id':'retain','head':fact('keep_root',x),
                'body':[fact('legacy_root',x)],'cost':1}]}
        result=execute_composition(lang,['retain'],encoded['context'])
        self.assertTrue(result['complete'])
        self.assertEqual(retain_legacy_roots(encoded,result['certain_outputs']),self.inputs['source_output']['statements'])

    def test_many_unread_queries_do_not_require_cartesian_world_enumeration(self):
        self.inputs['queries']=[{'id':'q'+str(i),'operation':'meaning','unit_ids':[4]} for i in range(40)]
        self.inputs['answers']=[]
        encoded=encode_source_observations('one',**self.inputs);x={'var':'X'}
        lang={'signatures':{**signatures(),'keep_root':{'arguments':['term'],'kind':'output'}},
            'constants':{},'rules':[{'id':'retain','head':fact('keep_root',x),
                'body':[fact('legacy_root',x)],'cost':1}]}
        result=execute_composition(lang,['retain'],encoded['context'],timeout_seconds=10)
        self.assertTrue(result['complete'])
        self.assertLess(result['solver']['models'],1000)
        self.assertEqual(len(result['certain_outputs']),1)

    def test_whole_window_claim_cites_its_actual_definite_query(self):
        encoded=encode_source_observations('one',**self.inputs)
        lang={'signatures':{**signatures(),'scope_claim':{'arguments':['query'],'kind':'output'}},
            'constants':{},'rules':[]}
        renderer={'predicate':'scope_claim','term':['checked_scope'],
            'support_arguments':[],'support_from_terms':[],'support_from_queries':[0]}
        result={'status':'sat','complete':True,'certain_outputs':[fact('scope_claim','q1')],
            'possible_outputs':[fact('scope_claim','q1')],'unknown_observations_preserved':[]}
        spec={'constructors':[{'name':'checked_scope','sort':'Scope','arguments':[],
            'meaning':'Software fixture for an actually inspected window.'}]}
        out=render_composition(lang,[renderer],encoded,result,spec)
        self.assertEqual(out['statements'][0]['support_ids'],[4,9])
        self.inputs['answers'][0]['choice']='unknown';self.inputs['answers'][0]['evidence']=[]
        unknown=encode_source_observations('one',**self.inputs)
        with self.assertRaises(ValueError):render_composition(lang,[renderer],unknown,result,spec)
