import hashlib
import json
from pathlib import Path
import tempfile
import types
import unittest

from legal_skill_guard.paired_interfaces.control_answers import source_bundle, wire_schema
from legal_skill_guard.paired_interfaces.control_programs import ControlProgramRuntime
from legal_skill_guard.paired_interfaces.control_tools import legal_tools
from legal_skill_guard.paired_interfaces.native_adapters import LIBRARY, run_airline
from tests import test_paired_native_adapters as native_fixtures


def native_program():
    return {'predicates': [{'id': 'native', 'prompt': 'Return each current native task answer.',
                           'schema_mode': 'native', 'schema': {}}], 'extractors': [],
            'composition': "def compose(inputs, predict, extractors):\n    return predict('native', inputs['public'])\n"}


class EncodedExecutor:
    """Constructed codec fixture; not an actual weak response or trial."""
    def __init__(self, value):
        self.ledger = types.SimpleNamespace(run_id='constructed_native_codec')
        self.value, self.calls = value, []

    def generate(self, call_id, **kwargs):
        self.calls.append(kwargs)
        return {'content': json.dumps({'value': self.value}), 'finish_reason': 'stop',
                'usage': {'prompt_tokens': 1, 'completion_tokens': 1},
                'elapsed_seconds': 0, 'cache_hit': False}


class ControlNativeTools(unittest.TestCase):
    def test_native_source_bundle_decodes_each_task_and_keeps_cni_evidence(self):
        public = {'source_text': 'A clause.', 'sentence_spans': [[0, 9]], 'hypothesis': 'A claim.'}
        source = {'key': 'constructed', 'dataset': 'ContractNLI', 'views': [
            {'id': key, 'public': public, 'answer_schema': {'type': 'string', 'enum': ['Entailment']}}
            for key in ('q1', 'q2')]}
        bundle = source_bundle(source)
        executor = EncodedExecutor({key: {'answer': 'Entailment', 'evidence_sentence_ids': [0]}
                                   for key in ('q1', 'q2')})
        with tempfile.TemporaryDirectory() as tmp:
            result = ControlProgramRuntime(executor, tmp, max_calls=1).run(native_program(), source, bundle)
        self.assertEqual(result['answer'], {'q1': 'Entailment', 'q2': 'Entailment'})
        self.assertEqual(result['traces'][0]['native_evidence'], {'q1': [0], 'q2': [0]})
        self.assertEqual(len(executor.calls), 1)

    def test_public_oe_codec_rejects_duplicate_asset_outputs_without_last_write_repair(self):
        source = {'key': 'constructed', 'dataset': 'OpenExempt', 'views': [{'id': 'EC',
            'public': {'original_input': '11 U.S.C. § 522(d)(3)\nFacts:\nA blender $10 and a bed $20.\nOutput contract:'},
            'answer_schema': {'type': 'object', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}}}]}
        bundle = source_bundle(source)
        executor = EncodedExecutor({'EC': {'answer': [{'asset': 'blender', 'claims': []},
                                                      {'asset': 'blender', 'claims': []}],
                                           'evidence_sentence_ids': []}})
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Duplicate asset'):
                ControlProgramRuntime(executor, tmp, max_calls=1).run(native_program(), source, bundle)
            record = json.loads(next(Path(tmp).glob('program_executions/*/result.json')).read_text())
            self.assertFalse(record['core_executed'])
            self.assertIn('Duplicate asset', record['error'])

    def test_control_can_execute_the_same_actual_frozen_airline_program_without_a_model(self):
        graph, units = native_fixtures.NativeAdapterTests().graph()
        expected = run_airline(graph, units, hashlib.sha256(LIBRARY.read_bytes()).hexdigest())
        source = {'key': 'constructed', 'dataset': 'RuleArena_Airline', 'views': [
            {'id': 'q', 'public': {'facts': units[0]['text']}, 'answer_schema': {'type': 'integer'}}]}
        bundle = source_bundle(source)
        tools, assets = legal_tools(source, bundle)
        value = {'predicates': [], 'extractors': [],
                 'composition': "def compose(inputs, predict, extractors):\n    result = apply_legal('frozen_legal_module', "
                    + repr(expected['inputs']) + ")\n    return {'q': result['answer']}\n"}
        executor = EncodedExecutor(None)
        with tempfile.TemporaryDirectory() as tmp:
            actual = ControlProgramRuntime(executor, tmp, max_calls=1, shared_assets=assets,
                                           legal_tools=tools).run(value, source, bundle)
        self.assertEqual(actual['answer'], {'q': expected['answer']})
        self.assertTrue(actual['core_executed'])
        self.assertEqual(actual['traces'][0]['type'], 'legal_tool')
        self.assertEqual(actual['traces'][0]['new_model_requests'], 0)
        self.assertFalse(executor.calls)


if __name__ == '__main__':
    unittest.main()
