"""Constraint semantics and execution, with synthetic software fixtures only."""
from copy import deepcopy
import unittest

from legal_skill_guard.skill_evolution.semantic_learning import (
    assess_candidate, check_binding, compile_bundle, contract, review_binding,
    producing_calls, run_bundle, update_frontier)
from legal_skill_guard.skill_evolution.span_compiler import execute_json


def fixture():
    source = {'key': 'TRAIN:software_fixture', 'views': [{'id': 'nda-5', 'public': {
        'question': 'Fixture query', 'source_text': 'alpha beta', 'sentence_spans': [[0, 10]]}}]}
    spec = {'kind': 'relational_rule', 'rationale': 'Software fixture, no legal rule',
            'frames': [{'name': 'link', 'meaning': 'Fixture link', 'fields': [
                {'name': 'owner', 'meaning': 'Fixture owner', 'type': 'string', 'domain': ['left', 'right']},
                {'name': 'members', 'meaning': 'Fixture set', 'type': 'array', 'domain': ['a', 'b']}]}],
            'source_examples': [], 'policy_text': None,
            'procedure': 'def apply(inputs, premises):\n    return {"handled": False, "answer": "NotMentioned", "used_records": []}\n'}
    code = 'def apply(inputs, premises):\n    return {"link": [{"support_ids": [0], "fields": {"owner": {"value": "left", "support_ids": [0]}, "members": {"value": ["a", "b"], "support_ids": [0]}}}]}\n'
    return source, {'spec': spec, 'source_program': code}


class SemanticLearningChecks(unittest.TestCase):
    def observation(self, source, bundle, **changes):
        args = dict(kind='link', field='owner', value='left', support_ids=[0],
                    polarity='rejected', reason='Explicit fixture review', review_origin='fixture review v1')
        args.update(changes)
        return review_binding(source, bundle['spec'], **args)

    def test_joint_bundle_executes_without_native_supervision(self):
        source, bundle = fixture()
        compile_bundle(bundle, {})
        run = run_bundle(bundle, source)
        self.assertEqual(run['records'][0]['values']['owner'], 'left')
        self.assertFalse(run['views']['nda-5']['value']['handled'])
        self.assertEqual(run['contract'], contract(bundle['spec']))

    def test_correct_native_feedback_cannot_override_rejected_binding(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        assessment = assess_candidate(bundle, [source], [o], native_feedback={'correct': True})
        self.assertEqual(assessment['source_violations'], 1)
        state = update_frontier({}, bundle, assessment, acquisition_receipt='actual fixture receipt')
        self.assertFalse(state['feasible_versions'])
        self.assertFalse(state['core_learning_success_claimed'])

    def test_null_does_not_become_negative_or_supported(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        bundle['source_program'] = bundle['source_program'].replace('"value": "left"', '"value": None')
        a = assess_candidate(bundle, [source], [o])
        self.assertEqual(a['source_open'], 1)
        self.assertEqual(a['source_supported'], 0)

    def test_removing_rejected_claim_does_not_verify_replacement(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        bundle['source_program'] = 'def apply(inputs, premises):\n    return {"link": []}\n'
        a = assess_candidate(bundle, [source], [o])
        self.assertEqual(a['source_rejections_not_reproduced'], 1)
        self.assertEqual(a['source_supported'], 0)
        self.assertFalse(a['complete_source_semantics_verified'])

    def test_supported_binding_is_only_local_support(self):
        source, bundle = fixture()
        o = self.observation(source, bundle, polarity='supported')
        a = assess_candidate(bundle, [source], [o])
        self.assertEqual(a['source_supported'], 1)
        self.assertFalse(a['complete_source_semantics_verified'])

    def test_array_set_order_does_not_change_review_meaning(self):
        source, bundle = fixture()
        o = self.observation(source, bundle, field='members', value=['b', 'a'], polarity='supported')
        self.assertEqual(assess_candidate(bundle, [source], [o])['source_supported'], 1)

    def test_changed_relation_meaning_cannot_discard_old_observation(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        changed = deepcopy(bundle)
        changed['spec']['frames'][0]['fields'][0]['meaning'] = 'Different semantics'
        self.assertEqual(assess_candidate(changed, [source], [o])['source_open'], 1)

    def test_wrong_source_and_silent_source_removal_are_rejected(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        changed = deepcopy(source)
        changed['views'][0]['public']['source_text'] = 'different source'
        records = run_bundle(bundle, source)['records']
        with self.assertRaisesRegex(ValueError, 'different source bytes'):
            check_binding(o, changed, bundle['spec'], records)
        with self.assertRaisesRegex(ValueError, 'silently disappear'):
            assess_candidate(bundle, [], [o])

    def test_partial_source_review_requires_real_origin_and_typed_value(self):
        source, bundle = fixture()
        for changes in ({'value': None}, {'review_origin': ''}, {'field': 'unacquired'},
                        {'support_ids': [True]}, {'field': 'members', 'value': [{}]}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.observation(source, bundle, **changes)

    def test_source_program_cannot_emit_native_answer_labels(self):
        source, bundle = fixture()
        bundle['source_program'] = 'def apply(inputs, premises):\n    return {"answer": "Entailment"}\n'
        with self.assertRaisesRegex(ValueError, 'native answer labels'):
            compile_bundle(bundle, {})

    def test_retains_rejected_versions_and_acquisition_receipts(self):
        source, bundle = fixture()
        o = self.observation(source, bundle)
        a = assess_candidate(bundle, [source], [o])
        state = update_frontier({}, bundle, a, acquisition_receipt='first real receipt')
        changed = deepcopy(bundle)
        changed['source_program'] = changed['source_program'].replace('"left"', '"right"')
        a2 = assess_candidate(changed, [source], [o])
        state2 = update_frontier(state, changed, a2, acquisition_receipt='second real receipt')
        self.assertEqual(len(state2['versions']), 2)
        self.assertEqual(len(state2['attempts']), 2)
        self.assertEqual(len(state['versions']), 1)
        self.assertFalse(state2['production_induction_implemented'])

    def test_trace_preserves_results_and_retains_producer_ancestry(self):
        source, bundle = fixture()
        original = bundle['source_program']
        bundle['source_program'] = ('def produce():\n' +
            original.split('\n', 1)[1] +
            '\ndef apply(inputs, premises):\n    return produce()\n')
        normal = run_bundle(bundle, source)
        traced = run_bundle(bundle, source, trace=True)
        self.assertEqual(normal['records'], traced['records'])
        self.assertEqual(normal['views'], traced['views'])
        found = producing_calls(traced['source_trace'], traced['records'][0])
        self.assertEqual(found['functions'], ['apply', 'produce'])
        self.assertIn(['apply', 'produce'], found['lineages'])
        self.assertFalse(found['semantic_fault_proved'])

    def test_trace_diagnostics_do_not_complete_unknowns(self):
        source, bundle = fixture()
        bundle['source_program'] = bundle['source_program'].replace('"value": "left"', '"value": None')
        a = run_bundle(bundle, source, trace=True)
        self.assertIn('owner', a['records'][0]['unresolved_fields'])

    def test_trace_truncation_is_explicit_and_does_not_change_output(self):
        code = 'def apply(inputs, premises):\n    return list(range(140))\n'
        result = execute_json(code, {}, {}, trace=True)
        self.assertEqual(result['result'], list(range(140)))
        self.assertTrue(result['trace_truncated'])


if __name__ == '__main__':
    unittest.main()
