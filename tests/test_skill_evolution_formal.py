"""The fixed study schedule and native permission boundaries stay explicit."""
from collections import Counter
import json
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from experiments.legal_skill_evolution_formal import schedule, ARMS, CURVE_ARMS
from legal_skill_guard.skill_evolution.study import Study


class FormalTests(unittest.TestCase):
    def test_formal_constructor_keeps_DEV_annotations_out_of_learning_and_never_opens_TEST(self):
        root = Path(__file__).resolve().parents[1]
        profile = json.loads((root / 'configs/legal_skill_evolution_repair_v13_20261111.json').read_text())
        profile['arms'] = list(ARMS)
        original_read = Path.read_text
        def guarded_read(path, *args, **kwargs):
            if 'sealed_test' in path.parts:raise AssertionError('Unfrozen formal code opened TEST')
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded_read), \
             patch('legal_skill_guard.skill_evolution.study.EvolutionLedger'), \
             patch('legal_skill_guard.skill_evolution.study.FrozenExecutor', return_value=SimpleNamespace()), \
             patch('legal_skill_guard.skill_evolution.study.FrozenTeacher'):
            study = Study(root, profile, stage='formal')
        self.assertEqual(len(study.records), 128)
        self.assertEqual(len(study.dev_records), 40)
        self.assertEqual(set(study.grading) & set(study.dev_grading), set())
        self.assertEqual(set(study.records), set(study.source_ids['train']))
        self.assertEqual(set(study.dev_records), set(study.source_ids['dev']))
        with self.assertRaises(KeyError):study.feedback([study.source_ids['dev'][0]], {})

    def test_fixed_schedule_freezes_all_initial_answers_before_any_batch_update(self):
        actions = schedule()
        for batch in range(1, 9):
            current = [a for a in actions if a[2] == batch]
            initials = [a[1] for a in current if a[0] == 'initial']
            updates = [a[1] for a in current if a[0] == 'update']
            self.assertEqual(initials, list(ARMS))
            self.assertEqual(updates, list(ARMS))
            self.assertLess(max(i for i, a in enumerate(current) if a[0] == 'initial'),
                            min(i for i, a in enumerate(current) if a[0] == 'update'))
        for arm in ARMS:
            points = [b for a, name, b in actions if a == 'dev' and name == arm]
            self.assertEqual(points, list(range(9)) if arm in CURVE_ARMS else [0, 8])

    def test_formal_order_covers_native_parents_once_and_does_not_add_controlled_views(self):
        root = Path(__file__).resolve().parents[1]
        manifest = json.loads((root / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json').read_text())
        order = []
        for batch in manifest['source_sequence']:
            keys = [r['source_key'] for r in batch['sources']]
            self.assertEqual(len(keys), 16)
            counts = Counter(r['dataset'] for r in batch['sources'])
            self.assertEqual(counts['OpenExempt'], 4)
            self.assertTrue(all(counts[d] == 3 for d in counts if d != 'OpenExempt'))
            order.extend(keys)
        self.assertEqual(len(order), 128)
        self.assertEqual(len(set(order)), 128)
        train = json.loads((root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json').read_text())
        self.assertEqual(set(order), {r['key'] for r in train})
        self.assertEqual(sum(len(r['views']) for r in train), 280)
        self.assertFalse(any(v.get('controlled_diagnostic') for r in train for v in r['views']))


if __name__ == '__main__':unittest.main()
