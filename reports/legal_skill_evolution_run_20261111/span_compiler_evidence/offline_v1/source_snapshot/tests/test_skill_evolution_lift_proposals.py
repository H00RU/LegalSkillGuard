"""Operator wiring and safety only; synthetic fixtures are not method evidence."""
from copy import deepcopy
from dataclasses import asdict
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import jsonschema

from legal_skill_guard.skill_evolution.lift_proposals import schedule_lift, compile_scheduled_lift
from legal_skill_guard.skill_evolution.objects import Library, Skill, coupled_blocks
from legal_skill_guard.skill_evolution.proposal_batch import prepare_context
from legal_skill_guard.skill_evolution.teacher import proposal_schema
from legal_skill_guard.rr.checkpoint import immutable_json
from tests.test_skill_evolution_teacher_batch import fixture_study, ledger


def old_skill():
    origin = {'source_id': 'parent_0', 'view_id': 'native', 'quote': 'Fixture material only.'}
    return Skill(id='bound', intent='Fixture only',
        procedure='def apply(inputs, premises):\n    record = {"limit": premises["limit"], "scope": premises["scope"]}\n    return {"answer": "Entailment" if record["limit"] > 0 and record["scope"] else "Contradiction"}\n',
        inputs={}, outputs={'answer': {'type': 'string', 'description': 'Fixture answer'}},
        premises={n: {'mode': 'constant', 'type': t, 'value': v, 'origin': origin}
                  for n, t, v in [('limit', 'integer', 5), ('scope', 'boolean', True)]},
        reads=(), semantic_records=(), source_obligations=(), source_provenance=(origin,)).validate()


def reader():
    return {'question': 'Read the currently supplied rule record.', 'source_locator': 'Current rule text',
            'fields': [{'name': 'limit', 'question': 'What is the current limit?'},
                       {'name': 'scope', 'question': 'Does the current provision cover the stated category?'}]}


def row():
    return {'source': 'parent_16', 'selection_grade': 0,
            'views': [{'score': {'grade': 0},
                       'execution': {'events': [{'kind': 'APPLY', 'skill_id': 'bound'}]}}]}


