"""Synthetic accounting regressions; no method or held-out validation."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from reports.legal_skill_evolution_run_20261111 import frozen_cost_footprints as report


class FrozenCostAccounting(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lsg-cost-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = self.root / 'report'
        self.out.mkdir()
        self.frozen = self.root / 'frozen'
        self.frozen.mkdir()
        self.profile = self.root / 'formal.json'
        self.write(self.profile, {'artifacts': 'formal'})
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for key, value in (('ROOT', self.root), ('REPORT', self.out), ('FROZEN', self.frozen), ('FORMAL_PROFILE', self.profile)):
            self.stack.enter_context(patch.object(report, key, value))

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def invoke(self):
        with redirect_stdout(io.StringIO()):
            report.main()
        path = self.out / 'frozen_cost_footprints.json'
        return json.loads(path.read_text()) if path.exists() else None

    def fixture(self, transfer=False):
        prefix = 'legal_skill_evolution_frozen_fixture:'
        shared, full, failed, extra = [prefix + c * 64 for c in 'abcd']
        train, teacher, dev = ('training_response', 'training_teacher', 'DEV_response')
        self.ids = shared, full, failed, extra, train, teacher, dev
        self.write(self.root / 'configs/legal_skill_evolution_frozen_v1_20261111.json', {
            'run_id': prefix[:-1], 'freeze': {'artifact_sha256': 'fixture-freeze'}})
        self.write(self.frozen / 'TEST_completed.json', {'freeze_artifact_sha256': 'fixture-freeze',
            'completed_utc': '1970-01-01T00:01:40+00:00', 'result_file_sha256': {}})
        book = self.root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        book.parent.mkdir(parents=True)
        with sqlite3.connect(book) as db:
            db.execute('create table calls(id text,role text,status text,reserved_at real,result text)')
            for identity, role, status, at in ((shared, 'executor', 'completed', 10),
                    (full, 'executor', 'completed', 20), (failed, 'executor', 'failed', 30),
                    (extra, 'executor', 'completed', 150), (train, 'executor', 'completed', 1),
                    (teacher, 'teacher', 'completed', 2), (dev, 'executor', 'completed', 3)):
                db.execute('insert into calls values(?,?,?,?,?)', (identity, role, status, at,
                    json.dumps({'usage': {'prompt_tokens': 10, 'completion_tokens': 5}, 'elapsed_seconds': 2})))
        points = {}
        for arm in report.ARMS:
            for number in range(160):
                references = [shared, shared] + ([full] if arm == 'Full' else [])
                self.write(self.frozen / 'predictions' / arm / f'{number}.json', {'physical_call_ids': references})
            self.write(self.root / 'formal/dev' / arm / 'B8.json', {'physical_call_id': dev})
            learning = [train, dev] + ([teacher] if arm != 'NoSkill' else [])
            points[arm] = [{'batch': 8, 'batch_distinct_response_ids': learning}]
        self.write(self.out / 'formal_cost_footprints.json', {'per_batch_observed_response_footprints': points,
            'interpretation': 'Shared response use is not independent standalone spending.'})
        if transfer:
            self.write(self.frozen / 'transfer/completed.json', {
                'freeze_artifact_sha256': 'fixture-freeze', 'result_sha256': {}})
            for dataset in range(5):
                for number in range(32):
                    self.write(self.frozen / 'predictions/Full_foreign_off' / str(dataset) / f'{number}.json',
                        {'physical_call_ids': [shared, extra, extra]})

    def test_unfinished_matrix_does_not_open_any_input(self):
        with patch.object(report, 'load', side_effect=AssertionError('No input should be opened')):
            self.assertIsNone(self.invoke())

    def test_shared_costs_failures_and_DEV_exclusion(self):
        self.fixture()
        shared, full, failed, extra, train, teacher, dev = self.ids
        actual = self.invoke()
        self.assertEqual(actual['matrix_physical_dispatches_counted_once']['physical_requests'], 3)
        self.assertEqual(actual['matrix_physical_dispatches_counted_once']['statuses']['executor:failed'], 1)
        per_arm = actual['per_arm_matrix_consumed_response_footprints']
        self.assertEqual(per_arm['Full']['response_ids'], sorted([shared, full]))
        self.assertEqual(per_arm['NoSkill']['response_ids'], [shared])
        self.assertGreater(sum(row['physical_requests'] for row in per_arm.values()), 3)
        self.assertEqual(actual['matrix_dispatches_without_parent_evidence_attribution'], [failed])
        self.assertEqual(len(actual['shared_matrix_responses']), 1)
        self.assertEqual(len(actual['shared_matrix_responses'][0]['used_by_arms']), 7)
        end = actual['per_arm_learning_plus_matrix_consumed_response_footprints_excluding_DEV']
        self.assertEqual(set(end['Full']['response_ids']), {shared, full, train, teacher})
        self.assertEqual(set(end['NoSkill']['response_ids']), {shared, train})
        self.assertTrue(all(dev not in row['response_ids'] for row in end.values()))

    def test_transfer_charges_only_new_physical_dispatches(self):
        self.fixture(transfer=True)
        actual = self.invoke()
        self.assertTrue(actual['transfer_complete'])
        self.assertEqual(actual['additional_transfer_physical_dispatches_counted_once']['response_ids'], [self.ids[3]])
        self.assertEqual(actual['all_frozen_physical_dispatches_counted_once']['physical_requests'], 4)
        self.assertEqual(actual['registered_transfer_target_only_consumed_response_footprint']['physical_requests'], 2)

    def test_frozen_teacher_access_is_not_hidden_in_costs(self):
        self.fixture()
        book = self.root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        with sqlite3.connect(book) as db:
            db.execute('insert into calls values(?,?,?,?,?)',
                ('legal_skill_evolution_frozen_fixture:' + 'e' * 64, 'teacher', 'completed', 50, '{}'))
        with self.assertRaisesRegex(ValueError, 'teacher'):
            self.invoke()


if __name__ == '__main__':
    unittest.main()
