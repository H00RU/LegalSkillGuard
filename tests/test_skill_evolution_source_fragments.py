"""Exact text binding from actual TRAIN citations; never new legal values."""
import base64
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import unittest

import jsonschema

from legal_skill_guard.inference.codex_cli_client import strict_output_schema_issues
from legal_skill_guard.skill_evolution.lift_proposals import compile_scheduled_lift
from legal_skill_guard.skill_evolution.native import source_spans
from legal_skill_guard.skill_evolution.objects import Library, Skill
from legal_skill_guard.skill_evolution.runtime import FrozenReads, LocalReadError, render_messages
from legal_skill_guard.skill_evolution.source_fragments import bind_fragment_value, fragment_field
from legal_skill_guard.skill_evolution.teacher import PROPOSAL_SCHEMA, reader_from_wire, proposal_schema
from tests.test_skill_evolution_runtime import helper

SPEC = {'type': 'array', 'representation': 'source_spans', 'question': 'Select the literal governing clauses.'}


class SourceFragmentReads(unittest.TestCase):
    def setUp(self):
        self.report = Path(__file__).resolve().parents[1] / 'reports/legal_skill_evolution_run_20261111'
        self.sources = {s['key']: s for s in json.loads((self.report / 'contract_original_TRAIN_public.json').read_text())}
        self.source = next(s for k, s in self.sources.items() if k.startswith('ContractNLI:354'))
        self.view = self.source['views'][0]

    def request(self, response, **options):
        reads = FrozenReads(None);captured = []
        def generate(*args, **kwargs):
            captured.append(kwargs)
            jsonschema.validate(response, kwargs['schema'])
            return deepcopy(response), {'call_id': 'fixture', 'physical_call_id': 'fixture'}
        reads.generate = generate
        value = reads.read(self.source, self.view, question='Select the actual nondisclosure clauses.',
            fields={'clauses': SPEC}, locator='current source', purpose='fixture',
            require_rule_support=True, allow_unresolved=True, **options)
        return value, captured

    def test_actual_bad_field_citations_recover_text_without_relabeling_its_value(self):
        path = self.report / 'source_rule_evidence/legal_skill_evolution_source_rule_check_20261112/FreeEvolution/B3_candidates/0.json'
        table = json.loads(path.read_text())['table']
        trace = next(x['trace'] for x in table['mixed_version_table'] if x['mask'] == 3 and x['source'] == self.source['key'])
        field = next(e['fields']['permitted_recipient_classes_and_disclosure_contexts']
            for v in trace['views'] for e in v['execution'].get('events', [])
            if e.get('kind') == 'READ_LOCAL' and 'permitted_recipient_classes_and_disclosure_contexts' in e.get('fields', {}))
        original = deepcopy(field)
        spans = source_spans({k: v for k, v in self.view['public'].items() if k != 'question'})
        positions = {(s['field'], s['start'], s['end'], s['text']): s['id'] for s in spans}
        ids = [positions[s['field'], s['start'], s['end'], s['text']] for s in field['support']]
        values, support, receipt = bind_fragment_value(ids, spans)
        self.assertEqual(field, original)
        self.assertEqual(values, [s['text'] for s in support])
        self.assertNotEqual(values, field['value'])  # No reinterpretation as class/basis atoms.
        for s in support:self.assertEqual(self.view['public']['source_text'][s['start']:s['end']], s['text'])
        self.assertEqual(receipt['wire_support_ids'], ids)

    def test_real_source_selection_has_no_generated_value_and_retains_qualifications(self):
        spans = source_spans({k: v for k, v in self.view['public'].items() if k != 'question'})
        span = next(s for s in spans if 'except as is required in the course of service to the CCPDT' in s['text'])
        (values, event), captured = self.request({'clauses': {'status': 'known', 'support_ids': [span['id']]}})
        self.assertEqual(values['clauses'], [span['text']])
        self.assertNotIn('value', captured[0]['schema']['properties']['clauses']['properties'])
        self.assertNotIn('view_id', captured[0]['content'])
        self.assertTrue(all(s['field'] != 'question' for s in captured[0]['content']['source_spans']))
        self.assertEqual(event['fields']['clauses']['source_binding']['source_order_ids'], [span['id']])
        first = captured[0]
        self.view = self.source['views'][1]
        _, second = self.request({'clauses': {'status': 'known', 'support_ids': [span['id']]}})
        self.assertEqual(render_messages(first['system'], first['content'], first['schema']),
            render_messages(second[0]['system'], second[0]['content'], second[0]['schema']))

    def test_unknown_stays_missing_and_known_empty_has_a_cost_bearing_error(self):
        (values, event), _ = self.request({'clauses': {'status': 'unknown', 'support_ids': []}})
        self.assertEqual(values, {})
        self.assertEqual(event['unresolved_fields'], ['clauses'])
        with self.assertRaisesRegex(LocalReadError, 'Invalid source-fragment selection') as error:
            self.request({'clauses': {'status': 'known', 'support_ids': []}})
        self.assertEqual(error.exception.event['physical_call_id'], 'fixture')
        with self.assertRaisesRegex(LocalReadError, 'Unknown fragment'):
            self.request({'clauses': {'status': 'unknown', 'support_ids': [0]}})

    def test_ID_set_normalization_is_explicit_and_invalid_IDs_are_rejected(self):
        spans = [{'id': 0, 'text': 'A'}, {'id': 1, 'text': 'B'}]
        values, _, receipt = bind_fragment_value([1, 0, 1], spans)
        self.assertEqual(values, ['A', 'B'])
        self.assertEqual(receipt['wire_support_ids'], [1, 0, 1])
        for ids in ([True], [-1], [2], ['0']):
            with self.assertRaises(ValueError):bind_fragment_value(ids, spans)
        for spec in ({**SPEC, 'type': 'boolean'}, {**SPEC, 'representation': 'infer_law'}):
            with self.assertRaises(ValueError):fragment_field(spec)

    def test_all_selected_fragments_must_be_rule_text_and_alignment_cannot_be_filled(self):
        self.view = {'id': 'v', 'public': {'source_text': 'Governing clause.', 'facts': 'Case fact.', 'question': 'Native query.'}}
        with self.assertRaisesRegex(LocalReadError, 'all come from supplied rule'):
            self.request({'clauses': {'status': 'known', 'support_ids': [0, 1]}})
        with self.assertRaisesRegex(LocalReadError, 'array alignment'):
            self.request({'clauses': {'status': 'known', 'support_ids': [0]}}, array_lengths={'clauses': 2})

    def test_teacher_and_Lift_keep_literal_array_types_and_unchanged_program(self):
        self.assertEqual(strict_output_schema_issues(PROPOSAL_SCHEMA), [])
        raw = {'id': 'r', 'question': 'Select literal text.', 'source_locator': 'current source',
               'fields': [{'name': 'p', **SPEC}], 'bindings': [{'premise': 'p', 'field': 'p'}]}
        reader = reader_from_wire(raw)
        self.assertEqual(reader['schema']['properties']['p'], {'type': 'array', 'items': {'type': 'string'}})
        old = helper();premises = deepcopy(old.premises)
        premises['p']['type'] = 'array';premises['p']['value'] = ['literal fixture text']
        old = replace(old, premises=premises,
            procedure='def apply(inputs, premises):\n    return {"answer": "literal" in premises["p"][0]}\n').validate()
        plan = {'skill_id': old.id, 'old_hash': old.hash, 'premises': ['p']}
        wire = {'question': 'Select literal text.', 'source_locator': 'current source',
                'fields': [{'name': 'p', 'question': 'Select literal text.', 'representation': 'source_spans'}]}
        jsonschema.validate({'lift_reader': wire, 'blocks': []}, proposal_schema(plan, 1))
        new = Skill.from_dict(compile_scheduled_lift(plan, wire, Library(skills={old.id: old}))[0]['new'])
        self.assertEqual(new.procedure, old.procedure)
        self.assertEqual(new.reads[-1]['fields']['p']['representation'], 'source_spans')
        boolean = helper();plan.update(old_hash=boolean.hash)
        with self.assertRaisesRegex(ValueError, 'Source-fragment fields'):
            compile_scheduled_lift(plan, wire, Library(skills={boolean.id: boolean}))

    def test_existing_semantic_read_messages_remain_byte_identical_to_actual_request(self):
        folder = self.report / 'semantic_rule_update_attempt/raw/calls'
        for path in sorted(folder.glob('*/wire_request.json')):
            request = json.loads(path.with_name('request.json').read_text())
            payload = json.loads(base64.b64decode(json.loads(path.read_text())['body_b64']))
            task = json.loads(payload['messages'][1]['content'])['task']
            if 'permitted_representative_classes' not in task.get('fields', {}):continue
            captured = []
            class Capture(Exception):pass
            reads = FrozenReads(None)
            def generate(*args, **kwargs):captured.append(kwargs);raise Capture()
            reads.generate = generate
            source = self.sources[request['source']]
            with self.assertRaises(Capture):
                reads.read(source, source['views'][0], question=task['read_question'], fields=task['fields'],
                    locator=task['source_locator'], purpose=request['purpose'], require_rule_support=True,
                    invocation_arguments=task.get('invocation_arguments'))
            args = captured[0]
            self.assertEqual(render_messages(args['system'], args['content'], args['schema']), payload['messages'])
            return
        self.fail('No retained actual semantic READ request found')


if __name__ == '__main__':unittest.main()
