"""Executable operator witnesses;all finite examples are construction fixtures."""
import unittest

from experiments.two_method_ablation_assets import prepare
from experiments.two_method_graph_corpus import read
from legal_skill_guard.paired_interfaces.ablation_paths import finite_operator_paths
from legal_skill_guard.paired_interfaces.residual import FiniteModule, decode, encode
from legal_skill_guard.skill_evolution.objects import digest


class AblationPathTests(unittest.TestCase):
    def module(self):
        return FiniteModule.build('constructed_local_weight', {'weight': list(range(8))},
            [{'threshold': 2}, {'threshold': 5}], lambda u, c: {'over': u['weight'] > c['threshold']},
            consumer_sha256=digest('constructed law program'),
            source_scope={'source_fields': ['facts'], 'local_unit': 'one identified weight'})

    def test_both_restricted_paths_preserve_every_local_state_and_context(self):
        module = self.module(); result = finite_operator_paths(module)
        self.assertEqual(result['end_classes'], 3)
        self.assertEqual(len(result['compression_merges']), 5)
        self.assertTrue(result['refinement_splits'])
        for asset in result['assets'].values():
            for index, state in enumerate(module.states):
                for context_index, context in enumerate(module.contexts):
                    actual = decode(asset, encode(asset['features'], state), context, module_binding=module.binding)
                    self.assertEqual(actual, module.outcomes[index][context_index])
        self.assertTrue(result['same_reader_wire_contract'])
        self.assertFalse(result['operator_path_distinguishable_from_final_accuracy'])

    def test_every_refinement_step_contains_a_real_differing_program_output(self):
        result = finite_operator_paths(self.module())
        for witness in result['refinement_splits']:
            self.assertNotEqual(witness['left_output'], witness['right_output'])
            self.assertGreater(witness['new_blocks'], 1)

    def test_real_fixed_modules_keep_primary_pool_and_show_degenerate_endpoints(self):
        out, protocol, manifest = prepare()
        self.assertFalse(protocol['primary_candidate_pool_changed'])
        self.assertEqual(manifest['Airline_endpoint_classes'], 4)
        self.assertEqual(manifest['Airline_compression_merges'], 97)
        self.assertEqual(manifest['Airline_refinement_splits'], 1)
        self.assertEqual(manifest['OE_refinement_witnesses'], 10)
        airline = read(out / 'Airline_operator_paths.json')
        self.assertTrue(airline['production_array_factorization_certificate']['arbitrary_finite_bag_array_length'])
        self.assertEqual(airline['original_production_module_binding'], protocol['original_production_Airline_module_binding'])
        for report in read(out / 'OE_operator_paths.json'):
            self.assertTrue(report['same_endpoint_as_primary_local_records'])
            for witness in report['refinement_witnesses']:
                changes = {key for key in witness['left_inputs'] if witness['left_inputs'][key] != witness['right_inputs'][key]}
                self.assertEqual(changes, {witness['field']})
                self.assertNotEqual(witness['left_program_output'], witness['right_program_output'])


if __name__ == '__main__':
    unittest.main()
