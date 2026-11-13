"""Joint-update software regressions; these are not legal TRAIN examples."""
import ast
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.joint_updates import apply, learn, learn_guard, candidates, replay_delta, _fragment, _walk


def literal_paths(code, value):
    return [[*path, 'fields', 'value'] for path, node in _walk(_fragment(code))
            if node['ast'] == 'Constant' and type(node['fields']['value']) is type(value)
            and node['fields']['value'] == value]


def example(actor, amount):
    before = 'answer = lookup(' + repr(actor) + ')'
    after = 'answer = min(lookup(' + repr(actor) + '), ' + repr(amount) + ')'
    return {'event_id': actor, 'source_facts': [{'predicate': 'limit_for', 'arguments': [actor, amount]}],
        'before': before, 'after': after,
        'source_slots': {'actor': {'sort': 'entity', 'positions': [[0, 0]],
            'before_paths': literal_paths(before, actor), 'after_paths': literal_paths(after, actor)},
            'cap': {'sort': 'amount', 'positions': [[0, 1]], 'after_paths': literal_paths(after, amount)}}}


SIGNATURES = {'limit_for': ['entity', 'amount'], 'active': ['entity'], 'suspended': ['entity']}


class JointUpdateTests(unittest.TestCase):
    def test_learned_macro_constructs_a_real_losslessly_encoded_candidate(self):
        update = learn([example('A', 300)], SIGNATURES)
        program = "answer = lookup('C')\nuntouched = 91\n"
        facts = [{'predicate': 'limit_for', 'arguments': ['C', 700]}]
        result = candidates([update], facts, program)
        self.assertEqual(len(result), 1)
        self.assertEqual(ast.dump(ast.parse(replay_delta(program, result[0]['raw_edit']))),
            ast.dump(ast.parse(result[0]['program'])))
        self.assertEqual(result[0]['macro_edit']['current_source_parameters'], {'actor': 'C', 'cap': 700})
        self.assertEqual(result[0]['conditional_edit_bytes'],
            min(result[0]['raw_edit_bytes'], result[0]['macro_edit_bytes']))
        self.assertEqual(candidates([], facts, program), [])
        self.assertEqual(candidates([update], [], program), [])

    def test_learned_source_and_local_code_share_current_parameters(self):
        update = learn([example('A', 300), example('B', 500)], SIGNATURES)
        program = """def helper():
    return 41
answer = lookup('C')
other = lookup('A')
"""
        result = apply(update, [{'predicate': 'limit_for', 'arguments': ['C', 700]}], program)
        self.assertEqual(result['status'], 'applied')
        env = {'lookup': lambda actor: 1000}
        exec(result['program'], env)
        self.assertEqual(env['answer'], 700)
        self.assertEqual(env['other'], 1000)
        self.assertEqual(env['helper'](), 41)
        self.assertEqual(result['source_binding'], {'actor': 'C', 'cap': 700})
        self.assertNotIn('300', result['program']);self.assertNotIn('500', result['program'])

    def test_mismatched_current_actor_or_missing_source_cannot_be_guessed(self):
        update = learn([example('A', 300)], SIGNATURES)
        code = "answer = lookup('C')"
        self.assertEqual(apply(update, [], code)['status'], 'not_applicable')
        self.assertEqual(apply(update, [{'predicate': 'limit_for', 'arguments': ['B', 700]}], code)['status'], 'not_applicable')
        changed = deepcopy(example('A', 300));changed['source_slots']['cap']['sort'] = 'entity'
        with self.assertRaisesRegex(ValueError, 'nominal types'):learn([changed], SIGNATURES)

    def test_new_legal_literals_need_occurrence_specific_source_bindings(self):
        item = example('A', 300);item['source_slots']['cap']['after_paths'] = []
        with self.assertRaisesRegex(ValueError, 'Every new legal literal'):learn([item], SIGNATURES)
        item = example('A', 300);item['source_facts'][0]['arguments'][1] = 301
        with self.assertRaisesRegex(ValueError, 'actual witnessed value'):learn([item], SIGNATURES)

    def test_unknown_source_identity_is_not_a_static_guard(self):
        item = example('A', 300);del item['source_slots']['actor']
        with self.assertRaisesRegex(ValueError, 'static query constants'):learn([item], SIGNATURES)

    def test_old_equal_value_cannot_authorize_a_new_unbound_legal_occurrence(self):
        before = 'answer = lookup("A", 300)'
        after = 'answer = min(lookup("A", 300), 300)'
        fallback_before = literal_paths(before, 300)
        fallback_after, new_cap = literal_paths(after, 300)
        item = {'event_id': 'occurrence_specific',
            'source_facts': [{'predicate': 'active', 'arguments': ['A']}],
            'before': before, 'after': after,
            'source_slots': {'actor': {'sort': 'entity', 'positions': [[0, 0]],
                'before_paths': literal_paths(before, 'A'), 'after_paths': literal_paths(after, 'A')}},
            'copies': {'fallback': {'before_paths': fallback_before, 'after_paths': [fallback_after]}}}
        with self.assertRaisesRegex(ValueError, 'Every new legal literal occurrence'):
            learn([item], SIGNATURES)
        item['source_facts'].append({'predicate': 'limit_for', 'arguments': ['A', 300]})
        item['source_slots']['actor']['positions'].append([1, 0])
        item['source_slots']['cap'] = {'sort': 'amount', 'positions': [[1, 1]], 'after_paths': [new_cap]}
        update = learn([item], SIGNATURES)
        got = apply(update, [{'predicate': 'active', 'arguments': ['B']},
            {'predicate': 'limit_for', 'arguments': ['B', 700]}], 'answer = lookup("B", 900)')
        self.assertEqual(got['status'], 'applied')
        self.assertEqual(got['source_binding']['cap'], 700)
        self.assertEqual(_fragment(got['program']), _fragment('answer = min(lookup("B", 900), 700)'))

    def test_multiple_distinct_local_edits_remain_ambiguous(self):
        item = example('A', 300)
        item['copies'] = {'lhs': {'before_paths': [['fields', 'targets']],
            'after_paths': [['fields', 'targets']]}}
        update = learn([item], SIGNATURES)
        result = apply(update, [{'predicate': 'limit_for', 'arguments': ['C', 700]}],
            "first = lookup('C')\nsecond = lookup('C')\n")
        self.assertEqual(result['status'], 'ambiguous')
        self.assertEqual(result['distinct_candidate_edits'], 2)
        self.assertNotIn('program', result)

    def test_explicit_application_evidence_learns_a_relational_guard(self):
        positive = example('A', 300);update = learn([positive], SIGNATURES)
        positive['source_facts'].append({'predicate': 'active', 'arguments': ['A']})
        negative = example('B', 500)
        negative['source_facts'].append({'predicate': 'suspended', 'arguments': ['B']})
        guarded = learn_guard(update, [positive], [negative],
            [{'predicate': 'active', 'arguments': [{'source': 'actor'}]}])
        self.assertEqual(len(guarded['guard']), 1)
        self.assertEqual(apply(guarded, negative['source_facts'], negative['before'])['status'], 'not_applicable')
        self.assertEqual(apply(guarded, [{'predicate': 'limit_for', 'arguments': ['C', 700]}],
            "answer = lookup('C')")['status'], 'not_applicable')

    def test_new_internal_locals_do_not_capture_an_existing_target_variable(self):
        before = 'if ready:\n    answer = amount'
        after = 'if ready:\n    local_cap = min(amount, 300)\n    answer = local_cap'
        item = {'event_id': 'fresh', 'source_facts': [{'predicate': 'cap', 'arguments': [300]}],
            'before': before, 'after': after, 'source_slots': {'cap': {'sort': 'amount',
                'positions': [[0, 0]], 'after_paths': literal_paths(after, 300)}}}
        update = learn([item], {'cap': ['amount']})
        program = '_u_local_0 = 99\n' + before + '\n'
        result = apply(update, [{'predicate': 'cap', 'arguments': [700]}], program)
        self.assertEqual(result['status'], 'applied')
        env = {'ready': True, 'amount': 1000};exec(result['program'], env)
        self.assertEqual(env['answer'], 700);self.assertEqual(env['_u_local_0'], 99)
        self.assertEqual(result['fresh_names'], {'local_0': '_u_local_1'})


if __name__ == '__main__':unittest.main()
