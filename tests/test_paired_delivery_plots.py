"""Only constructed display fixtures;these are not research curve results."""
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest

from legal_skill_guard.paired_delivery_plots import plot_curves
from legal_skill_guard.paired_interfaces.formal_design import ARMS, CURVES


def fixture_rows():
    return [{'dataset': 'CONSTRUCTED_fixture', 'partition': 'dev', 'arm': arm, 'batch': batch,
        'mother_macro': .2 + batch / 16 + index / 40,
        'mother_resampling': {'interval': [.15 + batch / 16 + index / 40, .25 + batch / 16 + index / 40]}}
        for index, arm in enumerate(ARMS) for batch in CURVES]


class DeliveryPlotTests(unittest.TestCase):
    def test_vectors_and_600dpi_png_preserve_every_unsmoothed_actual_table_point(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows = fixture_rows(); before = deepcopy(rows)
            manifest = plot_curves(rows, tmp)
            self.assertEqual(rows, before)
            self.assertEqual(len(manifest['rendered_points']), 28)
            self.assertEqual({(r['arm'], r['batch']): r['value'] for r in manifest['rendered_points']},
                             {(r['arm'], r['batch']): r['mother_macro'] for r in rows})
            self.assertEqual(len(manifest['files_sha256']), 2)
            self.assertFalse(manifest['smoothing'])
            from PIL import Image
            with Image.open(Path(tmp) / 'CONSTRUCTED_fixture_DEV.png') as image:
                self.assertTrue(max(image.size) < 8000)
                self.assertAlmostEqual(image.info['dpi'][0], 600, places=1)
            self.assertTrue((Path(tmp) / 'CONSTRUCTED_fixture_DEV.pdf').read_bytes().startswith(b'%PDF'))

    def test_partial_curve_cannot_be_filled_with_zero_or_rendered(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'All seven'):
                plot_curves(fixture_rows()[:-1], tmp)
            self.assertEqual(list(Path(tmp).iterdir()), [])


if __name__ == '__main__':
    unittest.main()
