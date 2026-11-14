"""Impact constraints preserve valid meanings, not arbitrary old answers."""
import unittest

from legal_skill_guard.skill_evolution.repair_impact_contracts import generation_requirements, verify_effects, select_revisions


class RepairImpactContractTests(unittest.TestCase):
    def contract(self):
        return {'repairs': [{'id': 'bad_target', 'evidence_ref': 'actual_source_review'}],
            'conclusions': [{'id': 'category', 'value': 'Constructive', 'validity': 'supported',
                'evidence_ref': 'unchanged_source_inquiry_requirement'},
                {'id': 'unreviewed', 'value': 'unknown', 'validity': 'unknown'}]}

    def test_source_fix_and_preservation_both_participate_in_selection(self):
        c = self.contract()
        candidates = [
            {'id': 'small_but_harmful', 'edit_cost': 1,
                'actual_effects': {'repairs': {'bad_target': True}, 'conclusions': {'category': 'unhandled'}}},
            {'id': 'coupled', 'edit_cost': 2,
                'actual_effects': {'repairs': {'bad_target': True}, 'conclusions': {'category': 'Constructive'}}}]
        self.assertEqual(select_revisions(c, candidates)['selected'], 'coupled')
        instructions = generation_requirements(c)
        self.assertEqual(len(instructions['repair_dependencies']), 1)
        self.assertEqual([x['id'] for x in instructions['preserve_supported_conclusions']], ['category'])

    def test_counterevidence_releases_old_value_but_requires_real_recheck(self):
        c = self.contract(); c['conclusions'][0]['counterevidence'] = {'evidence_ref': 'actual_new_source_refutes_old'}
        result = {'repairs': {'bad_target': True}, 'conclusions': {'category': 'Actual'}}
        self.assertEqual(verify_effects(c, result)['status'], 'needs_recheck')
        result['rechecks'] = {'category': True}
        self.assertEqual(verify_effects(c, result)['status'], 'admissible')
        self.assertEqual(generation_requirements(c)['preserve_supported_conclusions'], [])

    def test_unchecked_correction_does_not_become_success(self):
        self.assertEqual(verify_effects(self.contract(), {'conclusions': {'category': 'Constructive'}})['status'], 'needs_recheck')
