"""Joint component integration regressions, not additional legal examples."""
import ast
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.joint_updates import _fragment, _walk
from legal_skill_guard.skill_evolution.joint_library_updates import (
    SOURCE_VIEW, apply_bundle, component_program, learn_bundle)
from legal_skill_guard.skill_evolution.open_acquisition import update_candidates
from legal_skill_guard.skill_evolution.source_observations import signatures


def paths(code, value):
    return [[*p, 'fields', 'value'] for p, n in _walk(_fragment(code))
            if n['ast'] == 'Constant' and type(n['fields']['value']) is type(value)
            and n['fields']['value'] == value]


SIG = {'limit_for': ['entity', 'amount']}
API_CONSTANTS = {'planner_program': ['value', 0], 'composition_program': [0]}


def example():
    first = 'return inputs.get("value", 0)'
    second = 'return inputs.get("A", 0)'
    edits = []
    for component, before in [('planner_program', first), ('composition_program', second)]:
        after = 'return min(' + before[len('return '):] + ', 300)'
        edits.append({'component': component, 'before': before, 'after': after,
            'source_slots': {'actor': {'sort': 'entity', 'positions': [[0, 0]],
                'before_paths': paths(before, 'A'), 'after_paths': paths(after, 'A')},
                'cap': {'sort': 'amount', 'positions': [[0, 1]], 'after_paths': paths(after, 300)}}})
    return {'event_id': 'actual_fixture_edit',
            'source_facts': [{'predicate': 'limit_for', 'arguments': ['A', 300]}], 'edits': edits}


def observation(facts):
    return {'visible_inputs_sha256': 'software_fixture_only', 'context': {'facts': facts}}


