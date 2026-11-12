"""Algorithm checks use symbolic software fixtures, not additional legal data."""
from copy import deepcopy
import json
import unittest

from legal_skill_guard.skill_evolution.scoped_grammar import (
    constructors, execute, induce, parse, reject_interpretation, term_sort, scope_patterns)
from legal_skill_guard.skill_evolution.span_compiler import execute_json


def fixture():
    text = 'alpha; beta; alpha unit.'
    spec = {'rationale': 'Software fixture', 'constructors': [
        {'name': 'base', 'meaning': 'First fixture entity', 'sort': 'entity', 'arguments': []},
        {'name': 'other', 'meaning': 'Second fixture entity', 'sort': 'entity', 'arguments': []},
        {'name': 'unit', 'meaning': 'Preserve its fixture owner as an argument', 'sort': 'entity', 'arguments': ['entity']},
        {'name': 'tag', 'meaning': 'Different fixture sort', 'sort': 'marker', 'arguments': []}],
        'seeds': [{'source': 'TRAIN:fixture', 'source_span_ids': [0], 'occurrence': 0,
                   'quote': q, 'term_json': json.dumps(t)}
                  for q,t in [('alpha',['base']),('beta',['other']),('alpha unit',['unit',['base']])]],
        'decision_program': 'def apply(inputs, premises):\n    for n in premises["nodes"]:\n        if n["term"][0] == "unit":\n            return {"handled": True, "answer": "Entailment", "used_nodes": [n["id"]]}\n    return {"handled": False, "answer": None, "used_nodes": []}\n'}
    return {'source_text': text}, spec


