"""Multi-stage dependencies cannot be reduced to independent rule outputs."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.open_acquisition import fit
from legal_skill_guard.skill_evolution.program_composition_profiles import admissible_program_compositions
from legal_skill_guard.skill_evolution.source_observations import encode_source_observations,signatures,fact
from legal_skill_guard.skill_evolution.theory_supervision import attach_theories


class ProgramCompositionProfileTests(unittest.TestCase):
    def fixture(self):
        r,t,u=({'var':name}for name in ('R','T','U'))
        language={'signatures':{**signatures(),'d':{'arguments':['term','unit'],'kind':'derived'},
                    'emit':{'arguments':['term','unit'],'kind':'output'}},'constants':{'position':[0]},
            'rules':[{'id':'derive','cost':1,'head':fact('d',t,u),'body':[
                fact('legacy_root',r),fact('term_child',r,0,t),fact('root_support',r,u)]},
                {'id':'compose','cost':1,'head':fact('emit',t,u),'body':[fact('d',t,u)]}]}
        spec={'constructors':[{'name':name,'sort':sort,'arguments':args,'meaning':'Software fixture'}
            for name,sort,args in [('old','Norm',['Actor']),('new','Norm',['Actor']),('actor','Actor',['text'])]]}
        lib={'language':language,'renderers':[{'predicate':'emit','term':['new',{'term_argument':0}],
             'support_arguments':[1],'support_from_terms':[0]}],'spec':spec,'selected_rule_ids':[]}
        obs=encode_source_observations('fixture',source_text='Alpha.',units=[{'id':4,'text':'Alpha.'}],
            source_output={'statements':[{'term':['old',['actor','Alpha']],'support_ids':[4]}],
                           'complete':False,'unresolved':[]},operations=[],queries=[],answers=[],scope='window')
        return lib,obs

    def test_joint_rule_dependency_enumerates_and_fits_actual_reachable_theories(self):
        lib,obs=self.fixture()
        profile=admissible_program_compositions(lib,obs,
            lambda output:{'accepted':bool(output['statements']),'reason':'fixture_only'})
        self.assertEqual(profile['rule_subsets_checked'],4)
        self.assertEqual(profile['finite_theory_count'],2)
        accepted=[e for e in profile['evaluations'] if e['admissible']]
        self.assertEqual(accepted[0]['witness_rule_ids'],['derive','compose'])
        learned,result=fit(lib,[attach_theories(obs,profile)])
        self.assertEqual(result['status'],'sat')
        self.assertEqual(set(learned['selected_rule_ids']),{'derive','compose'})

    def test_unknown_and_nonpositive_search_budget_are_not_completed_profiles(self):
        lib,obs=self.fixture();unknown=deepcopy(obs)
        unknown['context']['unknown_groups']=[[[],[]]]
        with self.assertRaisesRegex(ValueError,'unknown'):
            admissible_program_compositions(lib,unknown,lambda o:None)
        with self.assertRaises(ValueError):
            admissible_program_compositions(lib,obs,lambda o:None,timeout_seconds=0)
