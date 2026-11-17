from copy import deepcopy
import json
from pathlib import Path
import tempfile
import types
import unittest

from experiments.two_method_scope_control import freeze_best
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.scope_learning import (
    admit_variants, adversary_schema, blind_verifier_payload, make_variant,
    revision_schema, strict_json, verification_schema)
from legal_skill_guard.paired_interfaces.scope_replay import attribute, replay


class RecordedLabelFixture:
    """No service/ledger access; constructed labels are not experiment results."""
    def __init__(self, values=('yes',)):
        self.ledger = types.SimpleNamespace(run_id='scope_constructed_fixture')
        self.values, self.calls = iter(values), []

    def generate(self, identity, **kwargs):
        self.calls.append(identity)
        return {'content': json.dumps({'value': next(self.values)}), 'finish_reason': 'stop',
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1}, 'elapsed_seconds': 0,
                'cache_hit': False}


def fixture_program(composition):
    return {'predicates': [{'id': 'gate', 'prompt': 'Return the gate classification.',
        'schema_mode': 'fixed', 'schema': {'type': 'string', 'enum': ['yes', 'no']}}],
        'extractors': [], 'composition': composition}


class ScopeCounterfactualReplay(unittest.TestCase):
    def setUp(self):
        self.source = {'key': 'constructed_parent', 'dataset': 'fixture'}
        self.view = {'id': 'native', 'public': {'facts': 'gate'}, 'answer_schema': {'type': 'integer'}}

    def execute(self, tmp, program, executor=None, tools=None):
        executor = executor or RecordedLabelFixture()
        runtime = ControlProgramRuntime(executor, tmp, max_calls=10, legal_tools=tools)
        result = runtime.run(program, self.source, self.view)
        message = json.loads(runtime.execution_path(program, self.source, self.view).with_name('input.json').read_text())
        return message, result, executor

    def test_counterfactual_uses_recorded_label_without_new_executor_call(self):
        program = fixture_program("def compose(inputs, predict, extractors):\n    if predict('gate', inputs['public']) == 'yes':\n        return 1\n    return 0\n")
        with tempfile.TemporaryDirectory() as tmp:
            message, execution, executor = self.execute(tmp, program)
            report = attribute(message, execution)
            self.assertTrue(report['baseline_reproduced'])
            self.assertEqual(report['interventions'][0]['answer'], 0)
            self.assertEqual(len(executor.calls), 1)
            self.assertEqual(report['new_model_requests'], 0)

    def test_new_branch_predicate_input_is_unsupported_not_fabricated(self):
        program = fixture_program("def compose(inputs, predict, extractors):\n    if predict('gate', 'first') == 'yes':\n        return 1\n    if predict('gate', 'unobserved') == 'yes':\n        return 2\n    return 0\n")
        with tempfile.TemporaryDirectory() as tmp:
            message, execution, executor = self.execute(tmp, program)
            result = replay(message, execution, overrides={0: 'no'})
            self.assertFalse(result['supported'])
            self.assertIn('Unobserved predicate input', result['error'])
            self.assertEqual(len(executor.calls), 1)

    def test_new_pure_legal_input_can_be_recomputed_under_same_binding(self):
        program = fixture_program("def compose(inputs, predict, extractors):\n    n = 1\n    if predict('gate', 'first') == 'no':\n        n = 2\n    return apply_legal('law', {'n': n})['answer']\n")
        tool = {'binding_sha256': 'constructed-law-binding',
            'input_schema': {'type': 'object', 'properties': {'n': {'type': 'integer'}},
                             'required': ['n'], 'additionalProperties': False},
            'invoke': lambda x: {'answer': 10 * x['n']}}
        with tempfile.TemporaryDirectory() as tmp:
            message, execution, executor = self.execute(tmp, program, tools={'law': tool})
            report = attribute(message, execution, legal_tools={'law': tool})
            self.assertTrue(report['baseline_reproduced'])
            self.assertEqual(report['interventions'][0]['answer'], 20)
            self.assertEqual(len(executor.calls), 1)
            result = replay(message, execution, legal_tools={'law': {**tool, 'binding_sha256': 'other'}})
            self.assertFalse(result['supported'])

    def test_repeated_same_input_preserves_actual_occurrence_labels(self):
        program = fixture_program("def compose(inputs, predict, extractors):\n    n = 0\n    for i in range(2):\n        if predict('gate', 'same') == 'yes':\n            n = n + 1\n    return n\n")
        with tempfile.TemporaryDirectory() as tmp:
            message, execution, _ = self.execute(tmp, program, RecordedLabelFixture(('yes', 'no')))
            report = attribute(message, execution, max_replays=1)
            self.assertTrue(report['baseline_reproduced'])
            self.assertEqual(report['baseline']['answer'], 1)
            self.assertTrue(report['enumeration_truncated'])
            self.assertEqual(replay(message, execution, overrides={1: 'yes'})['answer'], 2)

    def test_failed_original_never_becomes_zero_loss_attribution(self):
        report = attribute({}, {'core_executed': False, 'error': 'incomplete weak JSON'})
        self.assertFalse(report['baseline_reproduced'])
        self.assertEqual(report['original_error'], 'incomplete weak JSON')
        self.assertEqual(report['interventions'], [])