class ScopedGrammarChecks(unittest.TestCase):
    def test_actual_factoring_changes_new_input_term_with_owner_preserved(self):
        public, spec = fixture()
        grammar = induce(spec, {'TRAIN:fixture': public})
        nodes = parse(grammar, 'beta unit')
        result = next(n for n in nodes if n['term'] == ['unit',['other']])
        self.assertTrue(any(r['induced'] for r in grammar['rules']))
        self.assertEqual((result['start'],result['end']), (0,9))
        flat = deepcopy(grammar);flat['disabled_rules'] = [r['id'] for r in grammar['rules'] if r['induced']]
        self.assertFalse(any(n['term'] == ['unit',['other']] for n in parse(flat, 'beta unit')))

    def test_nested_composition_keeps_each_owner_node(self):
        public,spec=fixture();grammar=induce(spec, {'TRAIN:fixture':public})
        self.assertIn(['unit',['unit',['other']]], [n['term'] for n in parse(grammar, 'beta unit unit')])

    def test_source_counterexample_removes_generalization_not_old_seed(self):
        public,spec=fixture();grammar=induce(spec, {'TRAIN:fixture':public})
        changed=reject_interpretation(grammar,'beta unit',start=0,end=9,sort='entity',
            term=['unit',['other']],review_origin='explicit fixture review')
        self.assertFalse(any(n['term']==['unit',['other']] for n in parse(changed,'beta unit')))
        self.assertTrue(any(n['term']==['unit',['base']] for n in parse(changed,'alpha unit')))
        self.assertFalse(changed['source_rejections'][0]['requires_new_acquisition'])
        self.assertFalse(grammar['disabled_rules'])

    def test_rejected_acquired_semantics_requires_new_acquisition(self):
        public,spec=fixture();grammar=induce(spec, {'TRAIN:fixture':public})
        changed=reject_interpretation(grammar,'alpha unit',start=0,end=10,sort='entity',
            term=['unit',['base']],review_origin='explicit fixture review')
        self.assertTrue(changed['source_rejections'][0]['requires_new_acquisition'])
        self.assertFalse(changed['source_rejections'][0]['new_legal_semantics_invented'])

    def test_incompatible_sort_is_not_substituted(self):
        public,spec=fixture();spec['seeds'].append({'source':'TRAIN:fixture','source_span_ids':[0],
            'occurrence':0,'quote':'beta','term_json':'["tag"]'})
        grammar=induce(spec, {'TRAIN:fixture':public})
        self.assertNotIn(['unit',['tag']], [n['term'] for n in parse(grammar,'beta unit')])

    def test_ambiguous_source_is_retained_and_cannot_be_core_proof(self):
        public,spec=fixture();spec['seeds'].append({'source':'TRAIN:fixture','source_span_ids':[0],
            'occurrence':0,'quote':'alpha','term_json':'["other"]'})
        grammar=induce(spec, {'TRAIN:fixture':public})
        nodes=parse(grammar,'alpha unit')
        self.assertTrue(any(n['ambiguous'] for n in nodes if n['term'][0]=='unit'))
        with self.assertRaisesRegex(ValueError,'ambiguous'):
            execute(spec,grammar,{'source_text':'alpha unit'},'nda-5','fixture')

    def test_ground_source_and_schema_types_checked(self):
        public,spec=fixture()
        bad=deepcopy(spec);bad['seeds'][0]['source']='DEV:fixture'
        with self.assertRaisesRegex(ValueError,'Non-TRAIN'):
            induce(bad,{'TRAIN:fixture':public})
        bad=deepcopy(spec);bad['seeds'][0]['quote']='not supplied'
        with self.assertRaises(ValueError):induce(bad,{'TRAIN:fixture':public})
        with self.assertRaisesRegex(ValueError,'sort mismatch'):
            term_sort(['unit',['tag']],constructors(spec))
        with self.assertRaisesRegex(ValueError,'Native answer'):
            term_sort('Entailment',constructors(spec))

    def test_generation_execution_reports_used_induced_rules(self):
        public,spec=fixture();grammar=induce(spec, {'TRAIN:fixture':public})
        result=execute(spec,grammar,{'source_text':'beta unit'},'nda-5','fixture')
        self.assertEqual(result['value']['answer'],'Entailment')
        self.assertTrue(result['used_induced_rule_ids'])
        self.assertEqual(result['nodes'][result['value']['used_nodes'][0]]['support_ids'],[0])

    def test_no_source_match_keeps_answer_unknown(self):
        public,spec=fixture();grammar=induce(spec, {'TRAIN:fixture':public})
        result=execute(spec,grammar,{'source_text':'unseen material'},'nda-5','fixture')
        self.assertFalse(result['value']['handled']);self.assertIsNone(result['value']['answer'])

    def test_context_contrasts_induce_shared_inherited_bindings(self):
        public,spec=fixture();spec['constructors'].append({'name':'duo','meaning':'Fixture pair',
            'sort':'entity','arguments':['entity','entity']})
        pairs=[{'source':('token',),'term':['duo',['unit',[name]],['unit',[name]]],
                'sort':'entity','seed':name} for name in ('base','other')]
        found=scope_patterns(pairs,constructors(spec))
        self.assertEqual(len(found),1);p=found[0]
        self.assertEqual(p['inherited_sorts'],['entity'])
        self.assertEqual(p['template'],['duo',['unit',{'$scope':0}],['unit',{'$scope':0}]])
        code='def apply(inputs, premises):\n    return bind_scope(inputs["template"], inputs["bindings"])\n'
        self.assertEqual(execute_json(code,{'template':p['template'],'bindings':[['other']]},{}),
            ['duo',['unit',['other']],['unit',['other']]])
        with self.assertRaises(ValueError):execute_json(code,{'template':p['template'],'bindings':[]},{})

    def test_unique_parent_alignment_supplies_new_context_not_new_meaning(self):
        public,spec=fixture();spec['constructors'].append({'name':'duo','meaning':'Fixture pair',
            'sort':'entity','arguments':['entity','entity']})
        pairs=[{'source':('unit',),'term':['unit',['base']],'sort':'entity','seed':'old'},
            {'source':('beta','unit'),'term':['duo',['other'],['unit',['other']]],'sort':'entity','seed':'new'}]
        found=scope_patterns(pairs,constructors(spec))
        p=next(p for p in found if p['source_tokens']==['unit'])
        self.assertEqual(p['template'],['unit',{'$scope':0}])
        self.assertEqual(p['observed_bindings'],[[['base']],[['other']]])


if __name__=='__main__':unittest.main()
