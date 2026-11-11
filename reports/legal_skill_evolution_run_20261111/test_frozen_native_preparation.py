"""Use fixtures for freeze permissions and codec separation, never real TEST."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.legal_skill_evolution_freeze_data import materialize, replacement_record, ACTIVE_FORMAL_PROFILE
from experiments.legal_skill_evolution_frozen import FrozenStudy
from legal_skill_guard.rr.partitions import Source
from legal_skill_guard.skill_evolution.objects import Library


class FrozenPreparationTests(unittest.TestCase):
    def test_frozen_actor_receives_public_case_without_native_answers(self):
        with tempfile.TemporaryDirectory() as folder:
            runner = object.__new__(FrozenStudy)
            runner.folder = Path(folder)
            source = {'key': 'fixture-only', 'dataset': 'SARA_v2_Binary', 'views': [
                {'id': 'native', 'public': {'source_text': 'Fixture public rule.', 'question': 'Fixture question.'},
                 'answer_schema': {'type': 'string', 'enum': ['Entailment', 'Contradiction']}}]}
            runner.grading = {'fixture-only': {'native': {'answer': 'Entailment'}}}
            class Actor:
                def run(self, current, view, library, *, purpose):
                    assert 'grading' not in current and 'answer' not in view['public']
                    assert purpose == 'skill_test'
                    return {'answer': 'Contradiction', 'evidence_sentence_ids': [], 'events': [],
                            'core_executed': False, 'fallback': True}
            runner.runtime = Actor()
            library = Library()
            before = library.hash
            record = runner.parent(source, library, 'NoSkill')
            self.assertEqual(record['native_grade'], 0)
            self.assertEqual(record['native_fallback_views'], 1)
            self.assertEqual(record['native_core_correct'], 0)
            self.assertEqual(library.hash, before)
            self.assertFalse(hasattr(runner, 'teacher'))

    def test_missing_B8_blocks_before_annotation_archive_or_sealed_packet_is_opened(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'configs').mkdir()
            (root / 'configs' / ACTIVE_FORMAL_PROFILE.name).write_text(json.dumps({'artifacts': 'formal'}))
            with patch('zipfile.ZipFile', side_effect=AssertionError('TEST archive opened before B8')):
                with self.assertRaisesRegex(ValueError, 'B8 learning'):
                    materialize(root)
            self.assertFalse((root / 'artifacts').exists())

    def test_replacement_keeps_original_four_queries_and_separates_answers_from_actor(self):
        definitions = {k: {'hypothesis': 'fixture hypothesis ' + k} for k in ('nda-11', 'nda-5', 'nda-7', 'nda-16', 'nda-20')}
        annotations = {k: {'choice': 'Entailment', 'spans': [0]} for k in definitions if k != 'nda-11'}
        annotations['nda-20'] = {'choice': 'NotMentioned', 'spans': []}
        doc = {'id': 'fixture-only', 'text': 'Fixture public clause.', 'spans': [[0, 22]],
               'annotation_sets': [{'annotations': annotations}]}
        source = Source('ContractNLI', 'fixture-mother', {'document': doc['text'],
            'query': definitions['nda-11']['hypothesis'], 'answer_type': 'contract_nli'}, 'test')
        expected = {'id': doc['id'], 'key': source.key, 'group': source.group, 'content_hash': source.content_key}
        public, grading = replacement_record(doc, source.group, definitions, expected)
        self.assertEqual([v['id'] for v in public['views']], ['nda-5', 'nda-7', 'nda-16', 'nda-20'])
        self.assertEqual(set(grading), {v['id'] for v in public['views']})
        self.assertIsNone(grading['nda-20']['evidence'])
        for view in public['views']:
            self.assertEqual(set(view['public']), {'source_text', 'sentence_spans', 'question'})
            self.assertEqual(view['public']['sentence_spans'], doc['spans'])
        changed = deepcopy(doc);changed['text'] += ' Changed public source.'
        with self.assertRaisesRegex(ValueError, 'prequalified identity'):
            replacement_record(changed, source.group, definitions, expected)


if __name__ == '__main__':unittest.main()