def variant_spec(before='hospital', after='prison', answer='yes', slot='local'):
    return {'slot': slot, 'target_predicate': 'gate',
            'edits': [{'before': before, 'after': after}],
            'intended_answer_json': json.dumps({'native': answer}),
            'policy_justification': 'GENERATOR_ONLY_JUSTIFICATION'}


class ScopeSourceVariants(unittest.TestCase):
    def source(self, dataset='SARA_v2_Binary', public=None):
        return {'key': 'constructed_parent', 'dataset': dataset, 'views': [{'id': 'native',
            'public': public or {'source_text': 'Hospital and prison law is immutable.',
                               'facts': 'A was in a hospital.', 'question': 'Does exclusion apply?'},
            'answer_schema': {'type': 'string', 'enum': ['yes', 'no']}}]}

    def test_facts_only_and_blind_verifier_excludes_generator_information(self):
        source = self.source()
        old = deepcopy(source)
        variant = make_variant(source, variant_spec(), 'local')
        self.assertEqual(source, old)
        public = variant['source']['views'][0]['public']
        self.assertEqual(public['source_text'], old['views'][0]['public']['source_text'])
        self.assertEqual(public['facts'], 'A was in a prison.')
        payload = blind_verifier_payload([variant], {})
        self.assertNotIn('GENERATOR_ONLY_JUSTIFICATION', json.dumps(payload))
        self.assertNotIn('intended_answer', json.dumps(payload))
        self.assertNotIn('target_predicate', json.dumps(payload))
        checked = admit_variants([variant], {'verdicts': [{'slot': 'local',
            'well_formed_and_policy_supported': True, 'answer_json': '{"native":"no"}',
            'rationale': 'Separate reading disagrees.'}]})
        self.assertFalse(checked[0]['admitted'])
        with self.assertRaises(ValueError):
            make_variant(source, variant_spec('immutable', 'changed'), 'local')

    def test_CNI_offsets_follow_literal_edit_and_cross_boundary_edits_fail(self):
        source = self.source('ContractNLI', {'source_text': 'Alpha. Beta.',
            'sentence_spans': [[0, 6], [7, 12]], 'question': 'Unchanged task'})
        variant = make_variant(source, variant_spec('Alpha', 'LongAlpha'), 'local')
        public = variant['source']['views'][0]['public']
        self.assertEqual(public['sentence_spans'], [[0, 10], [11, 16]])
        self.assertEqual([public['source_text'][a:b] for a,b in public['sentence_spans']],
                         ['LongAlpha.', 'Beta.'])
        with self.assertRaises(ValueError):
            make_variant(source, variant_spec('a. B', 'merged'), 'local')

    def test_OE_edit_preserves_statutes_givens_and_output_contract(self):
        text = 'Statutes:\nFixed hospital rule.\nSolved Reasoning Steps:\nFixed.\nFacts:\nA owns a hospital.\n\nOutput contract: fixed.'
        source = self.source('OpenExempt', {'original_input': text})
        variant = make_variant(source, variant_spec(), 'local')
        value = variant['source']['views'][0]['public']['original_input']
        self.assertIn('Fixed hospital rule.', value)
        self.assertIn('A owns a prison.', value)
        self.assertTrue(value.endswith('Output contract: fixed.'))
        with self.assertRaises(ValueError):
            make_variant(source, variant_spec('Fixed hospital rule.', 'Changed law.'), 'local')

    def test_strict_labels_schema_contract_and_fixed_seed_selection(self):
        for schema in (revision_schema(), adversary_schema(), verification_schema()):
            self.assertEqual(strict_output_schema_issues(schema), [])
        for text in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ValueError):
                strict_json(text)
        histories = [{'index': 0, 'evaluation': {'mother_macro': .5}, 'synthetic_accuracy': 0},
                     {'index': 1, 'evaluation': {'mother_macro': .25}, 'synthetic_accuracy': 1},
                     {'index': 2, 'evaluation': {'mother_macro': .5}, 'synthetic_accuracy': 1}]
        self.assertEqual(freeze_best(histories)['index'], 0)


if __name__ == '__main__':
    unittest.main()
