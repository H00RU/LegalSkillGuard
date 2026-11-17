"""Port graph identity, joint binding, ambiguity and native partial-loss guards.

All records here are implementation fixtures, not legal benchmark evidence.
"""
from copy import deepcopy
import json
import unittest

from legal_skill_guard.paired_interfaces import graph_interface as gi
from legal_skill_guard.paired_interfaces.asset_graph_pairs import (
    consumer_signature, pair_from_read, reference_world)
from legal_skill_guard.paired_interfaces.asset_interfaces import compile_plans, consume, frozen_skill
from legal_skill_guard.paired_interfaces.empirical_channel import learn_dictionary
from legal_skill_guard.paired_interfaces.native_channel_selection import NativeLoss
from legal_skill_guard.paired_interfaces.observed_abstention import MARKER
from legal_skill_guard.paired_interfaces.partial_native_loss import loss_interval
from legal_skill_guard.paired_interfaces.structural_channel import observations
from legal_skill_guard.skill_evolution.objects import digest


class AssetGraphPairTests(unittest.TestCase):
    def fixture(self, names=('desk', 'bike'), amounts=(20, 40)):
        text = 'Alice owns a ' + names[0] + ' worth $' + str(amounts[0]) + ' and a ' + names[1] + ' worth $' + str(amounts[1]) + '.'
        units = [{'id': 0, 'text': text}]
        cell = lambda value, status='stated': {'value': value, 'status': status}
        record = {'inventory_complete': True, 'unresolved': [], 'globals': {},
            'assets': [{'unit_id': 0, 'quote': name, 'fields': {
                'asset_descriptions': cell(name), 'asset_values': cell(amount),
                'asset_is_personal_nonbusiness_property': cell(True),
                'asset_is_wearing_apparel': cell(None, 'unknown')}} for name, amount in zip(names, amounts)]}
        card = {'source_semantic_truth_verified': True, 'native_answers_used': False,
                'source_units_sha256': digest(units), 'fixed_skill_sha256': digest(frozen_skill()),
                'public_regime': 'Illinois', 'port_record': record}
        plan = next(plan for plan in compile_plans(gi.plans(), 'Illinois') if plan['name'] == 'local_records')
        raw = {'assets': [{'unit_id': asset['unit_id'], 'quote': asset['quote'],
                          **{alias: asset['fields'][field] for field, alias in plan['field_aliases'].items()}}
                         for asset in record['assets']], 'inventory_complete': True, 'unresolved': []}
        return card, raw, plan, units

    def pair(self, card, raw, plan, units, **kwargs):
        return pair_from_read(card, raw, plan, units, source='fixture', role='development', provenance='fixture',
                              version=digest([plan['version'], 'fixture_fixed_model_decoder_alignment_profile']), **kwargs)

    def test_amount_swap_is_a_parameterized_joint_binding_error(self):
        card, raw, plan, units = self.fixture()
        field = plan['field_aliases']['asset_values']
        raw['assets'][0][field], raw['assets'][1][field] = raw['assets'][1][field], raw['assets'][0][field]
        pair, receipt = self.pair(card, raw, plan, units)
        self.assertFalse(receipt['observed_port_values_filled_from_reference'])
        self.assertEqual(receipt['alignments'], 1)
        dictionary = learn_dictionary([pair])
        self.assertTrue(any(observations(pair) & edit.images(pair.reference)
                            for edit in dictionary['edits'] if edit.before or edit.after))
        other, _, _, other_units = self.fixture(('chair', 'radio'), (31, 72))
        world, _ = reference_world(other, other_units, 'Illinois')
        images = set().union(*(edit.images(world) for edit in dictionary['edits']))
        expected = consumer_signature(world)
        self.assertTrue(expected['handled'])
        self.assertTrue(any(consumer_signature(image)['handled'] and
                            consumer_signature(image)['signature'] != expected['signature'] for image in images))

    def test_correct_final_mapping_does_not_erase_joint_source_binding_error(self):
        card, raw, plan, units = self.fixture()
        for name in ('asset_values', 'asset_descriptions'):
            field = plan['field_aliases'][name]
            raw['assets'][0][field], raw['assets'][1][field] = raw['assets'][1][field], raw['assets'][0][field]
        pair, receipt = self.pair(card, raw, plan, units)
        observed = next(iter(observations(pair)))
        self.assertNotEqual(pair.reference, observed)
        loss = NativeLoss(consumer_signature)
        self.assertEqual(loss_interval(loss, pair.reference, observed), [0., 0.])
        self.assertEqual(json.loads(consumer_signature(observed)['signature'])['EV'], consume(plan, raw, units, 'EV')['answer'])

    def test_source_alignment_keeps_ambiguity_and_does_not_use_expected_description(self):
        card, raw, plan, units = self.fixture()
        raw['assets'] = raw['assets'][:1]
        raw['assets'][0]['quote'] = units[0]['text']
        raw['inventory_complete'] = False
        pair, receipt = self.pair(card, raw, plan, units)
        self.assertEqual(receipt['alignments'], 2)
        self.assertEqual(len(observations(pair)), 2)
        limited, receipt = self.pair(card, raw, plan, units, max_alignments=1)
        self.assertFalse(receipt['production_abstention'])
        self.assertIn('analysis_alignment_unknown', receipt)
        loss = NativeLoss(consumer_signature)
        self.assertEqual(loss_interval(loss, limited.reference, next(iter(observations(limited)))), [0., 1.])

    def test_reference_unknown_stays_unknown_and_real_decoder_rejection_is_absorbing(self):
        card, raw, plan, units = self.fixture()
        card['port_record']['assets'][0]['fields']['asset_is_personal_nonbusiness_property'] = {'value': None, 'status': 'unknown'}
        world, _ = reference_world(card, units, 'Illinois')
        self.assertFalse(consumer_signature(world)['handled'])
        pair, receipt = self.pair(card, None, plan, units, production_errors=['original production rejection'])
        observed = next(iter(observations(pair)))
        self.assertIn(MARKER, dict(observed.nodes))
        self.assertEqual(loss_interval(NativeLoss(consumer_signature), pair.reference, observed), [1., 1.])

    def test_reference_context_and_source_bindings_cannot_be_reused_silently(self):
        card, raw, plan, units = self.fixture()
        with self.assertRaisesRegex(ValueError, 'binding'):
            reference_world(card, units, 'Arizona')
        stale = deepcopy(card)
        stale['source_units_sha256'] = 'changed'
        with self.assertRaisesRegex(ValueError, 'binding'):
            reference_world(stale, units, 'Illinois')


if __name__ == '__main__':
    unittest.main()
