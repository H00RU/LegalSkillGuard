from copy import deepcopy
import hashlib
import json
import unittest

from legal_skill_guard.paired_interfaces.control_tools import legal_tools, module_assets
from legal_skill_guard.paired_interfaces.control_answers import source_bundle
from legal_skill_guard.paired_interfaces.native_adapters import LIBRARY, run_airline
from legal_skill_guard.paired_interfaces.native_graph_consumers import (
    BOOLEAN_PORTS, openexempt, partial_skill, sara, sara_binding, sara_query)
from legal_skill_guard.paired_interfaces.rich_graph_pairs import (
    consumer_signature, pair_from_audited_reference, reference_graph, rich_graph)
from tests import test_paired_native_adapters as adapter_fixture


class RichNativeConsumerTests(unittest.TestCase):
    def oe_ports(self):
        return {'asset_descriptions': ['constructed asset'], 'asset_values': [100],
            'governing_regime': 'Illinois', 'number_of_debtors': 1, 'output_family': 'EC',
            **{key: [None] for key in BOOLEAN_PORTS}}

    def test_unknown_unused_flags_are_not_defaulted_and_fixed_program_executes(self):
        values = self.oe_ports()
        values['asset_is_personal_nonbusiness_property'] = [True]
        result = partial_skill(module_assets('OpenExempt')['skill'], values, [])
        self.assertTrue(result['handled'])
        self.assertEqual(result['visited_partial_worlds'], 1)
        self.assertEqual(result['demanded_unknown_paths'], [])
        self.assertIsNone(values['asset_is_wearing_apparel'][0])

    def test_unknown_demanded_flag_keeps_two_completions_and_no_answer(self):
        values = self.oe_ports()
        result = partial_skill(module_assets('OpenExempt')['skill'], values,
            [{'path': ['asset_is_personal_nonbusiness_property', 0], 'values': [False, True]}])
        self.assertFalse(result['handled'])
        self.assertIsNone(result['answer'])
        self.assertEqual(len(result['contrasting_or_representative_completions']), 2)
        limited = partial_skill(module_assets('OpenExempt')['skill'], values,
            [{'path': ['asset_is_personal_nonbusiness_property', 0], 'values': [False, True]}], max_worlds=1)
        self.assertFalse(limited['handled'])
        self.assertIn('limit', limited['reason'])

    def test_raw_OE_graph_runs_same_frozen_program_and_preserves_reader_key(self):
        graph = {'nodes': [{'id': 'p', 'kind': 'person', 'concept': 'unspecified', 'name': 'A'},
            {'id': 'g', 'kind': 'group', 'concept': 'unspecified', 'name': 'Debtors'},
            {'id': 'a', 'kind': 'asset', 'concept': 'household_good', 'name': 'short reader description'}],
            'relations': [{'predicate': 'member_of', 'arguments': ['p','g'], 'value': None, 'status': 'stated'},
                {'predicate': 'amount', 'arguments': ['a'], 'value': '$100.00', 'status': 'stated'}],
            'scope_complete': True, 'unresolved': []}
        public = {'original_input': 'Assume all assets are held for the personal use of the Debtor(s), unless explicitly stated otherwise.\nSolved Reasoning Steps:\nThe Debtors may claim property exemptions under Federal and Wisconsin statutes.\nFacts:\nNo fact is read from this field.'}
        result = openexempt(graph, public, 'EC')
        self.assertTrue(result['handled'])
        self.assertEqual(set(result['answer']), {'short reader description'})
        self.assertIsNone(result['graph_port_projection']['inputs']['asset_is_wearing_apparel'][0])

    def test_literal_rich_Airline_world_matches_actual_frozen_consumer(self):
        graph, units = adapter_fixture.NativeAdapterTests().graph()
        expected = run_airline(graph, units, hashlib.sha256(LIBRARY.read_bytes()).hexdigest())
        (world, _, _), _ = reference_graph(graph, {u['id']:u for u in units}, 'fixed_airline_task')
        restored = rich_graph(world)
        self.assertEqual(next(n for n in restored['nodes'] if n['kind']=='bag')['source_order'], 0)
        result = consumer_signature(world, 'RuleArena_Airline', {'native': {}})
        self.assertTrue(result['handled'])
        self.assertEqual(result['native']['native']['answer'], expected['answer'])
        observed = deepcopy(graph)
        next(e for e in observed['relations'] if e['predicate']=='weight').update(status='unread',value=None)
        pair, _ = pair_from_audited_reference(graph, observed, units,
            source='constructed', role='calibration', version='literal_v2', provenance='fixture',
            context='fixed_airline_task', semantic_reference_verified=True)
        self.assertFalse(consumer_signature(next(iter(pair.observed)), 'RuleArena_Airline', {'native': {}})['handled'])

    def test_SARA_roles_dates_and_explicit_unknowns_survive_projection(self):
        graph = {'nodes': [{'id':'p','kind':'person','concept':'unspecified','name':'Alice'},
            {'id':'s','kind':'event','concept':'service','name':'services'},
            {'id':'pay','kind':'event','concept':'payment','name':'paid'},
            {'id':'t','kind':'time','concept':'unspecified','name':'Feb 1st, 2017'}],
            'relations': [
                {'predicate':'worker','arguments':['s','p'],'value':None,'status':'stated'},
                {'predicate':'recipient','arguments':['s'],'value':None,'status':'unknown'},
                {'predicate':'date_start','arguments':['s','t'],'value':None,'status':'stated'},
                {'predicate':'amount','arguments':['pay'],'value':200,'status':'stated'},
                {'predicate':'date_at','arguments':['pay'],'value':'2017','status':'stated'}],
            'scope_complete':True,'unresolved':['Recipient is unknown.']}
        projected = sara_binding(graph)
        facts = projected['binding']['facts']
        self.assertIn({'predicate':'start_','arguments':['s','2017-02-01']},facts)
        self.assertIn({'predicate':'agent_','arguments':['s','p']},facts)
        self.assertFalse(any(r['predicate'] in ('income_','means_') for r in facts))
        self.assertFalse(any(r['predicate']=='patient_' for r in facts))
        self.assertFalse(any(r['predicate']=='start_' and r['arguments'][0]=='pay' for r in facts))
        self.assertEqual(projected['scope_contract']['family_scans'],[])
        query = sara_query("Section 3306(c)(21) applies to Alice's employment situation in 2017.",graph)
        self.assertEqual(query['query'][0]['arguments'],['s','p',{'variable':'_'},'2017-02-01'])

    def test_author_legal_program_executes_without_original_case_facts_or_query(self):
        graph={'nodes':[],'relations':[],'scope_complete':True,'unresolved':[]}
        result=sara(graph,{'question':'Section 68(f) applies for the year 2018.','facts':'No personal facts.'})
        self.assertTrue(result['handled'])
        self.assertEqual(result['factual_accesses'],[])
        self.assertFalse(result['original_case_query_or_facts_loaded'])
        self.assertTrue(result['source_program_unchanged'])

    def test_rich_graph_keeps_literal_date_changes_as_observed_errors(self):
        text='Alice started Feb 1st, 2017 and stopped Sep 2nd, 2017.'
        units=[{'id':0,'start':0,'end':len(text),'text':text}]
        graph={'nodes':[{'id':'t','kind':'time','concept':'unspecified','name':'Feb 1st, 2017',
                         'unit_id':0,'quote':text}], 'relations':[], 'scope_complete':True,'unresolved':[]}
        observed=deepcopy(graph);observed['nodes'][0]['name']='Sep 2nd, 2017'
        pair,receipt=pair_from_audited_reference(graph,observed,units,source='fixture',role='development',
            version='literal_v2',provenance='constructed',context='date',semantic_reference_verified=True)
        self.assertEqual(rich_graph(pair.reference)['nodes'][0]['name'],'Feb 1st, 2017')
        self.assertEqual(rich_graph(next(iter(pair.observed)))['nodes'][0]['name'],'Sep 2nd, 2017')
        self.assertFalse(receipt['source_alignment_uses_roles_values_or_labels'])

    def test_independent_control_gets_the_same_literal_graph_consumer(self):
        graph, units = adapter_fixture.NativeAdapterTests().graph()
        source={'key':'RuleArena_Airline:constructed','dataset':'RuleArena_Airline',
            'views':[{'id':'native','answer_schema':{'type':'integer'},'public':{
                'facts':units[0]['text'],'question':'Return ticket and fees.','source_text':'Shared fixed rules.'}}]}
        tools, assets=legal_tools(source,source_bundle(source))
        result=tools['source_graph_native_module']['invoke']({'graph':graph,'native_view_id':'native'})
        self.assertTrue(result['handled'])
        self.assertEqual(result['answer'],run_airline(graph,units,hashlib.sha256(LIBRARY.read_bytes()).hexdigest())['answer'])
        self.assertIn('native_graph_consumers.py',assets['shared_native_graph_adapters'])
        self.assertTrue(result['no_case_label_or_other_view_fact_used'])

    def test_independent_control_partial_tool_preserves_unknown_domains(self):
        source={'key':'OpenExempt:constructed','dataset':'OpenExempt','views':[]}
        tools,_=legal_tools(source,{'bundle_native_views':[]})
        values=self.oe_ports()
        result=tools['finite_partial_legal_module']['invoke'](values)
        self.assertFalse(result['handled'])
        self.assertEqual(len(result['contrasting_or_representative_completions']),2)
        values['asset_is_personal_nonbusiness_property']=[True]
        shared=tools['finite_partial_legal_module']['invoke'](values)
        direct=partial_skill(module_assets('OpenExempt')['skill'],values,[])
        self.assertEqual(shared['answer'],direct['answer'])
        self.assertTrue(shared['handled'])


if __name__ == '__main__':
    unittest.main()
