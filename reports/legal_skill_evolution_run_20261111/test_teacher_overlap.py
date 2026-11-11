"""Interval bookkeeping only; these fixtures are not model experiments."""
import unittest
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
from unittest.mock import patch
from . import audit_teacher_overlap as audit
from .audit_teacher_overlap import interval_summary, timestamp


class TeacherOverlapTests(unittest.TestCase):
    def test_touching_intervals_do_not_fake_parallel_invocations(self):
        result = interval_summary([(0, 1), (1, 2), (2, 3)])
        self.assertEqual(result['peak_overlap'], 1)
        self.assertEqual(result['union_seconds'], 3)
        self.assertEqual(result['observed_overlap_factor'], 1)

    def test_overlap_counts_durations_once_and_retains_gaps(self):
        result = interval_summary([(0, 3), (1, 2), (4, 6)])
        self.assertEqual(result['peak_overlap'], 2)
        self.assertEqual(result['union_seconds'], 5)
        self.assertEqual(result['wall_span_seconds'], 6)
        self.assertEqual(result['total_invocation_seconds'], 6)
        self.assertEqual(result['observed_overlap_factor'], 1)

    def test_no_intervals_or_invalid_clock_cannot_be_claimed_as_speedup(self):
        self.assertIsNone(interval_summary([])['observed_overlap_factor'])
        with self.assertRaises(ValueError):interval_summary([(2, 1)])
        with self.assertRaises(ValueError):timestamp('2026-11-11T00:00:00')

    def test_imported_phase_uses_original_physical_namespace(self):
        with TemporaryDirectory() as temporary:
            root=Path(temporary);old=root/'old';current=root/'current';report=root/'report'
            report.mkdir();current.mkdir()
            def save(path,value):
                path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value))
            old_id='legal_skill_evolution_formal_v3_fixture'
            save(root/'prior.json',{'run_id':old_id,'artifacts':'old'})
            save(root/'profile.json',{'run_id':'legal_skill_evolution_formal_v4_fixture','artifacts':'current',
                'exact_replay_profiles':['prior.json'],'teacher':{},'teacher_proposal_workers':2})
            save(root/'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json',
                 {'datasets':{'fixture':{'train':[{'key':'source'}]}}})
            start=timestamp('2026-11-11T00:00:00+00:00')
            arms=['arm'+str(i) for i in range(6)]
            save(current/'teacher_prefetch_B4_started.json',{'started_unix':start,'source_cohorts':{a:['source'] for a in arms}})
            save(current/'teacher_prefetch_B4_completed.json',{'batch':4,'completed_utc':'2026-11-11T00:00:20+00:00'})
            dbpath=root/'artifacts/rr_v2_preflight/research_ledger.sqlite3';dbpath.parent.mkdir(parents=True)
            with sqlite3.connect(dbpath) as db:
                db.execute('create table calls(id,role,status,reserved_at,result)')
                for i,arm in enumerate(arms):
                    identity=old_id+':teacher:'+str(i)
                    save(old/'calls'/audit.digest(identity)/'request.json',
                         {'user_prompt':json.dumps({'batch':4,'arm':arm}),'source_ids':['source'],'config':{}})
                    db.execute('insert into calls values(?,?,?,?,?)',(identity,'teacher','completed',start+i,
                        json.dumps({'invocation':{'started_at':'2026-11-11T00:00:0'+str(i)+'+00:00',
                                                 'finished_at':'2026-11-11T00:00:0'+str(i+1)+'+00:00'}})))
            with patch.multiple(audit,ROOT=root,REPORT=report,PROFILE=root/'profile.json'),redirect_stdout(StringIO()):audit.main()
            result=json.loads((report/'actual_teacher_overlap.json').read_text())['batches'][0]
            self.assertEqual(len(result['teacher_calls']),6)
            self.assertTrue(all(c['physical_ledger_id'].startswith(old_id+':') for c in result['teacher_calls']))
            self.assertEqual(result['executor_dispatches_during_teacher_interval'],0)


if __name__ == '__main__':unittest.main()
