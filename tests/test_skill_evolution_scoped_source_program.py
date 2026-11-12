"""The compiled source path cannot turn open scope attributes into facts."""
import unittest

from legal_skill_guard.skill_evolution.scoped_grammar import induce
from legal_skill_guard.skill_evolution.scoped_source_program import run_source
from test_skill_evolution_scoped_grammar import fixture


class ScopedSourceProgramChecks(unittest.TestCase):
    def test_current_context_binds_scope_without_hypothesis_evidence(self):
        public, spec = fixture()
        grammar = induce(spec, {'TRAIN:fixture': public})
        grammar['scope_patterns'] = [{'id': 'fixture-scope', 'source_tokens': ['unit'],
            'sort': 'entity', 'template': ['unit', {'$scope': 0}],
            'inherited_sorts': ['entity'], 'observed_bindings': [[['base']], [['other']]],
            'requires_current_source_binding': True}]
        source = {'views': [{'public': {'source_text': 'beta unit', 'question': 'alpha unit'}}]}
        program = '''def apply(inputs, premises):
    s = premises['scope_nodes'][0]
    owner = [n['term'] for n in premises['grammar_nodes'] if n['term'] == ['other']]
    if not owner:
        return {'statements': [], 'complete': False, 'unresolved': ['missing owner']}
    term = bind_scope(s['template'], [owner[0]])
    return {'statements': [{'term': term, 'support_ids': [0]}], 'complete': True, 'unresolved': []}
'''
        result, event = run_source(program, spec, grammar, source)
        self.assertEqual(result['nodes'][0]['term'], ['unit', ['other']])
        self.assertEqual(event['new_physical_calls'], 0)
        self.assertFalse(result['nodes'][0]['source_semantics_verified'])
        source['views'][0]['public']['source_text'] = 'unit'
        result, _ = run_source(program, spec, grammar, source)
        self.assertFalse(result['complete'])
        self.assertEqual(result['nodes'], [])

    def test_unbound_attribute_and_absent_witness_fail(self):
        public, spec = fixture(); grammar = induce(spec, {'TRAIN:fixture': public})
        source = {'views': [{'public': public}]}
        for term, ids in (("['unit', {'$scope': 0}]", '[0]'), ("['base']", '[999]')):
            program = "def apply(inputs, premises):\n    return {'statements':[{'term':"+term+", 'support_ids':"+ids+"}], 'complete':True, 'unresolved':[]}\n"
            with self.assertRaises(ValueError):
                run_source(program, spec, grammar, source)


if __name__ == '__main__':
    unittest.main()
