"""Unknown programs retain normal execution; only proved enum mismatch skips."""
from dataclasses import replace
import unittest
from legal_skill_guard.skill_evolution.answer_domain import literal_answers, incompatible_native_enum
from legal_skill_guard.skill_evolution.objects import Skill, Library
from legal_skill_guard.skill_evolution.runtime import SkillRuntime


class AnswerDomainTests(unittest.TestCase):
    def test_all_assignments_and_both_conditional_branches_are_included(self):
        body='def apply(inputs, premises):\n    answer = "Contradiction"\n    if inputs["x"]:\n        answer = "Entailment"\n    return {"answer": answer}'
        self.assertEqual(literal_answers(body), {'Entailment', 'Contradiction'})
        self.assertTrue(incompatible_native_enum(body, {'type':'string','enum':['Yes','No']}))
        self.assertIsNone(incompatible_native_enum(body, {'type':'string','enum':['Entailment','Contradiction','NotMentioned']}))
        inline='def apply(inputs, premises):\n    return {"answer": "Yes" if inputs["x"] else "No"}'
        self.assertEqual(literal_answers(inline), {'Yes','No'})

    def test_dynamic_assignment_alias_and_augmented_write_remain_unknown(self):
        for statement in ('answer = inputs["x"]','other = "Yes"\n    answer = other',
                          'answer = "Yes"\n    answer += inputs["x"]'):
            body='def apply(inputs, premises):\n    '+statement+'\n    return {"answer": answer}'
            self.assertIsNone(literal_answers(body))

    def test_dynamic_or_overriding_return_records_cannot_be_proved(self):
        for result in ('inputs["result"]','{"answer": "Yes", **inputs}', '{"answer": "Yes", "answer": inputs["x"]}'):
            self.assertIsNone(literal_answers('def apply(inputs, premises):\n    return '+result))
        self.assertIsNone(literal_answers('def apply(inputs, premises):\n    def answer():\n        return "Yes"\n    return {"answer": answer()}'))

    def test_pattern_capture_and_nonstandard_arguments_remain_unknown(self):
        body='def apply(inputs, premises):\n    answer = "Entailment"\n    match inputs["label"]:\n        case answer:\n            pass\n    return {"answer": answer}'
        self.assertIsNone(literal_answers(body))
        self.assertIsNone(literal_answers('def apply(answer, premises):\n    if premises["x"]:\n        answer = "Entailment"\n    return {"answer": answer}'))
        self.assertIsNone(literal_answers('def apply(inputs, premises, *, answer="Yes"):\n    if inputs["x"]:\n        answer = "Entailment"\n    return {"answer": answer}'))

    def test_terminal_skip_preserves_selected_roots_and_uses_same_direct_fallback(self):
        body='def apply(inputs, premises):\n    return {"answer": "Entailment"}'
        helper=Skill(id='fixture',intent='Fixture',procedure=body,inputs={'x':{'type':'integer','mode':'read','question':'Fixture only'}},
            outputs={'answer':{'type':'string'}},premises={},reads=(),semantic_records=(),source_obligations=(),source_provenance=()).validate()
        class Reads:
            def read(self,*args,**kwargs):raise AssertionError('Proved-invalid terminal caused a model read')
            def direct(self,source,view,purpose):return {'answer':'Yes','evidence_sentence_ids':[],'events':[], 'core_executed':False,'fallback':True}
        result=SkillRuntime(Reads()).run({'key':'fixture'},{'id':'native','answer_schema':{'type':'string','enum':['Yes','No']}},Library(skills={'fixture':helper}),retrieved=['fixture'])
        self.assertEqual(result['answer'],'Yes');self.assertEqual(result['retrieved'],['fixture'])
        self.assertTrue(result['fallback']);self.assertFalse(result['core_executed'])

    def test_an_incompatible_native_label_can_still_be_an_intermediate_output(self):
        producer=Skill(id='p',intent='Fixture',procedure='def apply(inputs, premises):\n    return {"answer": "Entailment"}',
            inputs={},outputs={'answer':{'type':'string'}},premises={},reads=(),semantic_records=(),source_obligations=(),source_provenance=()).validate()
        consumer=replace(producer,id='c',inputs={'label':{'type':'string','mode':'skill','skill_id':'p','field':'answer'}},
            procedure='def apply(inputs, premises):\n    return {"answer": "Yes" if inputs["label"] == "Entailment" else "No"}').validate()
        class Reads:
            def direct(self,*args,**kwargs):raise AssertionError('Valid dependency path fell back')
        result=SkillRuntime(Reads()).run({'key':'fixture'},{'id':'native','answer_schema':{'type':'string','enum':['Yes','No']}},
            Library(skills={'p':producer,'c':consumer}),retrieved=['p','c'])
        self.assertEqual(result['answer'],'Yes');self.assertTrue(result['core_executed'])
        self.assertEqual([e['kind'] for e in result['events']],['APPLY','USE','APPLY'])


if __name__ == '__main__':unittest.main()
