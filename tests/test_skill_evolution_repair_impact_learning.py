"""Impact learning must distinguish checking a value from changing it."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.repair_impact_learning import learn, predict, generation_scope


class RepairImpactLearningTests(unittest.TestCase):
    def event(self):
        evidence = ['software_fixture_not_research_evidence']
        return {'id': 'training', 'parent_revision': 'one_actual_update',
            'graph': {'nodes': [
                {'id': 'condition', 'kind': 'source_constraint', 'role': 'condition', 'evidence_refs': evidence},
                {'id': 'affected', 'kind': 'legal_field', 'role': 'condition', 'evidence_refs': evidence,
                    'current_validity': {'status': 'supported', 'value': 'old_valid', 'evidence_ref': 'current_source'}},
                {'id': 'stable', 'kind': 'legal_field', 'role': 'actor', 'evidence_refs': evidence,
                    'current_validity': {'status': 'supported', 'value': 'actor', 'evidence_ref': 'current_source'}},
                {'id': 'unreviewed', 'kind': 'legal_field', 'role': 'condition', 'evidence_refs': evidence}],
                'edges': [{'from': 'condition', 'to': 'affected', 'relation': 'qualifies', 'evidence_refs': evidence}],
                'seeds': ['condition']},
            'judgments': [
                {'node': 'affected', 'effect': 'recheck', 'holds': True, 'evidence_refs': evidence},
                {'node': 'stable', 'effect': 'recheck', 'holds': False, 'evidence_refs': evidence},
                {'node': 'affected', 'effect': 'preserve', 'holds': True, 'evidence_refs': evidence},
                {'node': 'stable', 'effect': 'preserve', 'holds': False, 'evidence_refs': evidence}]}

    def test_node_and_source_id_changes_do_not_change_prediction(self):
        original = self.event(); model = learn([original]); other = deepcopy(original)
        other['id'] = 'another_source'; other['parent_revision'] = 'another_update'
        names = {n['id']: 'different_' + n['id'] for n in other['graph']['nodes']}
        for node in other['graph']['nodes']:
            node['id'] = names[node['id']]
        for edge in other['graph']['edges']:
            edge.update({'from': names[edge['from']], 'to': names[edge['to']]})
        other['graph']['seeds'] = [names[s] for s in other['graph']['seeds']]
        other['judgments'] = []
        a = {r['node']: r['effects'] for r in predict(model, original)['nodes']}
        b = {r['node']: r['effects'] for r in predict(model, other)['nodes']}
        self.assertEqual({names[k]: v for k, v in a.items()}, b)

    def test_recheck_and_preserve_can_both_be_required(self):
        e = self.event(); result = generation_scope(learn([e]), e)
        self.assertIn('affected', [x['node'] for x in result['recheck']])
        self.assertIn('affected', [x['node'] for x in result['preserve_supported']])
        self.assertEqual(result['must_resolve'], [])

    def test_unknown_and_unseen_relations_do_not_become_negative_feedback(self):
        e = self.event(); model = learn([e])
        self.assertEqual(len(model['feedback']), 4)
        self.assertEqual(model['policies']['must_change']['status'], 'not_identified')
        new = deepcopy(e)
        new['graph']['edges'][0]['relation'] = 'new_unreviewed_dependency'
        affected = next(r for r in predict(model, new)['nodes'] if r['node'] == 'affected')
        self.assertEqual(affected['status'], 'unseen_structure')
        self.assertEqual(affected['effects'], [])

    def test_new_counterevidence_releases_preservation_but_requires_recheck(self):
        e = self.event(); model = learn([e])
        e['graph']['nodes'][1]['counterevidence'] = {'evidence_ref': 'new_actual_source_review'}
        result = generation_scope(model, e)
        self.assertNotIn('affected', [x['node'] for x in result['preserve_supported']])
        self.assertIn('affected', [x['node'] for x in result['recheck']])

    def test_predicted_preservation_requires_current_source_validity(self):
        e = self.event(); model = learn([e])
        del e['graph']['nodes'][1]['current_validity']
        result = generation_scope(model, e)
        self.assertEqual(result['preserve_supported'], [])
        self.assertIn('current_validity_not_established', [x['reason'] for x in result['unresolved']])

    def test_same_legal_scope_needs_current_program_shape_to_locate_wrong_shadow(self):
        e = self.event(); e['graph']['nodes'] = e['graph']['nodes'][:3]
        a, b = e['graph']['nodes'][1:]
        b['role'] = a['role']
        e['graph']['edges'].append({**deepcopy(e['graph']['edges'][0]), 'to': 'stable'})
        e['judgments'] = [
            {'node': 'affected', 'effect': 'must_change', 'holds': True, 'evidence_refs': ['actual_shape_fixture']},
            {'node': 'stable', 'effect': 'must_change', 'holds': False, 'evidence_refs': ['actual_shape_fixture']}]
        self.assertEqual(learn([e])['policies']['must_change']['status'], 'not_identified')
        a['program_operator'] = 'no_exceptions'; b['program_operator'] = 'add_exception'
        model = learn([e]); rows = {r['node']: r for r in predict(model, e)['nodes']}
        self.assertIn('must_change', rows['affected']['effects'])
        self.assertNotIn('must_change', rows['stable']['effects'])
