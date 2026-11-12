import unittest

from legal_skill_guard.skill_evolution.scoped_grammar import induce
from legal_skill_guard.skill_evolution.scoped_reader import bind, apply_current
from test_skill_evolution_scoped_grammar import fixture


class ScopedReaderChecks(unittest.TestCase):
    def setup_value(self):
        public,spec=fixture()
        value={'statements':[{'expression':'unit(other())','support_ids':[0]}]}
        return public,spec,value

    def test_constructor_expression_lowers_without_losing_owner(self):
        public,spec,value=self.setup_value();grammar=induce(spec,{'TRAIN:fixture':public})
        interpretation=bind(spec,public,value)
        self.assertEqual(interpretation['nodes'][0]['term'],['unit',['other']])
        result=apply_current(spec,grammar,interpretation,{'id':'nda-5','public':{'question':'fixture'}})
        self.assertTrue(result['value']['handled'])
        self.assertTrue(result['root_uses'][0]['induced_target_patterns_matched'])
        self.assertTrue(result['root_uses'][0]['term_not_in_acquired_pairs'])

    def test_variables_wrong_types_and_unacquired_calls_fail(self):
        public,spec,value=self.setup_value()
        for expression in ('unit(ARG0)','unit(tag())','missing()','__import__("os")'):
            value['statements'][0]['expression']=expression
            with self.subTest(expression=expression),self.assertRaises(ValueError):
                bind(spec,public,value)

    def test_semantic_text_is_not_confused_with_verbatim_quotation(self):
        public,spec,value=self.setup_value()
        spec['constructors'].append({'name':'word','meaning':'Fixture text','sort':'entity','arguments':['text']})
        value['statements'][0]['expression']='word("not in source")'
        pending=bind(spec,public,value)['nodes'][0]
        self.assertFalse(pending['text_argument_audit'][0]['verbatim_in_cited_source'])
        self.assertFalse(pending['source_semantics_verified'])
        value['statements'][0]['expression']='word("alpha")'
        self.assertEqual(bind(spec,public,value)['nodes'][0]['term'],['word','alpha'])

    def test_question_is_never_a_source_witness(self):
        public,spec,value=self.setup_value();public['question']='not in source'
        spec['constructors'].append({'name':'word','meaning':'Fixture text','sort':'entity','arguments':['text']})
        value['statements'][0]['expression']='word("not in source")'
        result=bind(spec,public,value)['nodes'][0]
        self.assertFalse(result['text_argument_audit'][0]['verbatim_in_cited_source'])
        self.assertFalse(result['source_semantics_verified'])

    def test_no_interpretations_is_unknown_not_a_negative_fact(self):
        public,spec,_=self.setup_value();grammar=induce(spec,{'TRAIN:fixture':public})
        result=apply_current(spec,grammar,bind(spec,public,{'statements':[]}),
            {'id':'nda-5','public':{'question':'fixture'}})
        self.assertFalse(result['value']['handled']);self.assertIsNone(result['value']['answer'])

    def test_raw_text_roots_and_absent_consumer_proofs_fail(self):
        public,spec,value=self.setup_value();value['statements'][0]['expression']='"alpha"'
        with self.assertRaisesRegex(ValueError,'root must'):bind(spec,public,value)
        value['statements'][0]['expression']='other()';grammar=induce(spec,{'TRAIN:fixture':public})
        spec['decision_program']='def apply(inputs, premises):\n    return {"handled": True, "answer": "Entailment", "used_nodes": [3]}\n'
        with self.assertRaisesRegex(ValueError,'non-root'):
            apply_current(spec,grammar,bind(spec,public,value),{'id':'nda-5','public':{'question':'fixture'}})

    def test_each_statement_retains_its_own_source_scope(self):
        public,spec,value=self.setup_value();public={'source_text':'alpha beta','sentence_spans':[[0,5],[6,10]]}
        spec['constructors'].append({'name':'word','meaning':'Fixture text','sort':'entity','arguments':['text']})
        value['statements'][0]={'expression':'word("alpha")','support_ids':[1]}
        result=bind(spec,public,value)['nodes'][0]
        self.assertFalse(result['text_argument_audit'][0]['verbatim_in_cited_source'])
        self.assertFalse(result['source_semantics_verified'])


if __name__=='__main__':unittest.main()
