"""Explicit scope checks from a real source-level semantic failure."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from legal_skill_guard.skill_evolution.claim_scope import declared_claim_mismatch
from legal_skill_guard.skill_evolution.objects import Skill


class ClaimScopeTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parents[1]
        folder = root / 'reports/legal_skill_evolution_run_20261111/activation_evidence'
        self.library = json.loads((folder / 'body_adapter_replay/Full/B1.json').read_text())
        self.skill = Skill.from_dict(self.library['skills']['section_152_b1_dependent_ineligibility_answer'])
        self.sources = {s['key']: s for s in json.loads((folder / 'original_TRAIN_sources.json').read_text())['public']}

    def test_actual_151_query_cannot_use_the_declared_152_final_proposition(self):
        view = self.sources['SARA_v2_Binary:cc82ab0fe40ca06245a9fdd00273c97ae8d8c2af9783b5618826de0125d41397']['views'][0]
        proof = declared_claim_mismatch(self.skill, view)
        self.assertEqual(proof['declared_clause'], ['152', 'b', '1'])
        self.assertEqual(proof['queried_clause'], ['151', 'c'])
        self.assertFalse(proof['legal_rule_truth_inferred'])

    def test_actual_152_query_is_preserved(self):
        view = self.sources['SARA_v2_Binary:a51930fd174465a9bc8bd24887336e753d1f76990c346645a1ae5cd8c074536d']['views'][0]
        self.assertIsNone(declared_claim_mismatch(self.skill, view))

    def test_unstated_ambiguous_or_ancestor_scopes_are_unknown(self):
        for question in ('Does the individual qualify?', 'Compare section 151(c) and section 152(b)(1).',
                         'Does section 152 apply?', 'Under section 152(b)(1)(A), does the claim follow?'):
            self.assertIsNone(declared_claim_mismatch(self.skill, {'public': {'question': question}}))
        from dataclasses import replace
        outputs = deepcopy(self.skill.outputs)
        for description in ('Uses section 152 to answer the supplied task.',
                            'The answer to the current §152(b)(1) proposition using section 151(c).'):
            outputs['answer']['description'] = description
            self.assertIsNone(declared_claim_mismatch(replace(self.skill, outputs=outputs),
                {'public': {'question': 'Section 151(c) applies.'}}))

    def test_scope_is_not_guessed_from_skill_id_or_provenance(self):
        from dataclasses import replace
        outputs = deepcopy(self.skill.outputs);outputs['answer']['description'] = 'Native answer.'
        self.assertIsNone(declared_claim_mismatch(replace(self.skill, outputs=outputs),
            {'public': {'question': 'Section 151(c) applies.'}}))

    def test_a_seed_description_does_not_block_a_generic_or_intermediate_reader(self):
        from dataclasses import replace
        inputs = deepcopy(self.skill.inputs)
        for port in inputs.values():
            port['question'] = 'Is the individual a dependent under section 152(b)(1)?'
        self.assertIsNone(declared_claim_mismatch(replace(self.skill, inputs=inputs),
            {'public': {'question': 'Section 151(c) applies.'}}))


if __name__ == '__main__':unittest.main()
