"""Actual full-source replacement wire and compiler, without a model client."""
from copy import deepcopy
import unittest
import jsonschema
from tests.test_skill_evolution_source_function_protocol import fixture
from experiments.legal_skill_evolution_source_gap_acquisition import compile_raw,C_SCHEMA,FREE_SCHEMA
from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.span_compiler import execute_json


class SourceGapProtocolTests(unittest.TestCase):
    def raw(self,arm):
        old,proposal,sources=fixture(arm)
        old['source_program']='def obsolete(inputs,premises):\n    return {}\n\n'+old['source_program']
        proposal.pop('source_functions')
        proposal['source_program']='def apply(inputs,premises):\n    return inputs["source_output"]\n'
        if arm=='FreeUpdate':
            proposal['composition_functions']=[proposal.pop('composition')]
            old['composition_program']='def apply(inputs,premises):\n    return inputs["source_output"]\n'
        return old,proposal,sources

    def test_source_module_replaces_old_helpers_for_both_actual_wire_formats(self):
        for arm in ('ConstraintAcquire','FreeUpdate'):
            old,proposal,sources=self.raw(arm);snapshot=deepcopy(old)
            schema=C_SCHEMA if arm=='ConstraintAcquire' else FREE_SCHEMA
            self.assertEqual(strict_output_schema_issues(schema),[])
            jsonschema.validate(proposal,schema)
            lib,receipt,canonical=compile_raw(old,proposal,arm,sources)
            self.assertEqual(lib['source_program'],proposal['source_program'])
            self.assertNotIn('obsolete',lib['source_program'])
            incoming={'statements':[],'complete':False,'unresolved':['actual unresolved source']}
            self.assertEqual(execute_json(lib['source_program'],{'source_output':incoming},{},allow_helpers=True),incoming)
            self.assertEqual(old,snapshot)
            self.assertEqual(lib['source_program_update']['mode'],'complete_replacement')

    def test_new_complete_source_module_cannot_borrow_an_undeclared_old_helper(self):
        old,proposal,sources=self.raw('FreeUpdate')
        proposal['source_program']='def apply(inputs,premises):\n    return obsolete(inputs,premises)\n'
        with self.assertRaisesRegex(ValueError,'Unsupported call'):
            compile_raw(old,proposal,'FreeUpdate',sources)
