import unittest
from legal_skill_guard.paired_interfaces.diversity import public_source
from legal_skill_guard.paired_interfaces.diversity_supervision import group_relation


class RealEditClosureTests(unittest.TestCase):
    def test_amount_and_entity_changes_recompute_joint_claim_scope(self):
        source=public_source({'index':'fixture','text':'Amy is from Texas. Bob is from Maine. Carl is from Utah. '
            'Amy sues Bob for $40,000 and $40,000. Amy sues Carl for $80,000.'},'diversity_4',project_split='train')
        group=group_relation(source,[{'amount_0':30000},{'citizenship_1':'Texas'}])
        signature=next(iter(group['relation']['signatures'].values()))
        self.assertEqual([v['answer'] for v in signature],['Yes','No','No'])
        self.assertEqual([v['aic_is_met'] for v in signature],[True,False,True])
        self.assertEqual([v['parties_are_diverse'] for v in signature],[True,True,False])
        self.assertEqual(group['cases'][0].root_id,group['cases'][2].root_id)
        self.assertTrue(all(r['unchanged_source_bytes_preserved'] for r in group['edit_receipts']))
        self.assertTrue(group['shared_vs_single_signatures_identical'])
        self.assertFalse(group['establishes_M2_shared_interpretation_advantage'])


if __name__=='__main__':unittest.main()
