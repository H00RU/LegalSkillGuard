"""Real TRAIN failure parity and freeze/data-isolation checks for the DEV path."""
from copy import deepcopy
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from experiments import legal_skill_evolution_mixed_dev as dev
from experiments import legal_skill_evolution_source_checkpoints as source
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.sara_statute_kernel import current_case_interface
from legal_skill_guard.skill_evolution.statute_pure_calculation import certificate
from legal_skill_guard.skill_evolution.native_theory_feedback import contract_execution, contract_checker


class FrozenEvaluationTests(unittest.TestCase):
    def test_real_unsupported_query_does_not_dispatch_empty_rereads(self):
        original = dev.read(dev.OUT / 'initial/FreeHistory' /
            (digest('SARA_v2_Binary:be5c71e70a4f8c272f0386786be696054da21713a709f57db5c0b9300976a4f0') + '.json'))
        self.assertFalse(original['execution']['handled'])
        self.assertFalse(original['contract']['requires_neural_read'])
        for arm in dev.current.learned.ARMS:
            with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'OUT', Path(directory)), patch.object(
                    dev, 'generate', side_effect=AssertionError('No declared observation can be reread')):
                result = dev.followup(None, {'key': original['source']}, {}, original, arm)
            self.assertFalse(result['eligible'])
            self.assertEqual(result['policies'], {})

    def test_unscored_DEV_execution_matches_TRAIN_but_learning_feedback_stays_TRAIN_only(self):
        t = dev.source_train
        sid = next(s for s in t.prepare()['sources'] if '4607c94' in s)
        public = next(s for s in t.read(dev.parent.PREPARED / 'public.json') if s['key'] == sid)
        saved = t.read(t.OUT / 'B5/post_shared_authorized_consumer/FreeUpdate/results' / t.previous.old.name_for(sid))
        output = saved['actual']['execution']['source_output']
        spec = source.load(5, 'FreeUpdate')['spec']
        changed = deepcopy(public)
        changed['split'] = 'dev'
        with patch('legal_skill_guard.skill_evolution.native_theory_feedback.grade_view', side_effect=AssertionError('Execution cannot read labels')):
            self.assertEqual(contract_execution(spec, changed)(output), contract_execution(spec, public)(output))
        with self.assertRaisesRegex(ValueError, 'TRAIN only'):
            contract_checker(spec, changed, {})

    def test_public_arithmetic_is_shared_without_case_read_or_learning_credit(self):
        obs = dev.current.learned
        actual = next(r for r in obs.read(obs.OUT / 'B7/scored_results.json')['rows']
            if r['arm'] == 'ProgramGuided' and 'ff37f276' in r['source'])
        sid = actual['source']
        public = next(s for s in obs.read(dev.parent.OUT / 'SARA_corrected_TRAIN_views.json') if s['key'] == sid)
        kernel = current_case_interface(next(r['kernel'] for r in obs.read(dev.parent.OUT / 'SARA_native_kernel_bank.json') if r['source'] == sid))
        self.assertTrue(certificate(kernel)['certified_fact_independent'])
        for arm in ('GenericView', *obs.ARMS):
            with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'OUT', Path(directory)), patch.object(
                    dev, 'generate', side_effect=AssertionError('A pure arithmetic query must not read case facts')):
                # No learned library is needed by any arm on this public route.
                row = dev.observe_case(None, public, kernel, arm, None)
            for key in ('answer', 'handled', 'kernel_sha256'):
                self.assertEqual(row['execution'][key], actual['execution'][key])
            self.assertEqual(row['execution']['binding_executions'][0]['execution'],
                actual['execution']['binding_executions'][0]['execution'])
            self.assertEqual(row['grounded']['bindings'][0]['inputs'],
                actual['grounded']['bindings'][0]['inputs'])
            self.assertEqual(row['reads'], [])
            self.assertTrue(row['shared_public_calculation']['not_a_learned_mechanism'])

    def test_fact_dependent_and_nested_statutory_calls_are_not_certified(self):
        obs = dev.current.learned
        bank = obs.read(dev.parent.OUT / 'SARA_native_kernel_bank.json')
        for prefix in ('ed3f34', 'cd2ab8', '250fc5'):
            kernel = current_case_interface(next(r['kernel'] for r in bank if r['source'].split(':')[-1].startswith(prefix)))
            self.assertFalse(certificate(kernel)['certified_fact_independent'])

    def test_no_DEV_record_read_before_actual_freeze_exists(self):
        paths = []
        def absent(path):
            paths.append(Path(path))
            raise FileNotFoundError(path)
        with patch.object(dev, 'read', absent), self.assertRaises(FileNotFoundError):
            dev.prepare()
        self.assertEqual(paths, [dev.frozen.OUT / 'frozen_manifest.json'])

    def test_real_B5_observation_lowering_and_execution_match_TRAIN(self):
        obs = dev.current.learned
        actual = obs.read(obs.OUT / 'B5/scored_results.json')['rows'][0]
        sid, arm = actual['source'], actual['arm']
        public = next(s for s in obs.read(dev.parent.OUT / 'SARA_corrected_TRAIN_views.json') if s['key'] == sid)
        kernel = current_case_interface(next(s['kernel'] for s in obs.read(dev.parent.OUT / 'SARA_native_kernel_bank.json') if s['source'] == sid))
        library = obs.read(obs.OUT / 'B5' / arm / 'library.json')
        with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'OUT', Path(directory)), patch.object(
                dev, 'generate', return_value=(deepcopy(actual['raw_decoded_observation']), {'existing_paid_response': True})):
            row = dev.observe_case(None, public, kernel, arm, library)
        self.assertEqual(row['grounded'], actual['grounded'])
        self.assertEqual(row['execution'], actual['execution'])
        self.assertEqual(row['actual_component_ids'], actual['actual_component_ids'])

    def test_real_source_programs_and_common_consumer_match_saved_execution(self):
        train = dev.source_train
        sid = next(s for s in train.prepare()['sources'] if '4607c94' in s)
        public = next(s for s in train.read(dev.parent.PREPARED / 'public.json') if s['key'] == sid)
        libraries = {a: source.load(5, a) for a in train.ARMS}
        with tempfile.TemporaryDirectory() as directory, patch.object(dev, 'OUT', Path(directory)):
            row = dev.source_case(SimpleNamespace(config=train.prepare()['executor_profile']), public, libraries)
        for arm in train.ARMS:
            actual = train.read(train.OUT / 'B5/post_shared_authorized_consumer' / arm / 'results' / train.previous.old.name_for(sid))
            self.assertNotIn('error', row['rows'][arm])
            before = deepcopy(actual['actual']['execution'])
            after = deepcopy(row['rows'][arm]['source_execution'])
            if arm == 'ConstraintAcquire':
                # Solver wall time changes on real replay; all logical output,
                # evidence, status, source terms and other receipt fields match.
                before['composition']['solver'].pop('seconds')
                after['composition']['solver'].pop('seconds')
            self.assertEqual(after, before)

    def test_real_executed_wrong_case_cannot_select_favorable_fallback(self):
        obs = dev.current.learned
        actual = next(r for r in obs.read(obs.OUT / 'B6/initial_scored_results.json')['rows']
            if r['arm'] == 'ProgramGuided' and r['execution']['handled'])
        public = next(s for s in obs.read(dev.parent.PREPARED / 'public.json') if s['key'] == actual['source'])
        grading = obs.read(dev.parent.PREPARED / 'grading.json')[actual['source']][public['views'][0]['id']]
        self.assertFalse(actual['native_score']['correct'])
        inherited = {'execution': {'answer': 'Contradiction'}}
        core = {'core_executed': True, 'answer': actual['execution']['answer']}
        row = dev.score_view(public, public['views'][0], core, inherited, grading)
        self.assertFalse(row['fallback'])
        self.assertEqual(row['answer'], actual['execution']['answer'])
        self.assertFalse(row['score']['correct'])
        unresolved = dev.score_view(public, public['views'][0], {'core_executed': False, 'answer': None}, inherited, grading)
        self.assertTrue(unresolved['fallback'])
        self.assertTrue(unresolved['score']['correct'])
        self.assertFalse(unresolved['core_score']['correct'])


if __name__ == '__main__':
    unittest.main()
