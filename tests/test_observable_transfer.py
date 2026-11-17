import unittest
from copy import deepcopy

from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, Pair
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.partial_native_loss import replay_bounds
from legal_skill_guard.paired_interfaces.observable_transfer import (
    ASSUMPTIONS, RESIDUAL, fit_observable, choose_observable, model_record, restore_model)
from legal_skill_guard.paired_interfaces.formal_learning import fit_prefix, arm_snapshot, select, pair_record
from legal_skill_guard.paired_interfaces.empirical_channel import graph_record


def world(count=1):
    return Graph(tuple([('a','person'),('b','person')]+[(f'e{i}','event') for i in range(count)]),
        frozenset(Fact(p,(f'e{i}',v)) for i in range(count) for p,v in [('worker','a'),('employer','b')]),'fixture','law')


def swapped(graph):
    return Graph(graph.nodes,frozenset(Fact(f.predicate,(f.arguments[0], 'b' if f.predicate=='worker' else 'a'))
        for f in graph.facts),graph.schema,graph.context)


def consume(graph):
    return {'handled':True,'signature':str(all(f.arguments[1]=='a' for f in graph.facts if f.predicate=='worker'))}


def cohort(bad=True,n=64):
    x=world();y=swapped(x) if bad else x
    return [Pair('d',x,y,'v','development','fixture')],[Pair(f'c{i}',x,y,'v','calibration','fixture') for i in range(n)]


class ObservableTransferTests(unittest.TestCase):
    def test_new_structure_changes_risk_and_replay_has_no_support(self):
        d,c=cohort();model=fit_observable(d,c);x=world(2)
        result=model.predict(NativeLoss(consume),{x:1.},assumptions=ASSUMPTIONS)
        self.assertEqual(result['empirical_interval'],[1.,1.])
        self.assertLess(result['source_cluster_radius'],.2)
        self.assertFalse(replay_bounds(c,NativeLoss(consume),{x:1.})['supported'])
        d2,c2=cohort(False);good=fit_observable(d2,c2).predict(NativeLoss(consume),{x:1.},assumptions=ASSUMPTIONS)
        choice=choose_observable({'columns':result,'records':good},baseline='columns')
        self.assertEqual(choice['plan'],'records');self.assertTrue(choice['certified_separation'])
        self.assertFalse(choice['costs_used'])

    def test_same_support_agrees_with_complete_replay_for_fixed_joint_error(self):
        for bad in (True,False):
            d,c=cohort(bad);model=fit_observable(d,c)
            prediction=model.predict(NativeLoss(consume),{world():1.},assumptions=ASSUMPTIONS)
            replay=replay_bounds(c,NativeLoss(consume),{world():1.})
            self.assertEqual(prediction['empirical_interval'],replay['empirical_risk_interval'])

    def test_unknown_residual_is_retained_and_unrestricted_bound_not_relabelled(self):
        d,c=cohort(False);c=[Pair(p.source_id,p.reference,swapped(p.reference),p.plan_version,p.role,p.provenance) for p in c]
        model=fit_observable(d,c);self.assertEqual(set(model.events),{RESIDUAL})
        result=model.predict(NativeLoss(consume),{world(2):1.},assumptions=ASSUMPTIONS)
        self.assertEqual(result['interval'],[0.,1.]);self.assertEqual(result['observable_residual_mass'],1.)
        self.assertEqual(result['unrestricted_latent_risk_interval'],[0.,1.])

    def test_ties_do_not_create_ranking_and_assumptions_are_required(self):
        d,c=cohort();m=fit_observable(d,c)
        with self.assertRaises(ValueError):m.predict(NativeLoss(consume),{world():1.},assumptions=())
        tied=choose_observable({'records':{'supported':True,'interval':[0,1]},'columns':{'supported':True,'interval':[0,1]}},baseline='columns')
        self.assertFalse(tied['supported']);self.assertFalse(tied['risk_informed_ranking'])

    def test_frozen_roundtrip_and_role_version_guards(self):
        d,c=cohort();m=fit_observable(d,c);r=model_record(m)
        self.assertEqual(restore_model(r).diagnostics(),m.diagnostics())
        changed=deepcopy(r);changed['events'][0]=list(RESIDUAL)
        with self.assertRaises(ValueError):restore_model(changed)
        with self.assertRaises(ValueError):fit_observable(d,[Pair('d',world(),world(),'v','calibration','fixture')])
        with self.assertRaises(ValueError):fit_observable(d,[Pair('c',world(),world(),'v2','calibration','fixture')])

    def test_full_formal_primary_is_revised_and_not_the_unrestricted_selector(self):
        x=world();roles=[{'source':'d','role':'development','dataset':'fixture','batch':1}]
        roles += [{'source':f'c{i}','role':'calibration','dataset':'fixture','batch':1} for i in range(64)]
        roles += [{'source':'r','role':'reference_only','dataset':'fixture','batch':1}]
        paired,scores=[],[]
        for plan,bad in [('columns',True),('records',False)]:
            d,c=cohort(bad)
            for pair in d+c:
                paired.append({'source':pair.source_id,'dataset':'fixture','view':'v0','plan':plan,'pair':pair_record(pair)})
                scores.append({'source':pair.source_id,'dataset':'fixture','view':'native','plan':plan,'grade':0.,'handled':False})
        snapshot=fit_prefix(roles,1,paired,[{'source':'r','dataset':'fixture','view':'v0','graph':graph_record(world(2))}],scores,
            {r['source']:['native'] for r in roles},candidate_orders={'fixture':['columns','records']},
            source_opaque_views={r['source']:['v0'] for r in roles})
        decision=select(arm_snapshot(snapshot,'M1_M2'),dataset='fixture',schema='fixture',context='law',arm='M1_M2',consume=consume)
        self.assertEqual(decision['plan'],'records')
        self.assertFalse(decision['unidentified_unrestricted_selector_executed'])
        replay=select(arm_snapshot(snapshot,'M1_full_trace_replay'),dataset='fixture',schema='fixture',context='law',arm='M1_full_trace_replay',consume=consume)
        self.assertEqual(replay['risks']['columns']['empirical_risk_interval'],[1.,1.])
        self.assertEqual(replay['risks']['records']['empirical_risk_interval'],[0.,0.])
        self.assertEqual(replay['risks']['columns']['paired_mothers'],65)


if __name__=='__main__':unittest.main()
