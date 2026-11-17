import unittest

from legal_skill_guard.paired_interfaces.consumer_graph_contract import consumer_graph
from legal_skill_guard.paired_interfaces.legal_consumers import contract, maud
from tests.test_paired_graph_interface import graph


class ConsumerGraphContracts(unittest.TestCase):
    def test_definition_local_inquiry_condition_populates_the_existing_standard_port(self):
        value = graph([('d', 'definition', 'knowledge_definition'),
                       ('a', 'information', 'explicit_actual_wording'),
                       ('q', 'condition', 'reasonable_inquiry_required')],
                      [('object', ['d', 'a']), ('condition', ['d', 'q'])])
        out, receipt = consumer_graph(value)
        self.assertEqual(maud(out, 'Knowledge Definition-Answer')['answer'], 'Constructive knowledge')
        self.assertEqual(len(value['relations']), 2)
        self.assertEqual(len(receipt['derived_ports']), 2)

    def test_an_unattached_inquiry_tag_does_not_change_a_definition(self):
        value = graph([('d', 'definition', 'knowledge_definition'),
                       ('a', 'information', 'explicit_actual_wording'),
                       ('q', 'condition', 'reasonable_inquiry_required')], [('object', ['d', 'a'])])
        out, receipt = consumer_graph(value)
        self.assertEqual(maud(out, 'Knowledge Definition-Answer')['answer'], 'Actual knowledge')

    def test_receiving_party_employee_permission_can_follow_explicit_group_membership(self):
        value = graph([('e', 'effect', 'permission'), ('p', 'group', 'receiving_party'),
                       ('g', 'group', 'unspecified'), ('m', 'group', 'own_employees'),
                       ('a', 'event', 'disclosure'), ('i', 'information', 'confidential_information')],
                      [('actor', ['e', 'p']), ('recipient', ['e', 'g']), ('member_of', ['m', 'g']),
                       ('action', ['e', 'a']), ('information', ['e', 'i'])])
        out, receipt = consumer_graph(value)
        self.assertEqual(contract(out, 'nda-5')['answer'], 'Entailment')
        self.assertEqual(contract(out, 'nda-7')['answer'], 'NotMentioned')
        value['unresolved'] = ['recipient definition incomplete']
        self.assertFalse(contract(consumer_graph(value)[0], 'nda-5')['handled'])


if __name__ == '__main__':
    unittest.main()
