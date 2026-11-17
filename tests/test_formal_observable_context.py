import unittest
from unittest.mock import patch
from legal_skill_guard.paired_interfaces.formal_observable import row_loss,complete_replay
from legal_skill_guard.paired_interfaces.formal_learning import pair_record
from legal_skill_guard.paired_interfaces.structural_channel import Pair
from tests.test_observable_transfer import world


class PublicContextTests(unittest.TestCase):
    def test_sara_missing_reference_query_is_not_replaced_by_current_target(self):
        with self.assertRaisesRegex(ValueError,'own public query'):
            row_loss('SARA_v2_Binary',None,lambda g: {'handled':True,'signature':'fake'})

    def test_full_replay_retains_each_source_own_public_context(self):
        seen=[]
        def consume(graph,dataset,public):
            seen.append(public['native']['question'])
            return {'handled':True,'signature':public['native']['question']}
        x=world();records=[{**pair_record(Pair(str(i),x,x,'v','calibration','test')),
            'native_public':{'native':{'question':q}}} for i,q in enumerate(['Alice in 2017','Bob in 2018'])]
        with patch('legal_skill_guard.paired_interfaces.rich_graph_pairs.consumer_signature',side_effect=consume):
            result=complete_replay(records,'SARA_v2_Binary',lambda g: self.fail('current target used'))
        self.assertEqual(set(seen),{'Alice in 2017','Bob in 2018'})
        self.assertEqual(result['empirical_risk_interval'],[0.,0.])

    def test_unknown_reference_is_not_matched_to_unknown_prediction_as_success(self):
        from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
        from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
        self.assertEqual(loss_interval(NativeLoss(lambda g:{'handled':False}),world(),world()),[1.,1.])


if __name__=='__main__':unittest.main()
