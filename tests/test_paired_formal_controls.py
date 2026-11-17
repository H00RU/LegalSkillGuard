"""Eight-batch control updates using constructed teachers and real pure workers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from legal_skill_guard.paired_interfaces.control_learning import unpack_teacher_payload
from legal_skill_guard.paired_interfaces.formal_actors import ProgramActor
from legal_skill_guard.paired_interfaces.formal_budget import PrefixBudgetExecutor
from legal_skill_guard.paired_interfaces.formal_controls import ControlBatchTrainer, ORDINARY, SCOPE
from legal_skill_guard.skill_evolution.objects import digest
from tests import test_paired_formal_budget as fixtures


class FormalControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.shared = self.root / 'shared_variants'
        self.roles = [{'source': 'SARA_v2_Binary:fixture_' + name, 'dataset': 'SARA_v2_Binary',
            'role': role, 'batch': batch} for name, role, batch in [
                ('d1', 'development', 1), ('c1', 'calibration', 1), ('ref', 'reference_only', 2),
                ('structure', 'structure_evaluation', 2), ('d4', 'development', 4), ('c8', 'calibration', 8)]]
        self.public = {r['source']: {'key': r['source'], 'dataset': r['dataset'], 'views': [
            {'id': 'native', 'public': {'facts': 'Alice earns 10.', 'question': 'Constructed fixture is true?'},
             'answer_schema': {'type': 'boolean'}}]} for r in self.roles}
        class Registry:
            actor = SimpleNamespace(views=lambda source: [{'view': 'v0', 'pre_generation_domain_refusal': False}])
            def readiness(self, batch):
                return {'ready': True}
            def review(self, source, view):
                return {'source': source['key'], 'fixture_partial_review': True}, None, {'fixture': True}
        self.registry = Registry(); self.teacher_calls = []; self.grades = []

    def trainer(self, arm):
        ledger = fixtures.FixtureLedger('fixture_' + arm); self.addCleanup(ledger.db.close)
        raw = fixtures.FixtureExecutor(ledger)
        executor = PrefixBudgetExecutor(raw, self.root / arm / 'budget')
        tests = self
        class Teacher:
            def __init__(self):
                self.ledger = ledger
            def propose(self, identity, **kwargs):
                old = ledger.db.execute('select result from calls where id=?', (identity,)).fetchone()
                if old:
                    return json.loads(old[0])
                payload = unpack_teacher_payload(json.loads(kwargs['user_prompt']))
                properties = kwargs['output_schema']['properties']
                tests.teacher_calls.append((arm, identity, deepcopy(payload)))
                ids = payload.get('required_seed_rationale_sources', [])
                if 'policy_rules' in properties:
                    value = {'policy_rules': ['constructed rule'], 'seed_rationales': [], 'implementation_advice': 'fixture'}
                elif 'variants' in properties:
                    value = {'variants': [{'slot': slot, 'target_predicate': 'native',
                        'edits': [{'before': '10', 'after': amount}], 'intended_answer_json': '{"native":true}',
                        'policy_justification': 'constructed fixture'} for slot, amount in [('local', '11'), ('systemic', '12')]]}
                elif 'verdicts' in properties:
                    value = {'verdicts': [{'slot': v['slot'], 'well_formed_and_policy_supported': True,
                        'answer_json': '{"native":true}', 'rationale': 'constructed fixture'} for v in payload['variants']]}
                else:
                    wanted = payload['batch'] == 4 or arm == SCOPE and payload['batch'] == 8
                    program = {'predicates': [], 'extractors': [], 'composition':
                        "def compose(inputs, predict, extractors):\n    return {'native': " + str(wanted) + '}\n'}
                    value = {'program': program, 'policy_rationale': 'fixture', 'changes_from_previous': []}
                    if 'seed_rationales' in properties:
                        value.update(seed_rationales=[{'source': source, 'rationale': 'fixture'} for source in ids],
                            trace_attribution_and_clause_grounded_revisions='fixture', regression_contrasts_and_backtracking='fixture')
                response = {'value': value}
                ledger.db.execute('insert into calls values(?,?,?,?,?,?)',
                    (identity, 'teacher', 'skill_teacher', kwargs['source_ids'][0], 'completed', json.dumps(response)))
                return response
        def grader(source, seal):
            role = next(r['role'] for r in self.roles if r['source'] == source)
            self.assertIn(role, ('development', 'calibration'))
            self.grades.append((source, seal['batch']))
            return {'native': {'answer': True}}
        trainer = ControlBatchTrainer(self.root / arm, arm=arm, roles=self.roles, public=self.public,
            registry=self.registry, teacher=Teacher(), executor=executor, grade_provider=grader,
            study_binding={'fixture': 'no model dispatch'}, shared_variants_root=self.shared)
        return trainer, raw

    def run_pair(self):
        ordinary, ordinary_raw = self.trainer(ORDINARY)
        scope, scope_raw = self.trainer(SCOPE)
        ordinary.batch(0); scope.batch(0)
        libraries = {}
        for batch in range(1, 9):
            evidence = {'input_plus_output_token_cap': 10000 * batch, 'fixture': True}
            ordinary.executor.set_limit(batch, evidence); scope.executor.set_limit(batch, evidence)
            libraries[SCOPE, batch] = scope.batch(batch)
            libraries[ORDINARY, batch] = ordinary.batch(batch)
        return ordinary, scope, ordinary_raw, scope_raw, libraries

    def test_fixed_stages_reselect_complete_prefix_without_reference_or_structural_labels(self):
        ordinary, scope, o_raw, s_raw, libraries = self.run_pair()
        self.assertEqual(len([c for c in self.teacher_calls if c[0] == ORDINARY]), 4)
        self.assertEqual(len([c for c in self.teacher_calls if c[0] == SCOPE]), 4)
        last = libraries[ORDINARY, 8]['datasets']['SARA_v2_Binary']
        self.assertEqual(last['current_prefix_measured_mothers'], 4)
        self.assertEqual(last['candidate_index'], 1)
        self.assertTrue(libraries[SCOPE, 8]['datasets']['SARA_v2_Binary']['fixed_monolithic_seed'])
        self.assertEqual(len(ordinary.completion_evidence()['actual_fixed_optimizer_teacher_calls']), 4)
        self.assertEqual(len(scope.completion_evidence()['actual_fixed_optimizer_teacher_calls']), 4)
        for arm, _, payload in self.teacher_calls:
            for example in payload.get('source_only_examples', []):
                self.assertNotIn('native_TRAIN_feedback', example)
            self.assertFalse(any('structure' in e['source'] for e in payload.get('measured_examples', [])))
        calls = len(self.teacher_calls)
        ordinary.batch(1); scope.batch(8)
        self.assertEqual(len(self.teacher_calls), calls)

    def test_shared_variants_are_blind_verified_and_never_select_on_extra_mothers(self):
        _, _, _, _, libraries = self.run_pair()
        shared = json.loads((self.shared / 'SARA_v2_Binary/verified.json').read_text())
        self.assertEqual(len(shared['variants']), 2)
        self.assertTrue(all(v['admitted'] and v['new_independent_mother'] is False for v in shared['variants']))
        verification = next(p for arm, _, p in self.teacher_calls if arm == SCOPE and 'variants' in p and 'shared_legal_assets' in p and 'measured_examples' not in p)
        self.assertFalse(any('intended_answer' in v or 'policy_justification' in v for v in verification['variants']))
        self.assertEqual(libraries[ORDINARY, 4]['datasets']['SARA_v2_Binary']['current_prefix_measured_mothers'], 3)

    def test_missing_source_review_blocks_teacher_and_weak_dispatch(self):
        trainer, raw = self.trainer(ORDINARY); trainer.batch(0)
        trainer.registry = SimpleNamespace(readiness=lambda batch: {'ready': False})
        trainer.executor.set_limit(1, {'input_plus_output_token_cap': 100})
        with self.assertRaisesRegex(ValueError, 'missing source-only reviews'):
            trainer.batch(1)
        self.assertEqual(self.teacher_calls, []); self.assertEqual(raw.physical_calls, [])

    def test_batch_order_and_fixed_teacher_schedule_cannot_expand(self):
        trainer, _ = self.trainer(ORDINARY)
        with self.assertRaisesRegex(ValueError, 'every original batch'):
            trainer.batch(4)
        with self.assertRaisesRegex(ValueError, 'fixed four-stage schedule'):
            trainer._teacher(3, 'SARA_v2_Binary', 'extra_candidate', {}, {}, [])


if __name__ == '__main__':
    unittest.main()
