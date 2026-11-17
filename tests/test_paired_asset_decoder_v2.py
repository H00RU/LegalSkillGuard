"""Ambiguous evidence stays a set;malformed evidence and unknowns stay errors."""
from copy import deepcopy
import unittest

from tests import test_paired_asset_graph_pairs as fixtures
from legal_skill_guard.paired_interfaces.asset_graph_pairs import pair_from_port_record
from legal_skill_guard.paired_interfaces.asset_port_decoder_v2 import consume, decode
from legal_skill_guard.paired_interfaces.structural_channel import observations
from legal_skill_guard.skill_evolution.objects import digest


class AssetDecoderV2Tests(unittest.TestCase):
    def test_shared_source_quote_retains_all_injective_alignments_without_refilling_values(self):
        card, raw, plan, units = fixtures.AssetGraphPairTests().fixture()
        for row in raw['assets']:
            row['quote'] = units[0]['text']
        record, receipt = decode(plan, raw, units)
        self.assertFalse(receipt['raw_values_statuses_and_scope_bits_changed'])
        pair, alignment = pair_from_port_record(card, record, plan, units, source='fixture',
            role='development', provenance='fixture', version=digest('decoder_v2_fixture'))
        self.assertEqual(alignment['alignments'], 2)
        self.assertEqual(len(observations(pair)), 2)
        self.assertTrue(consume(plan, record, 'EV')['handled'])
        self.assertEqual(record['assets'][0]['fields']['asset_values'], raw['assets'][0][plan['field_aliases']['asset_values']])

    def test_nonliteral_evidence_and_guessed_unknown_values_cannot_be_recovered(self):
        card, raw, plan, units = fixtures.AssetGraphPairTests().fixture()
        wrong = deepcopy(raw); wrong['assets'][0]['quote'] = 'a paraphrase absent from source'
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            decode(plan, wrong, units)
        wrong = deepcopy(raw)
        cell = wrong['assets'][0][plan['field_aliases']['asset_is_personal_nonbusiness_property']]
        cell['status'] = 'unknown'
        with self.assertRaisesRegex(ValueError, 'guessed'):
            decode(plan, wrong, units)

    def test_unknown_boolean_still_blocks_a_nonconstant_native_result(self):
        card, raw, plan, units = fixtures.AssetGraphPairTests().fixture()
        cell = raw['assets'][0][plan['field_aliases']['asset_is_personal_nonbusiness_property']]
        cell.update(value=None, status='unknown')
        record, receipt = decode(plan, raw, units)
        self.assertIsNone(record['assets'][0]['fields']['asset_is_personal_nonbusiness_property']['value'])
        self.assertFalse(consume(plan, record, 'EV')['handled'])


if __name__ == '__main__':
    unittest.main()
