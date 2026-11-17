"""Prevent paid formal work from silently treating recorded exposure as fresh."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from experiments import two_method_formal_study as formal
from experiments.two_method_heldout_exposure_gate import (
    KNOWN_INCIDENT, HeldoutExposureError, assert_unexposed_cohorts, inspect_exposure)


class HeldoutExposureGateTests(unittest.TestCase):
    def event(self, root, name, keys):
        p = Path(root) / (name + '.json')
        p.write_text(json.dumps({'incident_id': name,
                                'conservative_affected_cohorts': {'test': {'sources': keys}}}))

    def test_exposure_cannot_be_reset_by_renaming_or_moving_cohorts(self):
        with TemporaryDirectory() as root:
            self.event(root, 'one', ['old-test', 'old-dev'])
            lock = {'sources': {'dev': ['old-test'], 'test': ['old-dev']}}
            receipt = inspect_exposure(lock, root)
            self.assertEqual(receipt['affected_counts'], {'dev': 1, 'test': 1})
            with self.assertRaises(HeldoutExposureError): assert_unexposed_cohorts(lock, root)

    def test_all_incidents_accumulate_without_double_counting(self):
        with TemporaryDirectory() as root:
            self.event(root, 'one', ['a', 'b']); self.event(root, 'two', ['a', 'c'])
            lock = {'sources': {'dev': ['a'], 'test': ['b', 'c']}}
            receipt = inspect_exposure(lock, root)
            self.assertEqual(receipt['affected_counts'], {'dev': 1, 'test': 2})
            self.assertEqual(len(receipt['incidents']), 2)

    def test_unrelated_fresh_identity_is_not_marked_exposed(self):
        with TemporaryDirectory() as root:
            self.event(root, 'one', ['old'])
            receipt = assert_unexposed_cohorts({'sources': {'dev': ['fresh-dev'], 'test': ['fresh-test']}}, root)
            self.assertTrue(receipt['heldout_source_cohorts_unexposed'])

    def test_malformed_exposure_identity_fails_closed(self):
        with TemporaryDirectory() as root:
            self.event(root, 'one', [None])
            with self.assertRaises(ValueError):
                assert_unexposed_cohorts({'sources': {'dev': [], 'test': []}}, root)

    def test_actual_original_cohorts_stop_before_prepare_clients_and_study_activation(self):
        with patch.object(formal, 'prepare', side_effect=AssertionError('preparation reached')):
            with self.assertRaisesRegex(HeldoutExposureError, 'DEV72/TEST136'):
                formal.run()

    def test_known_exposure_survives_missing_ignored_artifact_directory(self):
        event = json.loads(KNOWN_INCIDENT.read_text())
        key = event['conservative_affected_cohorts']['test']['sources'][0]
        with TemporaryDirectory() as root:
            with self.assertRaises(HeldoutExposureError):
                assert_unexposed_cohorts({'sources': {'dev': [], 'test': [key]}}, Path(root) / 'absent')


if __name__ == '__main__': unittest.main()
