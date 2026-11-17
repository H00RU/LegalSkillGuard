"""Native-interface invariants; constructed text is not experimental evidence."""
import unittest

from legal_skill_guard.paired_interfaces.graph_interface import decode_columns, source_units, validate
from legal_skill_guard.paired_interfaces.legal_consumers import contract, maud


def graph(nodes, relations, complete=True):
    return {'nodes': [{'id': identity, 'kind': kind, 'concept': concept}
                      for identity, kind, concept in nodes],
            'relations': [{'predicate': predicate, 'arguments': arguments, 'status': 'stated'}
                          for predicate, arguments in relations],
            'scope_complete': complete, 'unresolved': []}


class LocalLegalConsumers(unittest.TestCase):
    def test_owned_employee_and_professional_permissions_are_distinct(self):
        value = graph([('e', 'effect', 'permission'), ('a', 'group', 'receiving_party'),
                       ('b', 'group', 'own_employees'), ('x', 'event', 'disclosure'),
                       ('i', 'information', 'confidential_information')],
                      [('actor', ['e', 'a']), ('recipient', ['e', 'b']),
                       ('action', ['e', 'x']), ('information', ['e', 'i'])])
        self.assertEqual(contract(value, 'nda-5')['answer'], 'Entailment')
        self.assertEqual(contract(value, 'nda-7')['answer'], 'NotMentioned')
        value['nodes'][2]['concept'] = 'affiliate_employees'
        self.assertEqual(contract(value, 'nda-5')['answer'], 'NotMentioned')
        self.assertEqual(contract(value, 'nda-7')['answer'], 'Entailment')

    def test_unknown_actor_cannot_become_a_negative_scope_conclusion(self):
        value = graph([('e', 'effect', 'permission'), ('x', 'event', 'disclosure')], [('action', ['e', 'x'])])
        self.assertFalse(contract(value, 'nda-5')['handled'])

    def test_requested_return_is_not_automatic_termination_return(self):
        value = graph([('e', 'effect', 'obligation'), ('a', 'group', 'receiving_party'),
                       ('x', 'event', 'return'), ('c', 'condition', 'request')],
                      [('actor', ['e', 'a']), ('action', ['e', 'x']), ('trigger', ['e', 'c'])])
        self.assertEqual(contract(value, 'nda-16')['answer'], 'NotMentioned')
        value['nodes'][3]['concept'] = 'termination'
        self.assertEqual(contract(value, 'nda-16')['answer'], 'Entailment')

    def test_pandemic_exception_keeps_its_own_obligation(self):
        value = graph([('p', 'exception', 'covid_19'), ('o', 'effect', 'ordinary_course_covenant'),
                       ('n', 'effect', 'negative_interim_covenant')], [('exception_for', ['p', 'o'])])
        self.assertEqual(maud(value, 'Ordinary Course Covenant includes carve-out for Pandemic responses-Answer (Y/N)')['answer'], 'Yes')
        self.assertEqual(maud(value, 'Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)')['answer'], 'No')
        value['relations'] = []
        self.assertFalse(maud(value, 'Negative Interim Covenant includes carveout for pandemic responses-Answer (Y/N)')['handled'])

    def test_knowledge_standards_do_not_cross_definition_scopes(self):
        value = graph([('d', 'definition', 'knowledge_definition'), ('s', 'condition', 'explicit_actual_wording'),
                       ('other', 'condition', 'due_inquiry_required')], [('standard', ['d', 's'])])
        self.assertEqual(maud(value, 'Knowledge Definition-Answer')['answer'], 'Actual knowledge')
        value['nodes'].append({'id': 'd2', 'kind': 'definition', 'concept': 'knowledge_definition'})
        value['relations'].append({'predicate': 'standard', 'arguments': ['d2', 'other'], 'status': 'stated'})
        self.assertFalse(maud(value, 'Knowledge Definition-Answer')['handled'])


class GraphTransport(unittest.TestCase):
    def test_parallel_columns_cannot_silently_drop_missing_cells(self):
        with self.assertRaisesRegex(ValueError, 'Unaligned'):
            decode_columns({'scope_complete': True, 'unresolved': [],
                            'nodes': {'id': ['a'], 'kind': []}, 'relations': {'predicate': []}})

    def test_source_units_retain_all_nonwhitespace_native_material(self):
        source = {'dataset': 'ContractNLI'}
        view = {'public': {'source_text': 'Header.  Clause. Tail.', 'sentence_spans': [[9, 16]]}}
        units = source_units(source, view)
        self.assertEqual(''.join(''.join(u['text'].split()) for u in units), 'Header.Clause.Tail.')


if __name__ == '__main__':
    unittest.main()
