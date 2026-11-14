"""Compare projected G outputs with the exact preexisting subset enumerator."""
from copy import deepcopy
import unittest

from tests.test_skill_evolution_program_composition_profiles import ProgramCompositionProfileTests
from legal_skill_guard.skill_evolution.program_composition_profiles import admissible_program_compositions
from legal_skill_guard.skill_evolution.projected_composition_profiles import admissible_projected_compositions
from legal_skill_guard.skill_evolution.relational_learning import execute_composition
from legal_skill_guard.skill_evolution.relational_rules import canonical
from legal_skill_guard.skill_evolution.source_observations import fact


class ProjectedProfileTests(unittest.TestCase):
    def test_recursive_and_redundant_paths_match_all_actual_subsets(self):
        lib, obs = ProgramCompositionProfileTests().fixture()
        lib['language']['rules'].extend([
            {'id': 'recursive_identity', 'cost': 1, 'head': fact('d', {'var': 'T'}, {'var': 'U'}),
             'body': [fact('d', {'var': 'T'}, {'var': 'U'})]},
            {'id': 'duplicate_output_path', 'cost': 1,
             'head': deepcopy(lib['language']['rules'][1]['head']),
             'body': deepcopy(lib['language']['rules'][1]['body'])}])
        check = lambda output: {'accepted': bool(output['statements']), 'reason': 'software_fixture'}
        before = admissible_program_compositions(lib, obs, check)
        after = admissible_projected_compositions(lib, obs, check)
        self.assertEqual(after['status'], 'complete')
        self.assertEqual({canonical(r['theory']): r['admissible'] for r in before['evaluations']},
                         {canonical(r['theory']): r['admissible'] for r in after['evaluations']})
        for row in after['evaluations']:
            actual = execute_composition(lib['language'], row['witness_rule_ids'], obs['context'])
            theory = [{k: v for k, v in a.items() if k != 'context_index'} for a in actual['certain_outputs']]
            self.assertEqual(theory, row['theory'])

    def test_partial_source_constraint_and_unknown_are_preserved(self):
        lib, obs = ProgramCompositionProfileTests().fixture()
        before = admissible_program_compositions(lib, obs, lambda o: {'accepted': True, 'reason': 'fixture'})
        atom = next(r['theory'][0] for r in before['evaluations'] if r['theory'])
        obs['context']['forbidden'] = [atom]
        after = admissible_projected_compositions(lib, obs, lambda o: {'accepted': True, 'reason': 'fixture'})
        self.assertEqual(len(after['allowed_theories']), 1)
        unknown = deepcopy(obs)
        unknown['context']['unknown_groups'] = [[[], []]]
        with self.assertRaisesRegex(ValueError, 'unknown'):
            admissible_projected_compositions(lib, unknown, lambda o: None)
        with self.assertRaises(ValueError):
            admissible_projected_compositions(lib, obs, lambda o: None, timeout_seconds=0)
