from copy import deepcopy
from itertools import product
import unittest

from legal_skill_guard.paired_interfaces.legal_consumers import maud as base, contract
from legal_skill_guard.paired_interfaces.partial_legal_consumer import maud,BASE_SHA256,base_binding
from legal_skill_guard.skill_evolution.objects import digest

ORD='Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)'
NEG='Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)'


def graph(covid='covid_19',covenant='ordinary_course_covenant',status='stated',*,complete=True):
    return {'nodes':[{'id':'e','kind':'exception','concept':covid},
                     {'id':'c','kind':'effect','concept':covenant}],
        'relations':[{'predicate':'exception_for','arguments':['e','c'],'status':status,'value':None}],
        'scope_complete':complete,'unresolved':[] if complete else ['unrelated unread material']}


class PartialLegalConsumerTests(unittest.TestCase):
    def test_every_defined_base_output_is_preserved_over_finite_query_abstraction(self):
        checked=tested=0
        for covid,covenant,status,reverse,extra in product(
                ['pandemic','epidemic','covid_19','unspecified'],
                ['ordinary_course_covenant','negative_interim_covenant','unspecified'],
                ['stated','negated','not_stated'],[False,True],[False,True]):
            g=graph(covid,covenant,status)
            if extra:g['nodes'].append({'id':'extra','kind':'exception','concept':'pandemic'})
            if reverse:g['nodes'].reverse()
            for task in (ORD,NEG):
                old=base(g,task);new=maud(g,task)
                self.assertEqual((new['handled'],new['answer']),(old['handled'],old['answer']))
                tested+=1
                if old['handled']:
                    self.assertTrue(new['handled']);self.assertEqual(new['answer'],old['answer'])
                    self.assertEqual(new.get('used_nodes'),old.get('used_nodes'));checked+=1
        self.assertEqual(tested,288)
        self.assertEqual(checked,84)  # The other204 complete cases are base refusals.

    def test_positive_witness_is_invariant_under_all_tested_complete_extensions(self):
        completions=0
        for wanted,task,covid in product(
                ['ordinary_course_covenant','negative_interim_covenant'],[ORD,NEG],['pandemic','epidemic','covid_19']):
            if (wanted.startswith('ordinary')) != (task==ORD):continue
            partial=graph(covid,wanted,complete=False);before=deepcopy(partial)
            partial['relations'].append({'predicate':'condition','arguments':['c','e'],'status':'unknown','value':None})
            before=deepcopy(partial);result=maud(partial,task)
            self.assertTrue(result['handled']);self.assertEqual(result['answer'],'Yes')
            self.assertEqual(partial,before)
            self.assertEqual(result['partial_F_execution']['input_graph_sha256'],digest(partial))
            for extra_kind,extra_concept,edge_state,reverse in product(
                    ['exception','effect'],['covid_19','unspecified'],
                    ['stated','negated','not_stated'],[False,True]):
                complete=deepcopy(partial);complete['scope_complete']=True;complete['unresolved']=[]
                complete['relations'][-1]['status']=edge_state
                complete['nodes'].append({'id':'new','kind':extra_kind,'concept':extra_concept})
                if reverse:complete['nodes'].reverse()
                original=base(complete,task)
                self.assertTrue(original['handled']);self.assertEqual(original['answer'],result['answer'])
                completions+=1
        self.assertEqual(completions,144)

    def test_no_negative_answer_is_created_from_partial_absence(self):
        g=graph('unspecified',complete=False)
        result=maud(g,ORD)
        self.assertFalse(result['handled']);self.assertIsNone(result['answer'])

    def test_wrong_scope_mention_and_uncertain_attachment_do_not_prove_yes(self):
        for g in [graph(covenant='negative_interim_covenant',complete=False),
                  graph(status='unknown',complete=False),graph(status='negated',complete=False),
                  graph('unspecified',complete=False)]:
            self.assertFalse(maud(g,ORD)['handled'])

    def test_known_contradiction_prevents_vacuous_completion_certificate(self):
        g=graph(complete=False);g['relations'].append({**g['relations'][0],'status':'negated'})
        self.assertFalse(maud(g,ORD)['handled'])
        g=graph(complete=False);g['relations'].append({**g['relations'][0],'status':'unread'})
        self.assertFalse(maud(g,ORD)['handled'])

    def test_a_base_completion_can_change_nonmonotone_query_result(self):
        # Knowledge and CNI permissions need stronger scope evidence. They
        # are counterexamples to applying positive-witness logic everywhere.
        g={'nodes':[{'id':'d','kind':'definition','concept':'knowledge_definition'},
                    {'id':'s','kind':'condition','concept':'reasonable_inquiry_required'}],
           'relations':[{'predicate':'standard','arguments':['d','s'],'status':'stated'}],
           'scope_complete':False,'unresolved':['other definition scope']}
        self.assertFalse(maud(g,'Knowledge Definition-Answer')['handled'])
        complete=deepcopy(g);complete['scope_complete']=True;complete['unresolved']=[]
        self.assertTrue(base(complete,'Knowledge Definition-Answer')['handled'])
        complete['nodes'] += [{'id':'d2','kind':'definition','concept':'knowledge_definition'},
                              {'id':'s2','kind':'condition','concept':'no_inquiry_required'}]
        complete['relations'].append({'predicate':'standard','arguments':['d2','s2'],'status':'stated'})
        self.assertFalse(base(complete,'Knowledge Definition-Answer')['handled'])

    def test_base_source_is_exact_pinned_function_and_input_is_not_repaired(self):
        self.assertEqual(base_binding(),BASE_SHA256)
        g=graph(complete=False);before=deepcopy(g);maud(g,ORD);self.assertEqual(g,before)

    def production_fixture(self):
        import json
        from legal_skill_guard.paired_interfaces.graph_interface import plans
        text='An exception for COVID-19 modifies the ordinary-course covenant.'
        g={'nodes':[{'id':'e','kind':'exception','concept':'covid_19','name':'COVID-19','quote':'COVID-19','unit_id':0},
                    {'id':'c','kind':'effect','concept':'ordinary_course_covenant','name':'ordinary-course covenant','quote':'ordinary-course covenant','unit_id':0}],
            'relations':[{'predicate':'exception_for','arguments':['e','c'],'status':'stated','value':None,'quote':text,'unit_id':0}],
            'scope_complete':False,'unresolved':['Unrelated source scope not read']}
        public={'source_text':text,'question':ORD}
        source={'key':'MAUD:fixture','dataset':'MAUD','views':[{'id':ORD,'public':public,'answer_schema':{'type':'string','enum':['Yes','No']}}]}
        view={'native_tasks':[ORD],'native_public':{ORD:public},
            'source_units':[{'id':0,'field':'source_text','start':0,'end':len(text),'text':text}],
            'scope':{'context':'MAUD:fixture'}}
        return source,view,plans()[1],{'content':json.dumps(g),'finish_reason':'stop'}

    def test_actual_production_decode_and_program_tool_share_identical_extension(self):
        from legal_skill_guard.paired_interfaces.production_decode import decode_response
        from legal_skill_guard.paired_interfaces.control_answers import source_bundle
        from legal_skill_guard.paired_interfaces.control_tools import legal_tools
        source,view,plan,response=self.production_fixture()
        result=decode_response(source,view,plan,response)
        self.assertFalse(result['production_errors']);self.assertEqual(result['native'][ORD]['answer'],'Yes')
        self.assertFalse(result['graph']['scope_complete']);self.assertTrue(result['graph']['unresolved'])
        tools,assets=legal_tools(source,source_bundle(source))
        control=tools['frozen_legal_module']['invoke']({'graph':result['graph'],'task':ORD})
        self.assertEqual(control['answer'],result['native'][ORD]['answer'])
        self.assertEqual(control['partial_F_execution']['protocol'],result['native'][ORD]['partial_F_execution']['protocol'])
        self.assertEqual(assets['completion_invariant_execution']['frozen_base_sha256'],BASE_SHA256)

    def test_partial_proof_does_not_bypass_real_production_decoder_refusal(self):
        from legal_skill_guard.paired_interfaces.production_decode import decode_response
        source,view,plan,response=self.production_fixture();response['finish_reason']='length'
        result=decode_response(source,view,plan,response)
        self.assertTrue(result['production_errors']);self.assertIsNone(result['graph'])
        self.assertFalse(result['native'][ORD]['handled'])


if __name__=='__main__':unittest.main()
