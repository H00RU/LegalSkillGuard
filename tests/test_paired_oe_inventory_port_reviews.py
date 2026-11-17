"""Source/view boundaries for the original remaining OE port references."""
from collections import Counter
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments import two_method_oe_inventory_port_reviews as reviews
from experiments.two_method_annotate import inputs
from experiments.two_method_graph_corpus import ROOT, read
from legal_skill_guard.paired_interfaces.asset_interfaces import context_from_public
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, FrozenTeacher
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger


class OEInventoryReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.public={s['key']:s for s in read(ROOT/'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        cls.locks=read(reviews.LOCK_PATH)

    def example(self,prefix,view):
        source=next(r['source'] for r in self.locks if r['source'].split(':')[1].startswith(prefix))
        s=self.public[source];task,mapping=inputs(s)
        units=next(v['source_units'] for v in task['views'] if v['view_id']==view)
        native=next(v for v in s['views'] if mapping[v['id']]==view)
        context=context_from_public(native['public'])
        return source,units,context,reviews.reviewed_card(source,view,units,context)

    def asset(self,card,part):
        return next(a for a in card['port_record']['assets'] if part in a['quote'])

    def value(self,card,part,field):return self.asset(card,part)['fields'][field]['value']

    def test_all38_literal_views_keep19_original_mother_roles(self):
        self.assertEqual(len(self.locks),38)
        roles={r['source']:r['role'] for r in self.locks}
        self.assertEqual(Counter(roles.values()),Counter(development=6,calibration=7,reference_only=6))
        for row in self.locks:
            _,units,_,card=self.example(row['source'].split(':')[1][:8],row['view'])
            self.assertFalse(card['complete_native_case_gold_claimed'])
            self.assertEqual(card['role'],row['role'])
            for asset in card['port_record']['assets']:
                unit=next(u for u in units if u['id']==asset['unit_id'])
                self.assertEqual(unit['text'].count(asset['quote']),1)
                self.assertIn(asset['amount_evidence']['quote'],unit['text'])

    def test_source_view_drift_and_wrong_public_regime_cannot_reuse_review(self):
        source,units,context,_=self.example('1bb6328a','v0');drift=deepcopy(units);drift[1]['text']+=' '
        with self.assertRaises(ValueError):reviews.reviewed_card(source,'v0',drift,context)
        with self.assertRaises(ValueError):reviews.reviewed_card(source,'v1',units,context)
        with self.assertRaises(ValueError):reviews.reviewed_card(source,'v0',units,{**context,'governing_regime':'Illinois'})
        with self.assertRaises(ValueError):reviews.reviewed_card(source,'v0',units,{**context,'public_task_assumptions':[]})

    def test_possession_disclosure_and_estate_inventory_do_not_supply_owner(self):
        for prefix,part in [('0d6a5c5f','decorative bowl'),('0d6a5c5f','custom dress shirt')]:
            v0=self.example(prefix,'v0')[3];v1=self.example(prefix,'v1')[3]
            self.assertTrue(self.value(v0,part,reviews.PERSONAL))
            self.assertIsNone(self.value(v1,part,reviews.PERSONAL))
        v0=self.example('1bb6328a','v0')[3];v1=self.example('1bb6328a','v1')[3]
        self.assertTrue(all(a['fields'][reviews.PERSONAL]['value'] is None for a in v0['port_record']['assets']))
        self.assertTrue(all(a['fields'][reviews.PERSONAL]['value'] is True for a in v1['port_record']['assets']))

    def test_claimed_ownership_and_has_remain_unknown_in_own_view(self):
        for prefix,part,unknown_view in [('1ca28cd2','accent chair','v1'),('cdf5d6eb','pet crate','v1'),
                                        ('d2908306','African grey parrot','v0'),('dbbe6b3d','electric clothes dryer','v0'),
                                        ('fbed840c','oversized crystal chandelier','v0')]:
            card=self.example(prefix,unknown_view)[3]
            self.assertIsNone(self.value(card,part,reviews.PERSONAL))
            self.assertEqual(self.asset(card,part)['ownership_evidence']['status'],'unknown')

    def test_explicit_business_use_overrides_personal_assumption(self):
        for view in ('v0','v1'):
            card=self.example('ae1e4bdb',view)[3]
            for part in ('digital camera','massage table'):
                self.assertFalse(self.value(card,part,reviews.FEDERAL))
                self.assertFalse(self.value(card,part,reviews.TANGIBLE))
            self.assertTrue(self.value(card,'Siberian husky',reviews.FEDERAL))
            card=self.example('fbed840c',view)[3]
            self.assertFalse(self.value(card,'circular saw',reviews.PERSONAL))
            self.assertTrue(self.value(card,'concert-grade oboe',reviews.PERSONAL))
            # A home-office device is not explicitly stated to be business use.
            self.assertTrue(self.value(self.example('b5dc2ec9',view)[3],'home office webcam',reviews.PERSONAL))

    def test_real_estate_is_not_a_movable_household_or_personal_port(self):
        for view in ('v0','v1'):
            card=self.example('5a573dfd',view)[3]
            self.assertFalse(self.value(card,'condominium',reviews.FEDERAL))
            self.assertFalse(self.value(card,'condominium',reviews.TANGIBLE))
            card=self.example('48b137c1',view)[3]
            self.assertFalse(self.value(card,'primary home',reviews.PERSONAL))
            self.assertFalse(self.value(card,'primary home',reviews.TANGIBLE))
            self.assertTrue(self.value(card,'fleece-lined vest',reviews.APPAREL))
        self.assertIsNone(self.value(self.example('48b137c1','v0')[3],'fleece-lined vest',reviews.PERSONAL))

    def test_Arizona_jewelry_ambiguity_and_separate_instrument_vehicle_categories(self):
        for view in ('v0','v1'):
            card=self.example('1fcfad02',view)[3]
            self.assertIsNone(self.value(card,'earrings',reviews.AZ_APPAREL))
            self.assertFalse(self.value(card,'earrings',reviews.AZ_HOME))
            self.assertTrue(self.value(card,'air conditioning',reviews.AZ_HOME))
            card=self.example('d68639e8',view)[3]
            for part in ('Corvette','acoustic bass'):
                self.assertFalse(self.value(card,part,reviews.AZ_HOME))
                self.assertFalse(self.value(card,part,reviews.AZ_APPAREL))

    def test_required_debtor_count_and_distinct_amount_asset_bindings(self):
        for prefix,count,part,amount in [('74dbd97c',2,'white wool suit',1300),('1bb6328a',1,'countertop ice maker',130),
                                        ('ae1e4bdb',2,'massage table',1025),('5a573dfd',2,'condominium',112850)]:
            for view in ('v0','v1'):
                card=self.example(prefix,view)[3]
                self.assertEqual(card['port_record']['globals']['number_of_debtors']['value'],count)
                self.assertEqual(self.value(card,part,'asset_values'),amount)

    def test_unused_ports_are_unread_and_medical_description_is_preserved(self):
        card=self.example('3ab6950c','v0')[3]
        asset=self.asset(card,'hospital bed')
        self.assertIn('required by doctor for treatment',asset['quote'])
        self.assertTrue(asset['fields'][reviews.FEDERAL]['value'])
        self.assertEqual(asset['fields'][reviews.PERSONAL],{'value':None,'status':'unread'})

    def test_cumulative138_manifest_uses_no_clients_grades_or_F_outputs(self):
        original=Path.read_text
        def safe(path,*args,**kwargs):
            if path.name=='grading.json' or path.name=='construction_and_grading_only.json':
                self.fail('annotation opened native grading/construction')
            return original(path,*args,**kwargs)
        with (patch.object(Path,'read_text',safe),
              patch.object(FrozenExecutor,'__init__',side_effect=AssertionError('executor')),
              patch.object(FrozenTeacher,'__init__',side_effect=AssertionError('teacher')),
              patch.object(EvolutionLedger,'__init__',side_effect=AssertionError('ledger')),
              patch('legal_skill_guard.paired_interfaces.asset_graph_pairs.consumer_signature',side_effect=AssertionError('F output')),
              patch('legal_skill_guard.paired_interfaces.native_graph_consumers.partial_skill',side_effect=AssertionError('F output'))):
            out,manifest=reviews.prepare()
        self.assertEqual(len(manifest['reviews']),138)
        self.assertEqual(manifest['previous_extra_reviews_retained'],100)
        self.assertTrue(manifest['heldout_exposure_not_repaired_by_source_review'])
        self.assertIsNone(manifest['interactive_root_annotation_cost_usd'])


if __name__=='__main__':unittest.main()
