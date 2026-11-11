"""Semantic ancestry and actual-use regressions on isolated fixtures."""
from copy import deepcopy
from dataclasses import asdict
from contextlib import contextmanager, redirect_stdout
import io
import json
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from legal_skill_guard.skill_evolution.objects import Skill, Library, digest
from .skill_lineage import accepted_lineage, foreign_off, actual_use


def skill(identity, source, *, dependency=None, version=1):
    inputs = ({'value': {'type': 'string', 'mode': 'skill', 'skill_id': dependency, 'field': 'answer'}}
              if dependency else {})
    return Skill(id=identity, intent='Fixture answer', procedure='def apply(inputs, premises):\n    return {"answer": "fixture"}',
        inputs=inputs, outputs={'answer': {'type': 'string'}}, premises={}, reads=(), semantic_records=(),
        source_obligations=(), source_provenance=({'source_id': source, 'view_id': 'fixture', 'quote': 'Fixture clause.'},),
        version=version).validate()


class SkillLineageTests(unittest.TestCase):
    def test_accepted_ancestry_retains_first_source_after_later_provenance_replacement(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);arm = root / 'Full';arm.mkdir()
            old = Library();old.save(arm / 'B0.json')
            for batch, source in enumerate(('fixture_A', 'fixture_B'), 1):
                current = skill('s', source, version=batch)
                new = Library(skills={'s': current})
                new.save(arm / f'B{batch}.json')
                candidates = arm / f'B{batch}_candidates';candidates.mkdir()
                revision = {'skill_id': 's', 'old_hash': old.skills['s'].hash if old.skills else None,
                            'new_hash': current.hash, 'new': asdict(current),
                            'operation': 'create' if batch == 1 else 'revise'}
                (candidates / '0.json').write_text(json.dumps({'revisions': [revision], 'selected_mask': 1}))
                (arm / f'update_B{batch}.json').write_text(json.dumps({'old_library_hash': old.hash,
                    'new_library_hash': new.hash, 'selected_candidate': 0, 'selected_mask': 1}))
                old = new
            lineage = accepted_lineage(root, 'Full', 2, {'fixture_A': 'A', 'fixture_B': 'B'})
            self.assertEqual(lineage['skills']['s']['first_datasets'], ['A'])
            self.assertEqual(lineage['skills']['s']['ancestral_datasets'], ['A', 'B'])
            masked, receipt = foreign_off(old, lineage, 'B')
            self.assertFalse(masked.skills)
            self.assertEqual(receipt['removed_skills']['s']['reason'], 'foreign_or_mixed_accepted_ancestry')
            broken = json.loads((arm / 'update_B2.json').read_text());broken['selected_mask'] = 0
            (arm / 'update_B2.json').write_text(json.dumps(broken))
            with self.assertRaisesRegex(ValueError, 'acceptance|mask'):
                accepted_lineage(root, 'Full', 2, {'fixture_A': 'A', 'fixture_B': 'B'})

    def test_foreign_removal_closes_over_consumers_without_mutating_original(self):
        library = Library(skills={'p': skill('p', 'a'), 'c': skill('c', 'b', dependency='p'),
                                  'independent': skill('independent', 'b')}, revision_patterns=[{'fixture': True}])
        lineage = {'library_hash': library.hash, 'skills': {
            key: {'ancestral_datasets': [dataset]} for key, dataset in [('p', 'A'), ('c', 'B'), ('independent', 'B')]}}
        before = deepcopy(library)
        masked, receipt = foreign_off(library, lineage, 'B')
        self.assertEqual(set(masked.skills), {'independent'})
        self.assertEqual(receipt['removed_skills']['c']['lost_producers'], ['p'])
        self.assertEqual(library.hash, before.hash)
        self.assertEqual(masked.revision_patterns, before.revision_patterns)

    def test_successful_helper_in_a_fallback_attempt_is_not_final_core_reuse(self):
        library = Library(skills={'p': skill('p', 'a')})
        lineage = {'library_hash': library.hash, 'skills': {'p': {'ancestral_datasets': ['A']}}}
        parent = {'source': 'b', 'dataset': 'B', 'library_hash': library.hash, 'views': [{
            'view': 'fixture', 'score': {'grade': 1, 'correct': True}, 'execution': {
                'events': [{'kind': 'APPLY', 'skill_id': 'p', 'skill_hash': library.skills['p'].hash}],
                'fallback': True, 'core_executed': False}}]}
        result = actual_use(parent, library, lineage)[0]
        self.assertEqual(result['applied_skill_ids'], ['p'])
        self.assertFalse(result['foreign_final_answer_skill_ids'])
        self.assertFalse(result['fully_correct_foreign_core'])
        execution = parent['views'][0]['execution']
        execution.update(fallback=False, core_executed=True, terminal_skill='p')
        self.assertTrue(actual_use(parent, library, lineage)[0]['fully_correct_foreign_core'])
        execution['events'][0]['skill_hash'] = 'wrong-version'
        with self.assertRaisesRegex(ValueError, 'actual frozen skill version'):
            actual_use(parent, library, lineage)

    def test_transfer_cannot_initialize_a_model_before_main_frozen_matrix_completes(self):
        from experiments.legal_skill_evolution_transfer import run
        with tempfile.TemporaryDirectory() as folder:
            with patch('experiments.legal_skill_evolution_frozen.FOLDER', Path(folder)), patch(
                    'experiments.legal_skill_evolution_frozen.FrozenStudy') as initialize:
                with self.assertRaisesRegex(ValueError, 'seven-system TEST matrix'):
                    run()
                initialize.assert_not_called()

    def test_registered_five_dataset_queue_resumes_without_reexecution_and_detects_result_tampering(self):
        from experiments.legal_skill_evolution_transfer import run
        from .native_statistics import DATASETS
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder);(root / 'libraries').mkdir()
            library = Library()
            lineage = {'library_hash': library.hash, 'skills': {}}
            (root / 'Full_accepted_lineage.json').write_text(json.dumps(lineage))
            masks, records, calls = {}, {}, []
            parents = {}
            for dataset in DATASETS:
                masked, masks[dataset] = foreign_off(library, lineage, dataset)
                masked.save(root / 'libraries' / ('Full_target_only_' + dataset + '.json'))
                source = {'key': 'fixture:' + dataset, 'dataset': dataset}
                records[source['key']] = source
                parents[source['key']] = {'source': source['key'], 'dataset': dataset,
                    'library_hash': library.hash, 'native_grade': 1,
                    'views': [{'view': 'fixture', 'controlled': False, 'score': {'grade': 1, 'correct': True},
                        'execution': {'core_executed': False, 'fallback': True, 'events': []}}]}
                path = root / 'predictions' / 'Full' / (digest(source['key']) + '.json')
                path.parent.mkdir(parents=True, exist_ok=True);path.write_text(json.dumps(parents[source['key']]))
            (root / 'registered_transfer_masks.json').write_text(json.dumps(masks))
            (root / 'TEST_completed.json').write_text(json.dumps({
                'freeze_artifact_sha256': 'fixture-only-freeze', 'result_file_sha256': {}}))
            class Ledger:
                @contextmanager
                def transaction(self):
                    with sqlite3.connect(':memory:') as db:
                        db.execute('create table calls (id text, role text, status text)')
                        yield db
            def parent(source, masked, namespace):
                self.assertNotIn('grading', source)
                self.assertTrue(namespace.startswith('Full_foreign_off/'))
                calls.append(source['key'])
                return deepcopy(parents[source['key']])
            runner = SimpleNamespace(profile={'run_id': 'fixture-only', 'freeze': {'artifact_sha256': 'fixture-only-freeze'}},
                libraries={'Full': library}, records=records, parent=parent, ledger=Ledger())
            with patch('experiments.legal_skill_evolution_frozen.FOLDER', root), patch(
                    'experiments.legal_skill_evolution_frozen.FrozenStudy', return_value=runner), redirect_stdout(io.StringIO()):
                run();self.assertEqual(len(calls), 5)
                summary = json.loads((root / 'transfer/summary.json').read_text())
                self.assertEqual(summary['parent_outcomes']['unchanged'], 5)
                self.assertEqual(summary['fully_correct_foreign_core_views'], 0)
                run();self.assertEqual(len(calls), 5)
                (root / 'transfer/summary.json').write_text('{}')
                with self.assertRaisesRegex(ValueError, 'completed transfer result changed'):
                    run()


if __name__ == '__main__':unittest.main()
