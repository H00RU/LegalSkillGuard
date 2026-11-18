import unittest
from legal_skill_guard.paired_interfaces.diversity import public_source
from legal_skill_guard.paired_interfaces.diversity_amount_judgment_supervision import controlled_amount_judgment_relation
from legal_skill_guard.paired_interfaces.diversity_amount_supervision import controlled_amount_relation
from legal_skill_guard.paired_interfaces.diversity_supervision import group_relation
from legal_skill_guard.paired_interfaces.shared_semantics import matches_assertions
from legal_skill_guard.paired_interfaces.shared_semantics_validation import unsupported_literal_assertions


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

    def test_entailed_high_amount_preserves_the_shared_threshold_restriction(self):
        source = public_source({'index': 'joint', 'text': 'Amy is from Texas. Bob is from Maine. Carl is from Utah. '
                                'Amy and Bob both sue Carl for $12,000 and $99,000.'},
                               'diversity_5', project_split='train')
        group = controlled_amount_relation(source, ['amount_0', 'amount_1'], entailed_anchor=True)
        self.assertEqual({tuple(row) for row in group['shared']['signatures'].values()},
                         {(False, False, True), (False, True, True), (True, True, True)})
        self.assertIn([True, False, True], group['independent']['signatures'].values())
        self.assertEqual(group['latent_representatives'], [0, 5001, 65001])
        self.assertEqual(len(group['covered_pairs']), 2)
        for case in group['cases']:
            self.assertNotIn('$99,000', case.public['source_text'])
            self.assertEqual(case.public['source_text'].count('an unspecified dollar amount'), 1)

    def test_verified_literal_amounts_still_permit_a_discriminating_legal_judgment(self):
        source = public_source({'index': 'joint', 'text': 'Amy is from Texas. Bob is from Maine. Carl is from Utah. '
                                'Amy and Bob both sue Carl for $12,000 and $99,000.'},
                               'diversity_5', project_split='train')
        group = controlled_amount_judgment_relation(source, ('amount_0', 'amount_1'))
        rows = [{'stated_amount': amount, 'unstated_amount': None, 'exceeds_threshold': judgment}
                for amount, judgment in zip(group['ordered_stated_amounts'], (True, False, True), strict=True)]
        shared = group['shared']['signatures'].values()
        independent = group['independent']['signatures'].values()
        fields = group['literal_assertion_fields']
        self.assertEqual(unsupported_literal_assertions(rows, shared, fields), [])
        self.assertFalse(any(matches_assertions(rows, candidate) for candidate in shared))
        self.assertTrue(any(matches_assertions(rows, candidate) for candidate in independent))
        rows[0]['unstated_amount'] = 66000
        self.assertEqual(unsupported_literal_assertions(rows, shared, fields),
                         [{'case_index': 0, 'field': 'unstated_amount'}])


if __name__=='__main__':unittest.main()
