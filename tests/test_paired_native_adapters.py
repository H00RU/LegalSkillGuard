import hashlib
import unittest

from legal_skill_guard.paired_interfaces.native_adapters import LIBRARY, airline_inputs, run_airline


class NativeAdapterTests(unittest.TestCase):
    def graph(self):
        text = 'Business flying from Philadelphia to New York. Bag A: 30 x 20 x 10 inches, 51 lbs. Ticket $100.'
        graph = {'nodes': [
            {'id': 'cabin', 'kind': 'information', 'concept': 'Business', 'unit_id': 0, 'name': 'Business', 'quote': 'Business'},
            {'id': 'bag', 'kind': 'bag', 'concept': 'checked_bag', 'unit_id': 0, 'name': 'Bag A',
             'quote': 'Bag A: 30 x 20 x 10 inches, 51 lbs.'}],
            'relations': [], 'scope_complete': True, 'unresolved': []}
        for predicate, value in [('length', 30), ('width', 20), ('height', 10), ('weight', 51)]:
            graph['relations'].append({'predicate': predicate, 'arguments': ['bag'], 'value': value,
                'status': 'stated', 'unit_id': 0, 'quote': graph['nodes'][1]['quote']})
        graph['relations'] += [
            {'predicate': 'route', 'arguments': [], 'value': None, 'status': 'stated', 'unit_id': 0,
             'quote': 'flying from Philadelphia to New York'},
            {'predicate': 'ticket_price', 'arguments': [], 'value': 100, 'status': 'stated', 'unit_id': 0,
             'quote': 'Ticket $100'}]
        return graph, [{'id': 0, 'start': 0, 'end': len(text), 'text': text}]

    def test_actual_preserved_program_executes_and_residual_representative_preserves_it(self):
        graph, units = self.graph()
        before = run_airline(graph, units, hashlib.sha256(LIBRARY.read_bytes()).hexdigest())
        self.assertTrue(before['learned_native_main_path_executed'])
        self.assertEqual(before['answer'], 100)
        next(e for e in graph['relations'] if e['predicate'] == 'weight')['value'] = 53
        after = run_airline(graph, units, hashlib.sha256(LIBRARY.read_bytes()).hexdigest())
        self.assertEqual(before['answer'], after['answer'])

    def test_an_unread_measurement_does_not_get_a_native_answer(self):
        graph, units = self.graph()
        next(e for e in graph['relations'] if e['predicate'] == 'weight').update(status='unread', value=None)
        self.assertFalse(airline_inputs(graph, units)['handled'])

    def test_an_excluded_south_america_route_does_not_enter_the_else_branch(self):
        graph, units = self.graph()
        next(e for e in graph['relations'] if e['predicate'] == 'route')['quote'] = 'flying from Orlando to Lima'
        self.assertFalse(airline_inputs(graph, units)['handled'])


if __name__ == '__main__':
    unittest.main()
