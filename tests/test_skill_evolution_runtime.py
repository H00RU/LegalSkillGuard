"""Meaningful runtime and data isolation checks before any physical generation."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest

from legal_skill_guard.skill_evolution.objects import Skill, Library, coupled_blocks
from legal_skill_guard.skill_evolution.teacher import validate_grounding
from legal_skill_guard.skill_evolution.runtime import execute_helper, SkillRuntime, render_messages
from legal_skill_guard.skill_evolution.native import answer_wire_schema, decode_answer, restore_enum_transport, source_spans
from legal_skill_guard.skill_evolution.controlled import add_controlled
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.patterns import instantiate_edit
from legal_skill_guard.inference.codex_cli_client import canonical_json_sha256


def fixture_ledger(folder, freeze=None):
    path = Path(folder) / 'fixture.sqlite3'
    with sqlite3.connect(path) as db:
        db.execute('create table meta (key text primary key, value text not null)')
        db.execute('create table calls (id text primary key, role text, purpose text, bucket text, source text, request_hash text, status text, reserved_at real, result text)')
        db.execute('insert into meta values (?,?)', ('spec', json.dumps({'fixture_only': True})))
    return EvolutionLedger(path, run_id='fixture', sources={'train': ['train'], 'dev': ['dev'], 'test': ['test']},
                           binding={'fixture': True}, freeze=freeze)


def helper(procedure='def apply(inputs, premises):\n    return {"answer": inputs["a"] and premises["p"]}\n'):
    return Skill('test', 'fixture only', procedure,
        {'a': {'type': 'boolean', 'mode': 'read', 'question': 'A'}},
        {'answer': {'type': 'boolean'}},
        {'p': {'type': 'boolean', 'mode': 'constant', 'value': True, 'origin': {'source': 'fixture'}}},
        (), (), (), ()).validate()


class RuntimeTests(unittest.TestCase):
    def test_read_span_ids_bind_exact_source_and_preserve_structured_facts(self):
        public = {'source_text': 'Rule header\nA rule.\n\nA second rule.',
                  'facts': {'actual_known': False, 'tax_year': 2025}}
        spans = source_spans(public)
        self.assertEqual([s['id'] for s in spans], list(range(len(spans))))
        for span in spans:
            raw = public[span['field']] if isinstance(public[span['field']], str) else json.dumps(public[span['field']], ensure_ascii=False)
            self.assertEqual(span['text'], raw[span['start']:span['end']])
        self.assertIn('"actual_known": false', spans[-1]['text'])
        self.assertEqual(''.join(public['source_text'].split()), ''.join(''.join(s['text'].split()) for s in spans if s['field']=='source_text'))
    def test_source_record_accepts_existing_read_port_without_counting_it_as_lift(self):
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'literal source'}
        old = helper()
        current = replace(old, inputs={'a': {'type': 'boolean', 'mode': 'read',
            'question': 'Read current A.', 'field': 'a', 'skill_id': None}},
            premises={'p': {**old.premises['p'], 'origin': origin}},
            semantic_records=({'id': 'read_record', 'ports': ['a']},),
            source_provenance=(origin,)).validate()
        validate_grounding(current, {'fixture': {'views': [{'id': 'v', 'public': {'source_text': 'literal source'}}]}})
        self.assertEqual(coupled_blocks(current), [])
        self.assertEqual(current.procedure, old.procedure)
    def test_observed_enum_encoding_recovery_cannot_choose_a_new_citation(self):
        schema = {'type': 'array', 'items': {'type': 'string', 'enum': ['11 U.S.C. § 522(d)(9)']}}
        raw = ['11 U.S.C. Â§ 522(d)(9)', '11 U.S.C. Â§ 999']
        value, changes = restore_enum_transport(raw, schema)
        self.assertEqual(value, ['11 U.S.C. § 522(d)(9)', '11 U.S.C. Â§ 999'])
        self.assertEqual(len(changes), 1)
        self.assertEqual(raw[0], '11 U.S.C. Â§ 522(d)(9)')
    def test_physical_ledger_reuse_and_frozen_teacher_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = fixture_ledger(folder)
            request = {'thinking': False, 'payload': 'fixture'}
            self.assertTrue(ledger.reserve('fixture:one', role='executor', purpose='skill_actor', source='train', request=request)['dispatch'])
            ledger.finish('fixture:one', status='completed', result={'answer': 1})
            self.assertFalse(ledger.reserve('fixture:one', role='executor', purpose='skill_actor', source='train', request=request)['dispatch'])
            with self.assertRaises(BudgetError):
                ledger.reserve('fixture:wrong', role='teacher', purpose='skill_teacher', source='dev', request={})
            with ledger.transaction() as db:
                self.assertEqual(db.execute('select count(*) from calls').fetchone()[0], 1)
        with tempfile.TemporaryDirectory() as folder:
            ledger = fixture_ledger(folder, freeze={'batch': 8, 'artifact_sha256': 'fixture'})
            with self.assertRaises(BudgetError):ledger.require_train(['train'])
            with self.assertRaises(BudgetError):ledger.permit('train', 'skill_teacher', 'teacher')
            ledger.permit('test', 'skill_test', 'executor')

    def test_teacher_orphan_cache_cannot_be_charged_as_new_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = fixture_ledger(folder)
            teacher = object.__new__(FrozenTeacher)
            teacher.ledger, teacher.artifacts, teacher.config = ledger, Path(folder), {}
            teacher.adapter = SimpleNamespace(cache_root=Path(folder), request_payload=lambda **args: args)
            schema = {'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}
            args = {'purpose': 'skill_teacher', 'system_prompt': 'fixture', 'user_prompt': 'fixture', 'output_schema': schema}
            cache = Path(folder) / 'skill_teacher' / (canonical_json_sha256(args) + '.json')
            cache.parent.mkdir();cache.write_text('{}')
            with self.assertRaises(BudgetError):
                teacher.propose('fixture:teacher', source_ids=['train'], system_prompt='fixture', user_prompt='fixture', output_schema=schema)
            with ledger.transaction() as db:self.assertEqual(db.execute('select count(*) from calls').fetchone()[0], 0)

    def test_model_sees_the_same_schema_as_guided_decoding_and_hold_precedes_transport(self):
        schema = {'type': 'object', 'properties': {'answer': {'type': 'boolean'}},
                  'required': ['answer'], 'additionalProperties': False}
        messages = render_messages('fixture', {'public': 'fixture source'}, schema)
        self.assertEqual(json.loads(messages[-1]['content'])['output_schema'], schema)
        with tempfile.TemporaryDirectory() as folder:
            executor = object.__new__(FrozenExecutor)
            executor.artifacts = Path(folder)
            (Path(folder) / 'HOLD_GENERATION').write_text('hold before transport')
            # No ledger/network/config exists: the boundary must fire first.
            with self.assertRaises(GenerationHold):executor.generate('fixture')

    def test_edit_transplant_preserves_new_source_bindings(self):
        before = 'def apply(inputs, premises):\n    return {"answer": inputs["old_a"] or premises["old_b"]}\n'
        after = before.replace(' or ', ' and ')
        target = before.replace('old_a', 'current_a').replace('old_b', 'current_b')
        program = instantiate_edit(before, after, target)
        self.assertIn("inputs['current_a'] and premises['current_b']", program)
        unsupported = after.replace('premises["old_b"]', '99')
        self.assertIsNone(instantiate_edit(before, unsupported, target))

    def test_isolated_helper_preserves_types_and_blocks_effects(self):
        self.assertEqual(execute_helper(helper(), {'a': True}, {'p': False}), {'answer': False})
        with self.assertRaises(Exception):
            execute_helper(helper(), {'a': 1}, {'p': True})
        with self.assertRaises(ValueError):
            helper('def apply(inputs, premises):\n    import os\n    return premises["p"]\n')
        with self.assertRaises(ValueError):
            helper('def apply(inputs, premises):\n    return {"answer": open("/etc/passwd") and premises["p"]}\n')

    def test_public_output_codec_has_no_gold_and_rejects_duplicate_keys(self):
        view = {'id': 'EC', 'public': {'original_input': '11 U.S.C. § 522(d)(1)\nFacts:\na chair valued at $1 and a desk valued at $2'},
                'answer_schema': {'type': 'object', 'additionalProperties': {'type': 'array', 'items': {'type': 'string'}}}}
        value = {'answer': [{'asset': 'a chair', 'claims': ['11 U.S.C. § 522(d)(1)']}], 'evidence_sentence_ids': []}
        self.assertEqual(decode_answer('OpenExempt', view, value)[0], {'a chair': ['11 U.S.C. § 522(d)(1)']})
        value['answer'].append(value['answer'][0])
        with self.assertRaises(ValueError):decode_answer('OpenExempt', view, value)

    def test_native_auxiliary_fields_cannot_expand_without_public_sentence_ids(self):
        view = {'id': 'native', 'public': {'source_text': 'fixture', 'question': 'fixture'},
                'answer_schema': {'type': 'integer', 'minimum': 0}}
        schema = answer_wire_schema('RuleArena_Airline', view)
        self.assertEqual(schema['properties']['evidence_sentence_ids']['maxItems'], 0)
        cnli = {'id': 'q', 'public': {'sentence_spans': [[0, 3], [4, 8]]},
                'answer_schema': {'type': 'string', 'enum': ['Entailment']}}
        evidence = answer_wire_schema('ContractNLI', cnli)['properties']['evidence_sentence_ids']
        self.assertEqual((evidence['maxItems'], evidence['items']['maximum']), (2, 1))

    def test_controlled_layer_keeps_parent_and_label_boundaries(self):
        root = Path(__file__).resolve().parents[1]
        prepared = root / 'artifacts/legal_skill_evolution_20261111/prepared/train'
        if not prepared.is_dir():self.skipTest('Local native data not installed')
        public = json.loads((prepared / 'public.json').read_text())
        grading = json.loads((prepared / 'grading.json').read_text())
        evidence = json.loads((root / 'reports/legal_skill_evolution_plan_20261111/CONTROLLED_LAYER_EVIDENCE.json').read_text())
        augmented, grades = add_controlled(public, grading, evidence)
        self.assertEqual(len(augmented), 128)
        self.assertEqual(sum(len(r['views']) for r in augmented), 312)
        self.assertEqual(sum(len(r['views']) for r in public), 280)
        for row in augmented:
            self.assertNotIn('grading', row)
            self.assertEqual(len(row['views']), len(grades[row['key']]))
            for view in row['views']:
                self.assertNotIn('reference_definition_satisfied', view['public'])

    def test_actual_producer_consumer_trace(self):
        class Reads:
            def read(self, *args, **kwargs):return {'a': True}, {'kind': 'READ_LOCAL'}
        producer = helper()
        producer = replace(producer, id='producer', outputs={'claim': {'type': 'boolean'}},
            procedure='def apply(inputs, premises):\n    return {"claim": inputs["a"] and premises["p"]}\n')
        consumer = replace(helper(), id='consumer', inputs={'a': {'type': 'boolean', 'mode': 'skill',
            'skill_id': 'producer', 'field': 'claim'}})
        result = SkillRuntime(Reads()).run({'key': 'fixture', 'dataset': 'fixture'},
            {'id': 'v', 'public': {}, 'answer_schema': {'type': 'boolean'}},
            Library(skills={'producer': producer, 'consumer': consumer}), retrieved=['consumer'], fallback=False)
        self.assertTrue(result['core_executed'])
        self.assertTrue(result['answer'])
        self.assertEqual(len([e for e in result['events'] if e['kind'] == 'USE']), 1)


if __name__ == '__main__':unittest.main()
