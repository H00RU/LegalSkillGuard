"""Two teacher reservations, fixed-input preparation and zero-call resume."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
from types import SimpleNamespace
import unittest
from legal_skill_guard.skill_evolution.teacher_transport import unpack
from unittest.mock import patch

from legal_skill_guard.rr.ledger import BudgetError
from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.proposal_batch import prefetch_teachers, prepare_context
from legal_skill_guard.skill_evolution.study import Study


def ledger(path, *, run='fixture', workers=2):
    if not path.exists():
        with sqlite3.connect(path) as db:
            db.execute('create table meta (key text primary key,value text)')
            db.execute('insert into meta values (?,?)', ('spec', json.dumps({'fixture_only': True})))
            db.execute('create table calls (id text primary key,role text,purpose text,bucket text,source text,request_hash text,status text,reserved_at real,result text)')
    return EvolutionLedger(path, run_id=run,
        sources={'train': [f'parent_{i}' for i in range(32)], 'dev': ['dev'], 'test': ['test']},
        binding={'fixture': 'same'}, teacher_concurrency=workers)


def fixture_study(folder, budget):
    study = object.__new__(Study)
    study.folder, study.ledger, study.stage = folder, budget, 'formal'
    study.arms = ('NoSkill', 'FreeEvolution', 'LiftOnly', 'CoRevOnly', 'Full', 'Lift+GenericJoint', 'AllPorts+CoRev')
    study.batches = [[f'parent_{i}' for i in range(16)], [f'parent_{i}' for i in range(16, 32)]]
    study.order = sum(study.batches, [])
    study.profile = {'teacher_proposal_workers': 2, 'teacher': {}, 'prior_logical_replay_executions': {}}
    study.records = {key: {'key': key, 'dataset': 'SARA_v2_Binary', 'views': [
        {'id': 'native', 'public': {'text': 'Fixture material only.'},
         'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction']}}]} for key in study.order}
    study.grading = {key: {'native': {'answer': 'Entailment'}} for key in study.order}
    def parent(key, library):return {'source': key, 'dataset': 'SARA_v2_Binary', 'library_hash': library.hash,
        'selection_grade': (int(key.split('_')[1]) % 4) / 4, 'native_grade': 0, 'views': []}
    study.parent = parent
    for arm in study.arms:
        library = Library();library.save(study.library_path(arm, 1))
        immutable_json(folder / arm / 'initial_B2.json', {'binding': {'arm': arm, 'batch': 2,
            'source_ids': study.batches[1], 'library_hash': library.hash},
            'results': [parent(key, library) for key in study.batches[1]]})
    return study


class TeacherBatchTests(unittest.TestCase):
    def test_only_same_run_two_teachers_overlap_and_executor_stays_serial(self):
        with tempfile.TemporaryDirectory() as folder:
            budget = ledger(Path(folder) / 'fixture.sqlite')
            request = lambda n, role='teacher':budget.reserve('fixture:' + n, role=role,
                purpose='skill_teacher' if role == 'teacher' else 'skill_actor', source='parent_0',
                request={} if role == 'teacher' else {'thinking': False})
            self.assertTrue(request('t1')['dispatch']);self.assertTrue(request('t2')['dispatch'])
            with self.assertRaises(BudgetError):request('t3')
            with self.assertRaises(BudgetError):request('e1', 'executor')
            foreign = ledger(Path(folder) / 'fixture.sqlite', run='other')
            with self.assertRaises(BudgetError):
                foreign.reserve('other:t', role='teacher', purpose='skill_teacher', source='parent_0', request={})
            for identity in ('t1', 't2'):budget.finish('fixture:' + identity, status='completed', result={})
            self.assertTrue(request('e1', 'executor')['dispatch'])
            with self.assertRaises(BudgetError):request('e2', 'executor')
            budget.finish('fixture:e1', status='completed', result={})
            self.assertFalse(request('t1')['dispatch'])
            self.assertIsNone(budget.policy['physical_call_caps'])
            with budget.transaction() as db:self.assertEqual(db.execute('select count(*) from calls').fetchone()[0], 3)

    def test_missing_any_arm_initial_answer_blocks_every_teacher_before_context_generation(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);study = fixture_study(root, ledger(root / 'fixture.sqlite'))
            (root / 'AllPorts+CoRev/initial_B2.json').unlink()
            with patch('legal_skill_guard.skill_evolution.proposal_batch.FrozenTeacher') as teacher:
                with self.assertRaisesRegex(ValueError, 'every arm first attempt'):prefetch_teachers(study, 2)
                teacher.assert_not_called()
            self.assertFalse(list(root.glob('*/update_context*')))

    def test_context_keeps_worst_three_and_same_first_five_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);study = fixture_study(root, ledger(root / 'fixture.sqlite'))
            context = prepare_context(study, 'Full', 2)
            self.assertEqual(context['trigger'], ['parent_16', 'parent_20', 'parent_24'])
            self.assertEqual(context['history'], [f'parent_{i}' for i in range(5)])
            self.assertEqual(context['cohort'], context['trigger'] + context['history'])
            self.assertEqual(len(context['queue']), 0)

    def test_six_proposals_peak_at_two_and_resume_does_not_dispatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);budget = ledger(root / 'fixture.sqlite');study = fixture_study(root, budget)
            state = {'active': 0, 'peak': 0, 'calls': 0};lock = threading.Lock();barrier = threading.Barrier(2)
            class Teacher:
                def __init__(self, current, artifacts, config):self.ledger = current
                def propose(self, call_id, **kwargs):
                    request = self.ledger.reserve(call_id, role='teacher', purpose='skill_teacher',
                        source=kwargs['source_ids'][0], request=kwargs)
                    if not request['dispatch']:return request['result']
                    with lock:
                        state['active'] += 1;state['peak'] = max(state['peak'], state['active']);state['calls'] += 1
                    barrier.wait(timeout=5)
                    result = {'value': {'blocks': []}, 'request_sha256': digest(kwargs),
                        'source_ids': kwargs['source_ids'], 'fixture_only': True}
                    self.ledger.finish(call_id, status='completed', result=result)
                    with lock:state['active'] -= 1
                    return result
            with patch('legal_skill_guard.skill_evolution.proposal_batch.FrozenTeacher', Teacher):
                result = prefetch_teachers(study, 2)
                self.assertEqual(state['peak'], 2);self.assertEqual(state['calls'], 6)
                self.assertEqual(result['new_physical_teacher_requests_this_attempt'], 6)
                prefetch_teachers(study, 2);self.assertEqual(state['calls'], 6)
                with budget.transaction() as db:
                    self.assertEqual(db.execute('select role,status,count(*) from calls group by role,status').fetchall(), [('teacher', 'completed', 6)])

    def test_failed_teacher_stops_unsent_jobs_drains_running_worker_and_remains_charged(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);budget = ledger(root / 'fixture.sqlite');study = fixture_study(root, budget)
            barrier = threading.Barrier(2)
            class Teacher:
                def __init__(self, current, artifacts, config):self.ledger = current
                def propose(self, call_id, **kwargs):
                    current = unpack(json.loads(kwargs['user_prompt']));failed = current['arm'] == 'FreeEvolution'
                    self.ledger.reserve(call_id, role='teacher', purpose='skill_teacher', source=kwargs['source_ids'][0], request=kwargs)
                    barrier.wait(timeout=5)
                    if failed:
                        self.ledger.finish(call_id, status='failed', result={'fixture_error': True})
                        raise ValueError('fixture transport failure')
                    # Ensure the failure is observed before the surviving job
                    # finishes, without relying on a timing-only sleep.
                    while True:
                        with self.ledger.transaction() as db:
                            if db.execute("select 1 from calls where status='failed'").fetchone():break
                    result = {'value': {'blocks': []}, 'request_sha256': digest(kwargs), 'source_ids': kwargs['source_ids']}
                    self.ledger.finish(call_id, status='completed', result=result)
                    return result
            with patch('legal_skill_guard.skill_evolution.proposal_batch.FrozenTeacher', Teacher):
                with self.assertRaisesRegex(ValueError, 'fixture transport failure'):prefetch_teachers(study, 2)
            with budget.transaction() as db:
                rows = db.execute('select status,count(*) from calls group by status').fetchall()
                self.assertEqual(rows, [('completed', 1), ('failed', 1)])
            failed = json.loads((root / 'teacher_prefetch_B2_failed.json').read_text())
            self.assertEqual(len(failed['unsent_arms']), 4)
            self.assertFalse((root / 'teacher_prefetch_B2_completed.json').exists())


if __name__ == '__main__':unittest.main()
