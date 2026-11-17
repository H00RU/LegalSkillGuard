"""Independent simplex witnesses distinguish a structural obstruction from noise."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from experiments import two_method_m2_identifiability_audit as audit
from legal_skill_guard.paired_interfaces.empirical_channel import graph_record
from legal_skill_guard.paired_interfaces.formal_learning import arm_snapshot, fit_prefix, pair_record, select
from legal_skill_guard.paired_interfaces.native_channel_selection import choose_risks
from legal_skill_guard.paired_interfaces.structural_channel import Fact, Graph, IDENTITY, Pair, fit
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest


class IdentifiabilityAuditTests(unittest.TestCase):
    def historical_selector(self):
        return audit.BASE / 'M2_identifiability_audit_v1/1637667ad04395b561d442a4b1c670b89b1b9970e040c72f580d8033b499a6af/source_snapshot/legal_skill_guard/paired_interfaces/formal_learning.py'
    def fixture_channel(self,n,mode):
        graph=Graph((('p','person'),),frozenset({Fact('eligible',('p',))}),'algebra-fixture','fixed')
        pairs=[Pair('constructed:'+str(i),graph,graph,'fixture-version','calibration','constructed-only') for i in range(n)]
        return fit(pairs,{'edits':(IDENTITY,),'development_sources':frozenset({'constructed:dev'})},
                   version='fixture-version',unknown_mode=mode)

    def test_more_perfect_calibration_does_not_rule_out_full_unrestricted_unknown(self):
        for n in (8,64,1024):
            report=audit.channel_witness(self.fixture_channel(n,'unrestricted'))
            self.assertTrue(report['unknown_mass_one_feasible'])
            self.assertTrue(report['unrestricted_constraint_template_verified'])
            self.assertTrue(report['all_checked_upper_bounds_one'])
            self.assertEqual(report['bounded_loss_objective_checks']['all_modeled_losses_zero'][1],1.)

    def test_conditional_detectable_unknown_is_a_different_assumption(self):
        report=audit.channel_witness(self.fixture_channel(64,'detectable_residual'))
        self.assertFalse(report['unknown_mass_one_feasible'])
        self.assertFalse(report['unrestricted_constraint_template_verified'])
        self.assertLess(report['bounded_loss_objective_checks']['all_modeled_losses_zero'][1],1.)

    def test_production_zero_cost_upper_risk_tie_is_not_informed_by_lower_endpoints(self):
        result=choose_risks({'records':{'supported':True,'interval':[0.,1.]},
                             'columns':{'supported':True,'interval':[.9,1.]},
                             'local_records':{'supported':True,'interval':[.1,1.]}},
                            baseline='columns',costs={'records':0.,'columns':0.,'local_records':0.})
        self.assertEqual(result['plan'],'columns')
        self.assertFalse(result['risk_informed_ranking'])

    def test_selector_source_check_does_not_certify_a_different_primary_assumption(self):
        with TemporaryDirectory() as root:
            p=Path(root)/'changed.py';p.write_text("def select():\n costs={p: 0. for p in plans}\n choice=m2['detectable_residual']\n")
            result=audit.selector_contract(p)
            self.assertTrue(result['all_candidate_costs_fixed_zero'])
            self.assertFalse(result['primary_selects_unrestricted_mode'])

    def test_full_primary_selector_keeps_columns_even_when_conditional_model_ranks_records(self):
        # Reproduce the archived historical implementation, not today's revision.
        import importlib.util
        spec=importlib.util.spec_from_file_location('historical_formal_learning',self.historical_selector())
        original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
        fit_prefix,arm_snapshot,select=original.fit_prefix,original.arm_snapshot,original.select
        graph=Graph((('x','event'),),frozenset({Fact('value_A',('x',))}),'fixture-schema','fixture-context')
        other=Graph(graph.nodes,frozenset(),graph.schema,graph.context)
        unseen=Graph(graph.nodes,graph.facts|{Fact('unseen_relation',('x',))},graph.schema,graph.context)
        measured=[('constructed:dev','development')]+[('constructed:cal'+str(i),'calibration') for i in range(64)]
        roles=[{'source':s,'role':r,'dataset':'fixture','batch':1} for s,r in measured]
        roles.append({'source':'constructed:ref','role':'reference_only','dataset':'fixture','batch':1})
        pairs=[];scores=[]
        for plan in ('columns','records'):
            for source,role in measured:
                pair=Pair(source,graph,other if plan=='columns' else graph,digest(['fixture',plan]),role,'constructed-only')
                pairs.append({'source':source,'dataset':'fixture','view':'v0','plan':plan,'pair':pair_record(pair)})
                scores.append({'source':source,'dataset':'fixture','view':'native','plan':plan,
                               'grade':float(plan=='records'),'handled':True})
        snapshot=fit_prefix(roles,1,pairs,[{'source':'constructed:ref','dataset':'fixture','view':'v0','graph':graph_record(unseen)}],
                            scores,{s:['native'] for s,_ in measured},candidate_orders={'fixture':['columns','records']},
                            source_opaque_views={r['source']:['v0'] for r in roles})
        consume=lambda world:{'handled':True,'signature':'A' if Fact('value_A',('x',)) in world.facts else 'B'}
        for arm in ('M1_M2','M2_fixed_interfaces'):
            choice=select(arm_snapshot(snapshot,arm),dataset='fixture',schema=graph.schema,context=graph.context,arm=arm,consume=consume)
            self.assertEqual(choice['plan'],'columns')
            self.assertFalse(choice['risk_informed_ranking'])
            self.assertEqual(choice['conditional_M2_choices']['detectable_residual']['plan'],'records')
            self.assertTrue(choice['conditional_M2_choices']['detectable_residual']['risk_informed_ranking'])

    def test_all_real_saved_channels_are_verified_without_clients_or_heldout_inputs(self):
        original=Path.read_text
        def bounded(path,*args,**kwargs):
            if path.name=='grading.json' or 'sealed_test' in path.parts or 'dev' in path.parts:
                self.fail('audit opened heldout/grading input')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',bounded),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger'))):
            out,report=audit.prepare(selector_source=self.historical_selector())
        self.assertTrue(report['primary_M2_fixed_columns_equivalence_proved_for_current_contract'])
        self.assertEqual(report['real_pilot_fitted_groups'],24)
        self.assertEqual(report['real_unrestricted_channels_with_full_unknown_witness'],24)
        self.assertLess(report['real_conditional_channels_with_full_unknown_witness'],24)
        self.assertFalse(report['goal_completed'])
        self.assertEqual(report['new_model_requests'],0)
        self.assertTrue(report['historical_selector_explicitly_selected'])
        self.assertFalse(report['revised_observable_selector_refuted_by_this_audit'])


if __name__=='__main__':unittest.main()
