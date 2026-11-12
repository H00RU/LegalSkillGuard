"""Meaningful runtime and data isolation checks before any physical generation."""
from dataclasses import asdict, replace
import json
import base64
import hashlib
from pathlib import Path
import subprocess
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from legal_skill_guard.skill_evolution.objects import Skill, Library, coupled_blocks
from legal_skill_guard.skill_evolution.teacher import (validate_grounding, prune_unobserved_premise_metadata,
    compile_block, skill_from_wire)
from legal_skill_guard.skill_evolution.runtime import (execute_helper, SkillRuntime, render_messages,
    aligned_array_ports, FrozenReads)
from legal_skill_guard.skill_evolution.native import answer_wire_schema, decode_answer, restore_enum_transport, source_spans
from legal_skill_guard.skill_evolution.controlled import add_controlled
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.clients import FrozenTeacher
from legal_skill_guard.skill_evolution.clients import FrozenExecutor, GenerationHold
from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.skill_evolution.patterns import instantiate_edit
from legal_skill_guard.skill_evolution.revisions import trigger_revision_reachability
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
    def test_indexed_replay_keeps_earliest_wire_identity_and_rechecks_ledger(self):
        with tempfile.TemporaryDirectory() as folder:
            ledger = fixture_ledger(folder)
            client = object.__new__(FrozenExecutor)
            client.config = {'enable_thinking': False, 'model': 'Qwen/Qwen3-8B',
                'temperature': .6, 'top_p': .95, 'top_k': 20, 'max_tokens': 8192, 'seed': 45}
            client.ledger, client.artifacts = ledger, Path(folder) / 'current'
            prior = Path(folder) / 'prior'
            client.exact_replay_roots = [prior]
            messages = [{'role': 'user', 'content': 'fixture'}]
            schema = {'type': 'object', 'properties': {'a': {'type': 'boolean'}, 'b': {'type': 'boolean'}}}
            payload = client.payload(messages=messages, thinking=False, schema=schema)
            wire = json.dumps(payload, ensure_ascii=False).encode()
            for i in (1, 2):
                identity = 'fixture:old' + str(i)
                reserved = ledger.reserve(identity, role='executor', purpose='skill_actor', source='train',
                    request={'thinking': False, 'fixture': i})
                ledger.finish(identity, status='completed', result={'content': str(i), 'request_hash': reserved['request_hash']})
                dest = prior / 'calls' / str(i)
                dest.mkdir(parents=True)
                (dest / 'request.json').write_text(json.dumps({'id': identity, 'source': 'train',
                    'purpose': 'skill_actor', 'request_hash': reserved['request_hash']}))
                (dest / 'wire_request.json').write_text(json.dumps({'body_b64': base64.b64encode(wire).decode(),
                    'body_sha256': hashlib.sha256(wire).hexdigest()}))
            args = {'source': 'train', 'purpose': 'skill_actor', 'messages': messages, 'thinking': False, 'schema': schema}
            first = client.generate('fixture:new1', **args)
            self.assertEqual(first['reused_physical_call_id'], 'fixture:old1')
            with patch.object(Path, 'glob', side_effect=AssertionError('Repeated historical filesystem scan')):
                self.assertEqual(client.generate('fixture:new2', **args)['content'], '1')
            reordered = {**schema, 'properties': dict(reversed(list(schema['properties'].items())))}
            with patch('legal_skill_guard.rr.client.ExecutorClient.generate', return_value={'cache_miss': True}):
                self.assertEqual(client.generate('fixture:new3', **(args | {'schema': reordered})), {'cache_miss': True})
            with ledger.transaction() as db:
                self.assertEqual(db.execute('select count(*) from calls').fetchone()[0], 2)
                db.execute('update calls set result=? where id=?', (json.dumps({'request_hash': 'tampered'}), 'fixture:old1'))
            with self.assertRaises(BudgetError):client.generate('fixture:new4', **args)

    def test_retained_unique_draft_installs_as_creation_without_fictitious_revision(self):
        origin = {'source_id': 'fixture', 'view_id': 'v', 'quote': 'literal source'}
        raw = {'id': 'draft', 'intent': 'fixture', 'procedure': helper().procedure,
            'inputs': [{'name': 'a', 'type': 'boolean', 'mode': 'read', 'question': 'A', 'field': 'a', 'skill_id': None}],
            'outputs': [{'name': 'answer', 'type': 'boolean', 'description': 'fixture'}],
            'premises': [{'name': 'p', 'type': 'boolean', 'mode': 'constant', 'value': True,
                'origin': origin, 'question': 'P', 'read_id': None, 'field': None}],
            'reads': [], 'semantic_records': [], 'source_obligations': [], 'source_provenance': [origin], 'version': 1}
        ancestor = skill_from_wire(raw)
        library = Library(provisional_edits=[{'revisions': [{'new': asdict(ancestor)}]}])
        proposal = {'revisions': [{'operation': 'revise', 'skill': {**raw, 'version': 2}}]}
        sources = {'fixture': {'views': [{'id': 'v', 'public': {'source_text': 'literal source'}}]}}
        actual = compile_block(proposal, library, sources, 'Full')[0]
        self.assertEqual((actual['operation'], actual['old_hash'], actual['new']['version']), ('create', None, 1))
        self.assertEqual(actual['new']['procedure'], raw['procedure'])
        self.assertFalse(actual['representation_adaptation']['retained_draft_installation']['counts_as_existing_skill_revision'])
        with self.assertRaises(ValueError):compile_block(proposal, Library(), sources, 'Full')
        competing = replace(ancestor, intent='different recorded draft with the same ID/version')
        library.provisional_edits.append({'revisions': [{'new': asdict(competing)}]})
        with self.assertRaises(ValueError):compile_block(proposal, library, sources, 'Full')

    def test_reader_without_any_premise_binding_is_not_executed(self):
        skill = replace(helper(), reads=({'id': 'unused', 'question': 'irrelevant', 'fields': {'unused': {'type': 'object'}}},))
        calls = []
        def read(*args, **kwargs):
            calls.append(kwargs['fields'])
            return {'a': True}, {'kind': 'READ_LOCAL', 'fields': {}}
        runtime = SkillRuntime(SimpleNamespace(read=read))
        actual = runtime.run({'key': 'fixture'}, {'id': 'v', 'answer_schema': {'type': 'boolean'}},
            Library(skills={skill.id: skill}), retrieved=[skill.id], fallback=False)
        self.assertTrue(actual['core_executed'])
        self.assertEqual(calls, [{'a': {'type': 'boolean', 'question': 'A'}}])

    def test_unreached_unknown_is_never_filled_and_reached_unknown_still_fails(self):
        branch = replace(helper(), procedure=('def apply(inputs, premises):\n'
            '    if inputs["a"]:\n        return {"answer": premises["p"]}\n'
            '    return {"answer": False}\n'))
        self.assertEqual(execute_helper(branch, {'a': False}, {}, unresolved_premises=['p']), {'answer': False})
        with self.assertRaisesRegex(ValueError, 'KeyError'):
            execute_helper(branch, {'a': True}, {}, unresolved_premises=['p'])
        with self.assertRaises(ValueError):execute_helper(branch, {'a': False}, {})
        with self.assertRaises(ValueError):
            execute_helper(branch, {'a': False}, {'p': True}, unresolved_premises=['p'])
        for body in ('x = premises', 'x = len(premises)', 'x = str(premises)',
                     'x = "p" in premises', 'premises["p"] = True', 'del premises["p"]'):
            program = ('def apply(inputs, premises):\n    ' + body + '\n'
                '    if inputs["a"]:\n        return {"answer": premises["p"]}\n'
                '    return {"answer": False}\n')
            with self.assertRaises(ValueError):
                execute_helper(replace(branch, procedure=program), {'a': False}, {}, unresolved_premises=['p'])

    def test_partial_read_keeps_unknown_evidence_and_requires_support_for_known_values(self):
        reads = FrozenReads(None)
        response = {'a': {'status': 'known', 'value': False, 'support_ids': [0]},
                    'b': {'status': 'unknown', 'value': None, 'support_ids': []}}
        reads.generate = lambda *args, **kwargs: (json.loads(json.dumps(response)), {'call_id': 'fixture'})
        args = ({'key': 'fixture', 'dataset': 'fixture'},
                {'id': 'v', 'public': {'source_text': 'A does not apply.'}})
        options = {'question': 'Read A and B', 'fields': {n: {'type': 'boolean'} for n in response},
                   'locator': 'source', 'purpose': 'fixture'}
        values, event = reads.read(*args, **options, allow_unresolved=True)
        self.assertEqual(values, {'a': False})
        self.assertEqual(event['unresolved_fields'], ['b'])
        self.assertIsNone(event['fields']['b']['value'])
        with self.assertRaises(ValueError):reads.read(*args, **options)
        response['a']['support_ids'] = []
        with self.assertRaisesRegex(ValueError, 'no selected current-source support'):
            reads.read(*args, **options, allow_unresolved=True)

    def test_trigger_pruning_keeps_dependencies_from_every_mixed_version(self):
        consumer = replace(helper(), id='consumer')
        producer = replace(helper(), id='new_producer')
        old = Library(skills={'consumer': consumer})
        new = Library(skills={'consumer': consumer, 'new_producer': producer})
        roots = {'source': {'view': ['consumer']}}
        proof = trigger_revision_reachability(old, new, roots, ['source'], ['new_producer'])
        self.assertFalse(proof['any_changed_reachable'])
        # The full-new graph no longer uses this producer; a mixed version
        # with the old consumer still does. It must remain eligible.
        old.skills['consumer'] = replace(consumer, inputs={'a': {'type': 'boolean',
            'mode': 'skill', 'skill_id': 'new_producer', 'field': 'answer'}})
        proof = trigger_revision_reachability(old, new, roots, ['source'], ['new_producer'])
        self.assertTrue(proof['any_changed_reachable'])
        self.assertIn('new_producer', proof['trigger_views'][0]['reachable_union_old_new'])
        self.assertTrue(trigger_revision_reachability(old, new, roots, ['source'], ['consumer'])['any_changed_reachable'])

    def test_array_alignment_comes_from_actual_uses_and_never_fills_values(self):
        program = ('def apply(inputs, premises):\n    keys = premises["keys"]\n'
            '    amounts = premises["amounts"]\n    total = 0\n'
            '    for j in range(len(keys)):\n        total = total + amounts[j]\n'
            '    return {"answer": total}\n')
        skill = replace(helper(), procedure=program, inputs={},
            premises={n: {'type': 'array', 'mode': 'constant', 'value': [], 'origin': {'source': 'fixture'}}
                      for n in ('keys', 'amounts')})
        self.assertEqual(aligned_array_ports(skill), [(('premises', 'keys'), [('premises', 'amounts')])])
        observes_length = replace(skill, procedure=program.replace('total = 0', 'total = len(amounts)'))
        self.assertEqual(aligned_array_ports(observes_length), [])
        direct_other_access = replace(skill, procedure=program.replace('total = 0', 'total = premises["amounts"][4]'))
        self.assertEqual(aligned_array_ports(direct_other_access), [])
        deletes = replace(skill, procedure=program.replace('total = total + amounts[j]', 'del amounts[j]'))
        self.assertEqual(aligned_array_ports(deletes), [])
        changes_index = replace(skill, procedure=program.replace('total = total + amounts[j]', 'j = j + 1\n        total = total + amounts[j]'))
        self.assertEqual(aligned_array_ports(changes_index), [])
        calls = []
        reads = FrozenReads(None)
        def generate(source, view, **args):
            calls.append(args)
            values = {'keys': ['a', 'b']} if len(calls) == 1 else {'amounts': [3, 5]}
            response = {n: {'status': 'known', 'value': v, 'support_ids': [0]} for n, v in values.items()}
            import jsonschema
            jsonschema.validate(response, args['schema'])
            return response, {'call_id': str(len(calls)), 'physical_call_id': str(len(calls)), 'usage': {}}
        reads.generate = generate
        values, event = reads.read({'key': 'fixture', 'dataset': 'fixture'},
            {'id': 'v', 'public': {'source_text': 'a has 3; b has 5.'}}, question='Read the current pairs.',
            fields={n: {'type': 'array', 'question': n} for n in ('keys', 'amounts')},
            locator='source', purpose='fixture', alignment=('keys', ['amounts']))
        self.assertEqual(values, {'keys': ['a', 'b'], 'amounts': [3, 5]})
        shape = calls[1]['schema']['properties']['amounts']['properties']['value']
        self.assertEqual((shape['minItems'], shape['maxItems']), (2, 2))
        self.assertEqual(calls[1]['content']['alignment_anchor_values'], {'keys': ['a', 'b']})
        self.assertEqual(event['physical_call_ids'], ['1', '2'])

    def test_unused_evidence_port_recovery_preserves_observable_program_behavior(self):
        raw = {'procedure': 'def apply(inputs, premises):\n    return {"answer": premises["cap"]}\n',
            'premises': [{'name': 'cap', 'value': 17}, {'name': 'rule_quotes', 'value': None}],
            'reads': [{'id': 'read', 'fields': [{'name': 'cap'}, {'name': 'quote'}],
                'bindings': [{'premise': 'cap', 'field': 'cap'}, {'premise': 'rule_quotes', 'field': 'quote'}]}],
            'semantic_records': [{'ports': ['cap', 'rule_quotes']}], 'source_obligations': []}
        normalized, removed = prune_unobserved_premise_metadata(raw)
        self.assertEqual([p['name'] for p in removed], ['rule_quotes'])
        self.assertEqual(normalized['procedure'], raw['procedure'])
        self.assertEqual(normalized['premises'], raw['premises'][:1])
        namespace = {}
        exec(raw['procedure'], {}, namespace)
        for evidence in (None, ['literal source'], ['different evidence']):
            self.assertEqual(namespace['apply']({}, {'cap': 17, 'rule_quotes': evidence}),
                             namespace['apply']({}, {'cap': 17}))
        # This superficially unused port affects len(premises); never prune it.
        observable = {**raw, 'procedure': 'def apply(inputs, premises):\n    return {"answer": premises["cap"] + len(premises)}\n'}
        self.assertEqual(prune_unobserved_premise_metadata(observable), (observable, []))
        alias = {**raw, 'procedure': 'def apply(inputs, premises):\n    p = premises\n    return {"answer": p["cap"]}\n'}
        self.assertEqual(prune_unobserved_premise_metadata(alias), (alias, []))
        semantic = {**raw, 'source_obligations': [{'port': 'rule_quotes'}]}
        self.assertEqual(prune_unobserved_premise_metadata(semantic), (semantic, []))

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
        self.assertEqual(coupled_blocks(current), [('p',)])
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
            teacher = object.__new__(FrozenTeacher)
            teacher.artifacts = Path(folder)
            with self.assertRaises(GenerationHold):
                teacher.propose('fixture', source_ids=['train'], system_prompt='', user_prompt='', output_schema={})

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
