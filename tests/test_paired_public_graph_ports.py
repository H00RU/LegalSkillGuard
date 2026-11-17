from copy import deepcopy
import itertools
import unittest

from legal_skill_guard.paired_interfaces.legal_consumers import maud
from legal_skill_guard.paired_interfaces.public_graph_ports import consumer_graph


def graph(condition_status='stated'):
    return {'nodes': [
        {'id': 'duty', 'kind': 'effect', 'concept': 'obligation'},
        {'id': 'action', 'kind': 'event', 'concept': 'ordinary_course_covenant'},
        {'id': 'exception', 'kind': 'exception', 'concept': 'unspecified'},
        {'id': 'condition', 'kind': 'condition', 'concept': 'covid_19'}],
        'relations': [
            {'predicate': 'action', 'arguments': ['duty', 'action'], 'value': None, 'status': 'stated'},
            {'predicate': 'exception_for', 'arguments': ['exception', 'duty'], 'value': None, 'status': 'stated'},
            {'predicate': 'condition', 'arguments': ['exception', 'condition'], 'value': None, 'status': condition_status}],
        'scope_complete': True, 'unresolved': []}


class PublicConsumerPortClosure(unittest.TestCase):
    def test_action_covenant_and_scoped_condition_match_explicit_consumer_ports(self):
        value = graph()
        canonical = deepcopy(value)
        canonical['nodes'][0]['concept'] = 'ordinary_course_covenant'
        canonical['nodes'][2]['concept'] = 'covid_19'
        expanded, receipt = consumer_graph(value)
        task = 'Ordinary Course Covenant-Answer'
        self.assertEqual(maud(expanded, task)['answer'], maud(canonical, task)['answer'])
        self.assertEqual(maud(expanded, task)['answer'], 'Yes')
        self.assertEqual(value, graph())
        self.assertTrue(all(n in expanded['nodes'] for n in value['nodes']))
        self.assertTrue(all(e in expanded['relations'] for e in value['relations']))
        repeated, second_receipt = consumer_graph(expanded)
        self.assertEqual(repeated, expanded)

    def test_mention_without_a_stated_exception_condition_does_not_derive_a_carveout(self):
        for status in ('negated', 'not_stated', 'unknown', 'unread'):
            value = graph(status)
            expanded, receipt = consumer_graph(value)
            self.assertFalse(any(n['concept'] == 'covid_19' and n['kind'] == 'exception'
                                 for n in expanded['nodes']))
            self.assertIn(value['relations'][2], expanded['relations'])
        value = graph();value['relations'].pop()
        expanded, receipt = consumer_graph(value)
        self.assertEqual(maud(expanded, 'Ordinary Course Covenant-Answer')['answer'], 'No')

    def test_unknown_scope_is_never_cleared_and_prohibition_is_not_an_affirmative_covenant(self):
        for complete, unresolved in itertools.product((True, False), ([], ['unresolved attachment'])):
            value = graph();value.update(scope_complete=complete, unresolved=unresolved)
            expanded, receipt = consumer_graph(value)
            self.assertEqual(expanded['scope_complete'], complete)
            self.assertEqual(expanded['unresolved'], unresolved)
            if not complete or unresolved:
                self.assertFalse(maud(expanded, 'Ordinary Course Covenant-Answer')['handled'])
        value = graph();value['nodes'][0]['concept'] = 'prohibition'
        expanded, receipt = consumer_graph(value)
        self.assertFalse(any(n['kind'] == 'effect' and n['concept'] == 'ordinary_course_covenant'
                             for n in expanded['nodes']))

    def test_a_covid_condition_is_not_moved_to_another_covenant(self):
        value = graph()
        value['nodes'].extend([{'id': 'other', 'kind': 'effect', 'concept': 'prohibition'},
                              {'id': 'other_action', 'kind': 'event', 'concept': 'negative_interim_covenant'}])
        value['relations'].append({'predicate': 'action', 'arguments': ['other', 'other_action'],
                                   'value': None, 'status': 'stated'})
        expanded, receipt = consumer_graph(value)
        self.assertEqual(maud(expanded, 'Ordinary Course Covenant-Answer')['answer'], 'Yes')
        self.assertEqual(maud(expanded, 'Negative Interim Covenant-Answer')['answer'], 'No')


if __name__ == '__main__':
    unittest.main()
