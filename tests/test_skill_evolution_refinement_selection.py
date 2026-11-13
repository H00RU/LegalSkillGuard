from copy import deepcopy
import unittest
from legal_skill_guard.skill_evolution.callable_rules import compile_library,plan
from legal_skill_guard.skill_evolution.refinement_selection import boolean_pivots,evidenced_refinement_candidates


class RefinementSelectionTests(unittest.TestCase):
    def setUp(self):
        self.material={'source_text':'Interface fixture with a partial conjunction.'}
        v={'program':'''def property_value(facts):
    a=facts.get('observed')
    b=facts.get('missing')
    if a is False or b is False:
        return {'value':False,'used_units':['u'],'open_dependencies':[]}
    return {'value':None,'used_units':['u'],'open_dependencies':['missing']}

def apply(inputs,premises):
    return property_value(inputs['facts'])
''','units':[{'id':'u','clause':'1(a)','kind':'predicate','function':'property_value',
            'arguments':[],'source_field':'source_text','quote':self.material['source_text'],
            'fields':[{'name':'observed','type':'boolean','question':'Observed property?'},
                      {'name':'missing','type':'boolean','question':'Other property?'}]}]}
        self.library=compile_library(v,self.material)
        self.planned=plan(self.library,'Section 1(a) applies to Alice.',self.material)

    def test_known_unverified_input_can_block_a_negative_proof(self):
        known={'observed':True};original=deepcopy(known)
        pivots=boolean_pivots(self.library,self.planned,known)
        evidence={'observed':{'value':False,'evidence':['separately checked observation']}}
        selected=evidenced_refinement_candidates(pivots,evidence)
        self.assertEqual([p['field'] for p in selected],['observed'])
        self.assertEqual(known,original)
        self.assertEqual(evidenced_refinement_candidates(boolean_pivots(self.library,self.planned,known,unknown_only=True),evidence),[])

    def test_counterfactual_without_a_witness_never_becomes_a_repair(self):
        self.assertEqual(evidenced_refinement_candidates(boolean_pivots(self.library,self.planned,{'observed':True}),{}),[])
