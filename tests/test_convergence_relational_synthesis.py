"""Exact local semantic checks, not real-reader efficacy evidence."""
import hashlib
import inspect
from textwrap import dedent
import unittest

from legal_skill_guard.paired_interfaces import residual as r


def joint_scope(u,c):
    if any(u[k] is None for k in ('ordinary_target','exception_target','a','b')):
        return {'ordinary':None,'negative':None}
    # Local clause attachment and quantity are distinct observations. Neither
    # field requested from a reader is the final native classification.
    same=u['ordinary_target']==u['exception_target']
    enough=u['a']+u['b']>3
    return {'ordinary':same and enough,'negative':(not same) and enough}


def identity_scope(u,c):
    # Two source slots can exchange actors. Protected consumer outputs name
    # the actor, so a multiset of True/False values loses a real distinction.
    values={u['actor0']:u['amount0'],u['actor1']:u['amount1']}
    return {'for_actor_A':values['A']>1,'for_actor_B':values['B']>1}


def make(fn,domains,scope,valid=lambda u,c:True):
    program=dedent(inspect.getsource(fn))
    return r.FiniteModule.build('scope_fixture',domains,[{}],fn,
        consumer_sha256=hashlib.sha256(program.encode()).hexdigest(),
        source_scope={'source_fields':['facts'],'local_unit':'one source-local clause/party group',**scope},
        valid_domain=valid,program_source=program)


class ConvergenceRelations(unittest.TestCase):
    def test_joint_grammar_composes_multiple_consumer_relations(self):
        spec=make(joint_scope,{'ordinary_target':['ordinary','negative',None],
            'exception_target':['ordinary','negative',None],'a':[0,1,2,None],'b':[0,1,2,None]}, {})
        result=r.propose(spec,relational=True,max_new=6)
        self.assertEqual(result['consumer_relation_count'],2)
        joint=[a for a in result['candidates'] if len([f for f in a['features'] if f['operation']=='relation'])==2]
        self.assertTrue(joint)
        asset=joint[0]
        self.assertFalse(any(f['operation']=='field' for f in asset['features']))
        for state,outcome in zip(spec.states,spec.outcomes):
            self.assertEqual(r.decode(asset,r.encode(asset['features'],state),{},module_binding=spec.binding),outcome[0])
        self.assertFalse(result['candidate_generation_uses_native_labels_or_model_outputs'])

    def test_identity_drop_has_a_concrete_counterexample(self):
        spec=make(identity_scope,{'actor0':['A','B'],'actor1':['A','B'],
            'amount0':[0,2],'amount1':[0,2]},
            {'entity_groups':[{'keys':['actor0'],'fields':['amount0']},
                              {'keys':['actor1'],'fields':['amount1']}]},
            valid=lambda u,c:u['actor0']!=u['actor1'])
        result=r.propose(spec,relational=True,max_new=10)
        self.assertTrue(any(a['operation']=='consumer_keyed_binding' for a in result['candidates']))
        for operation in ['consumer_unkeyed_binding','consumer_marginals_binding']:
            rejected=next(x for x in result['rejected'] if x['operation']==operation)
            self.assertNotEqual(rejected['rejected_by']['left_output'],rejected['rejected_by']['right_output'])
            legal=rejected['legal_source_counterexample']
            self.assertTrue(legal['both_worlds_legal'])
            self.assertNotEqual(legal['left_output']['outputs'],legal['right_output']['outputs'])
        import jsonschema
        asset=next(a for a in result['candidates'] if a['operation']=='consumer_keyed_binding')
        schema=r.reader_schema(asset)
        state=next(s for s in spec.states if s['actor0']=='A' and s['actor1']=='B')
        jsonschema.validate({'status':'complete','observation':{'source_anchor':'pair:0',
            'relations':r.encode(asset['features'],state)},'evidence':[{'field':'facts','quote':'two parties'}]},schema)

    def test_score_compatible_unknown_assertion_is_not_fidelity_verified(self):
        spec=make(joint_scope,{'ordinary_target':['ordinary','negative'],'exception_target':['ordinary'],
            'a':[2],'b':[2]}, {})
        result=r.propose(spec,relational=True,max_new=4);asset=result['candidates'][0]
        provenance=[{'kind':'independent_source_audit','evidence_sha256':'a'*64}]
        reading=r.encode(asset['features'],spec.states[0])
        audit=r.source_fidelity(spec,asset,reading,admissible_states=list(spec.states),provenance=provenance)
        self.assertEqual(audit['status'],'underdetermined_assertion')
        self.assertFalse(audit['source_fidelity_verified'])
        audit=r.source_fidelity(spec,asset,reading,admissible_states=[spec.states[0]],provenance=provenance)
        self.assertTrue(audit['source_fidelity_verified'])
        with self.assertRaisesRegex(ValueError,'independent'):
            r.source_fidelity(spec,asset,reading,admissible_states=list(spec.states),
                provenance=[{'kind':'candidate_prediction','evidence_sha256':'a'*64}])

    def test_unknown_comparison_does_not_become_false(self):
        feature={'operation':'relation','expression':{'op':'eq','args':[
            {'op':'field','field':'owner'},{'op':'constant','value':'debtor'}]}}
        self.assertIsNone(r.feature_value(feature,{'owner':None}))


if __name__=='__main__':unittest.main()
