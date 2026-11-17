import unittest
from copy import deepcopy
from unittest.mock import patch

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.numeric_ports import port_number, normalize_numeric_ports
from legal_skill_guard.paired_interfaces.reference_wire import graph_wire, asset_wire, reference_wire
from legal_skill_guard.paired_interfaces.production_decode import decode_response


class ReferenceChainTests(unittest.TestCase):
    def test_explicit_measurement_units_currency_and_unknowns(self):
        self.assertEqual(port_number('length','19 inches'),19)
        self.assertEqual(port_number('weight','51 pounds'),51)
        self.assertEqual(port_number('ticket_price','$1,400'),1400)
        self.assertEqual(port_number('weight','19 inches'),'19 inches')
        self.assertEqual(port_number('amount','51 pounds'),'51 pounds')
        self.assertEqual(port_number('weight','weight is 51 pounds'),'weight is 51 pounds')
        original={'relations':[{'predicate':'weight','status':'unknown','value':None}]}
        self.assertEqual(normalize_numeric_ports(original)[0],original)

    def test_empty_graph_columns_roundtrip_preserves_partial_scope(self):
        graph={'nodes':[],'relations':[],'scope_complete':False,'unresolved':['unknown scope']}
        for plan in gi.plans():
            self.assertEqual(gi.decode_plan(plan,graph_wire(plan,graph))[0],graph)
            self.assertEqual(reference_wire('OpenExempt',plan,{'graph':graph},[]),graph_wire(plan,graph))

    def test_truncation_and_unaligned_columns_do_not_reach_native_execution(self):
        import json
        plan=gi.plans()[0];graph={'nodes':[],'relations':[],'scope_complete':False,'unresolved':[]}
        wire=graph_wire(plan,graph);view={'source_units':[],'native_tasks':['native'],'native_public':{},'scope':{'context':'law'}}
        with patch('legal_skill_guard.paired_interfaces.rich_graph_pairs.consumer_signature',side_effect=AssertionError('must not execute')):
            result=decode_response({'dataset':'MAUD'},view,plan,{'content':json.dumps(wire),'finish_reason':'length'})
            self.assertTrue(result['production_errors']);self.assertFalse(result['native']['native']['handled'])
            wire['nodes']['id']=['dangling']
            result=decode_response({'dataset':'MAUD'},view,plan,{'content':json.dumps(wire),'finish_reason':'stop'})
            self.assertTrue(result['production_errors']);self.assertIsNone(result['graph'])

    def test_revision_hold_stops_formal_dispatch_before_prepare_or_clients(self):
        from experiments import two_method_formal_study as study
        with (patch.object(study,'assert_unexposed_cohorts'),
              patch.object(study,'prepare',side_effect=AssertionError('must not prepare'))):
            with self.assertRaisesRegex(ValueError,'revision hold'):
                study.run()


if __name__=='__main__':unittest.main()