class LiftProposalTests(unittest.TestCase):
    def test_directly_used_constant_needs_no_invented_coupling_record(self):
        from dataclasses import replace
        old = replace(old_skill(), semantic_records=(), procedure=(
            'def apply(inputs, premises):\n'
            '    return {"answer": "Entailment" if premises["limit"] > 0 and '
            'premises["scope"] else "Contradiction"}\n')).validate()
        self.assertEqual(coupled_blocks(old), [('limit',), ('scope',)])
        lib = Library(skills={old.id: old})
        plan = schedule_lift(lib, [row()], 'Full')
        self.assertEqual(plan['premises'], ['limit'])
        wire = reader();wire['fields'] = wire['fields'][:1]
        new = Skill.from_dict(compile_scheduled_lift(plan, wire, lib)[0]['new'])
        self.assertEqual(new.procedure, old.procedure)
        self.assertEqual(new.premises['scope'], old.premises['scope'])

    def test_schedules_only_actual_attempt_and_dedicated_arms(self):
        lib = Library(skills={'bound': old_skill()})
        for arm in ('LiftOnly', 'Full', 'Lift+GenericJoint'):
            self.assertEqual(schedule_lift(lib, [row()], arm)['premises'], ['limit', 'scope'])
        for arm in ('NoSkill', 'FreeEvolution', 'CoRevOnly', 'AllPorts+CoRev'):
            self.assertIsNone(schedule_lift(lib, [row()], arm))
        unused = row();unused['views'] = []
        self.assertIsNone(schedule_lift(lib, [unused], 'Full'))
        correct = row();correct['selection_grade'] = 1
        self.assertIsNone(schedule_lift(lib, [correct], 'Full'))

    def test_static_native_mismatch_does_not_trigger_a_useless_lift(self):
        trace = row();trace['views'][0]['execution'] = {'failed_candidates': [
            {'skill_id': 'bound', 'static_proof': {'incompatible': True}}]}
        self.assertIsNone(schedule_lift(Library(skills={'bound': old_skill()}), [trace], 'Full'))

    def test_wrong_parent_does_not_implicate_a_skill_on_its_correct_view(self):
        trace = row();trace['views'][0]['score']['grade'] = 1
        trace['views'].append({'score': {'grade': 0}, 'execution': {'events': []}})
        self.assertIsNone(schedule_lift(Library(skills={'bound': old_skill()}), [trace], 'Full'))

    def test_small_wire_compiles_without_repeating_or_mutating_program(self):
        old = old_skill();lib = Library(skills={old.id: old});before = deepcopy(asdict(old))
        plan = schedule_lift(lib, [row()], 'Full')
        revised = Skill.from_dict(compile_scheduled_lift(plan, reader(), lib)[0]['new'])
        self.assertEqual(revised.procedure, old.procedure)
        self.assertEqual((revised.inputs, revised.outputs), (old.inputs, old.outputs))
        self.assertEqual(asdict(old), before)
        self.assertEqual(revised.version, old.version + 1)
        self.assertTrue(all('value' not in p and p['mode'] == 'read' for p in revised.premises.values()))
        self.assertEqual(revised.reads[0]['fields']['limit']['type'], 'integer')

    def test_missing_duplicate_extra_fields_and_stale_version_are_rejected(self):
        lib = Library(skills={'bound': old_skill()});plan = schedule_lift(lib, [row()], 'Full')
        for fields in ([reader()['fields'][0]], [reader()['fields'][0]] * 2,
                       reader()['fields'] + [{'name': 'extra', 'question': 'Invented?'}]):
            bad = reader();bad['fields'] = fields
            with self.assertRaises(ValueError):compile_scheduled_lift(plan, bad, lib)
        stale = dict(plan, old_hash='stale')
        with self.assertRaises(ValueError):compile_scheduled_lift(stale, reader(), lib)

    def test_schema_requires_the_scheduled_reader_and_respects_remaining_slots(self):
        plan = schedule_lift(Library(skills={'bound': old_skill()}), [row()], 'Full')
        schema = proposal_schema(plan, 1)
        jsonschema.validate({'lift_reader': reader(), 'blocks': []}, schema)
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate({'lift_reader': None, 'blocks': []}, schema)
        jsonschema.validate({'lift_reader': None, 'blocks': []}, proposal_schema(None, 3))

    def test_host_candidate_shares_slots_and_invalid_reader_is_recorded(self):
        with TemporaryDirectory() as temporary:
            folder = Path(temporary);study = fixture_study(folder, ledger(folder / 'fixture.sqlite'))
            lib = Library(skills={'bound': old_skill()});lib.save(study.library_path('Full', 1))
            baseline = study.parent
            def parent(key, library, **kwargs):
                result = baseline(key, library)
                result['views'] = row()['views']
                return result
            study.parent = parent
            path = folder / 'Full/initial_B2.json'
            path.unlink()  # Replace this test fixture, never a real checkpoint.
            immutable_json(path, {'binding': {'arm': 'Full', 'batch': 2,
                'source_ids': study.batches[1], 'library_hash': lib.hash},
                'results': [parent(key, lib) for key in study.batches[1]]})
            with patch('legal_skill_guard.skill_evolution.proposal_batch.patterns.candidates',
                       return_value=[{'pattern_id': 'fixture', 'revisions': []}]):
                context = prepare_context(study, 'Full', 2)
            self.assertEqual(len(context['queue']), 2)
            self.assertIsNotNone(context['planned_lift'])
            response = {'value': {'lift_reader': None, 'blocks': []}, 'request_sha256': 'fixture'}
            with patch('legal_skill_guard.skill_evolution.study.propose_context', return_value=response), \
                    redirect_stdout(StringIO()):
                receipt = study.update('Full', 2)
            self.assertIsNone(receipt['selected_mask'])
            saved = Library.load(study.library_path('Full', 2))
            self.assertIn('explicit current-source reader', saved.provisional_edits[0]['error'])
            self.assertEqual(saved.provisional_edits[0]['planned_lift']['old_hash'], old_skill().hash)


if __name__ == '__main__':unittest.main()