class JointLibraryUpdateTests(unittest.TestCase):
    def test_source_program_edit_enters_the_same_candidate_path_and_invalidates_fit(self):
        before='def apply(inputs,premises):\n    return {"statements":[],"complete":False,"unresolved":["Alpha?"]}\n'
        after=before.replace('Alpha?','Beta?')
        item={'event_id':'source_program_fixture','source_facts':[{'predicate':'revision','arguments':['Alpha?','Beta?']}],
            'edits':[{'component':'source_program','before':before,'after':after,
                'source_slots':{role:{'sort':'text','positions':[[0,i]],
                    'before_paths':paths(before,value),'after_paths':paths(after,value)}
                    for i,(role,value)in enumerate([('old','Alpha?'),('new','Beta?')])}}]}
        bundle=learn_bundle([item],{'revision':['text','text']})
        library={'source_program':before,'operations':[],'planner_program':'def apply(inputs,premises):\n    return {"queries":[]}\n',
            'spec':{'constructors':[]},'language':{'signatures':signatures(),'constants':{},'rules':[]},
            'renderers':[],'selected_rule_ids':[],'fit':{'old':True}}
        result=update_candidates(library,[bundle],observation(item['source_facts']),{})
        self.assertEqual(len(result['candidates']),1)
        target=result['candidates'][0]['library']
        self.assertEqual(ast.dump(ast.parse(target['source_program'])),ast.dump(ast.parse(after)))
        self.assertIsNone(target['selected_rule_ids']);self.assertNotIn('fit',target)
        self.assertEqual(library['source_program'],before)

    def test_shared_binding_join_precedes_equal_program_deduplication(self):
        bundle = learn_bundle([example()], SIG, program_constants=API_CONSTANTS)
        library = {'planner_program': 'def apply(inputs, premises):\n    return inputs.get("value", 0)\n',
                   'composition_program': 'def apply(inputs, premises):\n    return inputs.get("B", 0)\n'}
        facts = [{'predicate': 'limit_for', 'arguments': [actor, 700]} for actor in ['A', 'B']]
        result = apply_bundle(bundle, observation(facts), library)
        self.assertEqual(result['status'], 'applied')
        self.assertEqual(result['source_bindings'], [{'actor': 'B', 'cap': 700}])
        for component in ('planner_program', 'composition_program'):
            env = {};exec(result['library'][component], env)
            self.assertEqual(env['apply']({'value': 1000, 'B': 900}, {}), 700)
        self.assertNotIn('300', repr(result['library']))

    def test_no_partial_install_or_missing_value_fallback(self):
        bundle = learn_bundle([example()], SIG, program_constants=API_CONSTANTS)
        library = {'planner_program': 'def apply(inputs, premises):\n    return inputs.get("value", 0)\n',
                   'composition_program': 'def apply(inputs, premises):\n    return inputs.get("C", 0)\n'}
        original = deepcopy(library)
        got = apply_bundle(bundle, observation([{'predicate': 'limit_for', 'arguments': ['B', 700]}]), library)
        self.assertEqual(got['status'], 'not_applicable');self.assertNotIn('library', got)
        self.assertEqual(library, original)
        bundle['source_view'] = 'unexecuted_ideal_output'
        with self.assertRaisesRegex(ValueError, 'actual observations'):
            apply_bundle(bundle, observation([]), library)

    def test_distinct_joint_edits_remain_ambiguous(self):
        bundle = learn_bundle([example()], SIG, program_constants=API_CONSTANTS)
        library = {'planner_program': 'def apply(inputs, premises):\n    return inputs.get("value", 0)\n',
                   'composition_program': 'def apply(inputs, premises):\n    return inputs.get("B", 0)\n'}
        facts = [{'predicate': 'limit_for', 'arguments': ['B', n]} for n in [700, 800]]
        result = apply_bundle(bundle, observation(facts), library)
        self.assertEqual(result['status'], 'ambiguous');self.assertEqual(result['distinct_candidate_edits'], 2)
        self.assertNotIn('library', result)

    def test_actual_acquisition_entry_builds_structured_edit_and_invalidates_old_fit(self):
        library = {'operations': [{'name': 'meaning', 'question': 'Alpha?',
            'choices': [{'name': 'one', 'meaning': 'First meaning'}], 'examples': []}],
            'planner_program': 'def apply(inputs, premises):\n    return {"queries": []}\n',
            'spec': {'constructors': [{'name': 'norm', 'sort': 'Norm', 'arguments': [], 'meaning': 'Fixture'}]},
            'language': {'signatures': {**signatures(), 'keep_root': {'arguments': ['term'], 'kind': 'output'}},
                         'constants': {}, 'rules': []}, 'renderers': [],
            'selected_rule_ids': [], 'fit': {'old': True}}
        target = deepcopy(library);target['operations'][0]['question'] = 'Beta?'
        before, after = [component_program(v, 'operations') for v in [library, target]]
        item = {'event_id': 'fixture_meaning_repair',
            'source_facts': [{'predicate': 'revised_question', 'arguments': ['Alpha?', 'Beta?']}],
            'edits': [{'component': 'operations', 'before': before, 'after': after,
                'source_slots': {role: {'sort': 'text', 'positions': [[0, index]],
                    'before_paths': paths(before, value), 'after_paths': paths(after, value)}
                    for index, (role, value) in enumerate([('old_question', 'Alpha?'), ('new_question', 'Beta?')])}}]}
        bundle = learn_bundle([item], {'revised_question': ['text', 'text']})
        obs = observation(item['source_facts'])
        got = update_candidates(library, [bundle], obs, {})
        self.assertTrue(got['U_enabled']);self.assertEqual(len(got['candidates']), 1)
        candidate = got['candidates'][0]
        self.assertEqual(candidate['library']['operations'], target['operations'])
        self.assertIsNone(candidate['library']['selected_rule_ids'])
        self.assertNotIn('fit', candidate['library'])
        self.assertFalse(candidate['new_or_changed_readings_certified'])
        self.assertEqual(candidate['conditional_edit_bytes'], min(candidate['raw_edit_bytes'], candidate['macro_edit_bytes']))
        disabled = update_candidates(library, [bundle], obs, {}, use_updates=False)
        self.assertEqual(disabled['candidates'], []);self.assertFalse(disabled['U_enabled'])
        self.assertEqual(library['operations'][0]['question'], 'Alpha?')


if __name__ == '__main__':unittest.main()
