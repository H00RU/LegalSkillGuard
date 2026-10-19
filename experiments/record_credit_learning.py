"""One real counterfactual-guided edit and complete forward-batch transfer.

The finite coordinator reuses the original learner, native solver, ordinary fit
and scorer. No new production solver, inference wrapper or efficacy admission.
"""
from __future__ import annotations

import copy
import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.witnessed_experience import WitnessedOnline
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.decision_evidence import (
    witness_knowledge_view,
    witnessed_skill_payload,
)
from legal_skill_guard.learning.experiment import ROOT, now, points, read, sha
from legal_skill_guard.learning.member_learning import paired_effect
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha


class RecordCreditLearning(WitnessedOnline):
    def inherit_current(self, row, mode):
        role = 'joint_empty' if mode == 'empty' else 'skills'
        old = ROOT/'runs'/self.cfg['inherited_source_run']
        stage = 'b3_prequential_'+mode
        messages, schema, _ = witnessed_skill_payload(row, self.labels, self.leads(row),
            self.cfg['bundled_solver_system'], self.materialized, mode=mode)
        ip, np, lp, dp = [old/f'{kind}/{stage}/{row["id"]}/{role}.json'
            for kind in ['inputs', 'native', 'logical_answers', 'deliveries']]
        assert read(ip) == {'messages': messages, 'schema': schema}
        native, logical = read(np)['response'], read(lp)
        assert native == logical['response'] and logical['ordinary_tool_source_ids'] == self.prefix_ids
        assert logical['bank_sha256'] == csha(self.bank if mode == 'combined' else [])
        self.record(f'inputs/{self.phase}/{row["id"]}/{role}.json', read(ip))
        self.record(f'deliveries/{self.phase}/{row["id"]}/{role}.json', read(dp))
        self.record(f'inherited_actual_calls/{row["id"]}/{role}.json', {
            'input_path': str(ip), 'input_sha256': sha(ip), 'native_path': str(np), 'native_sha256': sha(np),
            'logical_path': str(lp), 'logical_sha256': sha(lp), 'actual_original_response': native,
            'new_native_calls': 0, 'already_paid_not_independent_exploration': True})
        self.logical(row, role, native)

    def execute(self):
        assert self.cfg['study_kind'] == 'record_removal_feedback_actual_edit_forward8'
        assert len(self.documents) == 16 and len(self.prefix_ids) == 218 and len(self.bank) == 4
        assert [r['id'] for r in self.documents] == self.cfg['episode_ids']
        assert self.cfg['generation'] == read(ROOT/self.cfg['inherited_source_config'])['generation']
        path = ROOT/self.cfg['terminal_parent_publication']
        assert path == max(path.parent.glob('online_b*.json'), key=lambda p: int(p.stem.split('_b')[1]))
        parent = read(path)
        assert parent['publication'] == self.bank
        assert read(ROOT/self.cfg['terminal_parent_receipt'])['state'] == 'terminal_results_preserved'
        self.materialized = copy.deepcopy(parent['materialized_runtime_memory'])
        self.catalog = {w['witness_ref']: {k: v for k, v in w.items() if k != 'witness_ref'}
            for s in self.materialized for w in s['witnesses']}
        self.nonmember_catalog = {w['nonmember_ref']: {k: v for k, v in w.items() if k != 'nonmember_ref'}
            for s in self.materialized for w in s['nonmembers']}
        self.memory_tokens = self.meter.token_count(text=json.dumps(witness_knowledge_view(self.materialized),
            ensure_ascii=False, separators=(',', ':')))
        assert self.memory_tokens == parent['complete_model_delivered_knowledge_target8B_tokens'] <= 4096
        self.publication_history = []
        self.reading_policy = read(ROOT/self.cfg['reading_calibration_completion'])['reading_policy']
        self.last_update = {'actual_parent_publication': parent,
            'actual_previous_all8_training_update_effect': read(ROOT/self.cfg['inherited_parent_update_effect']),
            'historical_effect_not_a_new_execution_or_complete_old_trajectory_replay': True}
        old_bank, old_materialized, old_tokens = copy.deepcopy(self.bank), copy.deepcopy(self.materialized), self.memory_tokens
        self.record('declaration.json', {'at': now(), 'config': self.cfg,
            'frozen_bindings': self.bindings.copy(), 'actual_initial_terminal_bank': self.bank,
            'actual_initial_materialized_memory': self.materialized, 'initial_knowledge_tokens': self.memory_tokens,
            'initial_ordinary_source_ids': self.prefix_ids, 'reading_policy': self.reading_policy,
            'planned_new_native_teacher_CPUfits': [64, 1, 1], 'planned_logical_answers': 80,
            'inherited_already_paid_physical_answers': 16,
            'not_independent_confirmation_complete128_or_official_TEST': True,
            'all_structurally_valid_teacher_edits_publish_without_efficacy_admission': True})
        self.current_batch = 3
        for row in self.documents[:8]:
            for mode in ['empty', 'combined']:
                self.phase = 'inherited_b3_'+mode
                self.inherit_current(row, mode)
        current = self.score(self.answers)
        self.units.extend(current)
        empty = [u for u in current if u['condition'] == 'joint_empty']
        full = [u for u in current if u['condition'] == 'skills']
        window = self.past[-8:]+self.documents[:8]
        effects = self.learn_with_record_removal_feedback(self.documents[:8], empty, full, window, 'credit_b3')
        start, self.phase = len(self.answers), 'credit_b3_actual_after'
        for row in self.documents[:8]:
            self.answer_mode(row, 'combined', self.leads(row))
        after = self.score(self.answers[start:])
        self.units.extend(after)
        update = paired_effect(full, after, seed=2026101941, replicates=5000)
        self.record('actual_publication_effect.json', {'at': now(), 'effect': update,
            'same_actual218_ordinary_model': True, 'not_an_effectiveness_admission_or_new_source_transfer': True})
        self.fit_prefix(self.documents[:8])
        assert len(self.prefix_ids) == 226
        learned, learned_materialized, learned_tokens = copy.deepcopy(self.bank), copy.deepcopy(self.materialized), self.memory_tokens
        self.current_batch, start = 4, len(self.answers)
        styles = ('empty', 'parent', 'learned')
        try:
            for index, row in enumerate(self.documents[8:]):
                offset = index % len(styles)
                for style in styles[offset:]+styles[:offset]:
                    self.phase = 'forward_b4_'+style
                    if style == 'parent':
                        self.bank, self.materialized, self.memory_tokens = old_bank, old_materialized, old_tokens
                    else:
                        self.bank, self.materialized, self.memory_tokens = learned, learned_materialized, learned_tokens
                    self.answer_mode(row, 'empty' if style == 'empty' else 'combined', self.leads(row))
        finally:
            # Restore the ONLY newly published bank regardless of its score.
            self.bank, self.materialized, self.memory_tokens = learned, learned_materialized, learned_tokens
        forward = self.score(self.answers[start:])  # First use of B4 annotations.
        self.units.extend(forward)
        groups = {s: [u for u in forward if u['stage'] == 'forward_b4_'+s] for s in styles}
        assert all(len(v) == 8 for v in groups.values())
        assert len(self.native) == 64 and len(self.answers) == 80
        assert len(self.teachers) == self.teacher_attempts == len(self.fit_records) == 1
        result = {'at': now(), 'run_id': self.run_id, 'record_removal_effects': effects,
            'actual_same_tool_training_publication_effect': update,
            'training_metrics': {'empty': points(empty), 'parent': points(full), 'actual_learned': points(after)},
            'complete_forward8_metrics': {s: points(v) for s, v in groups.items()},
            'forward_paired_effects': {f'{a}_to_{b}': paired_effect(groups[a], groups[b],
                seed=2026101942+i, replicates=5000) for i, (a, b) in enumerate([
                    ('empty', 'parent'), ('empty', 'learned'), ('parent', 'learned')])},
            'actual_terminal_library': self.bank, 'actual_terminal_materialized_memory': self.materialized,
            'actual_terminal_knowledge_tokens': self.memory_tokens, 'ordinary_source_ids': self.prefix_ids,
            'actual_new_native_teacher_CPUfits': [64, 1, 1], 'inherited_already_paid_physical_answers': 16,
            'logical_answers': 80, 'all_actual_units_and_adverse_results': self.units,
            'prior_native_attempts_completed_unfinished': [819, 818, 1],
            'cumulative_native_attempts_completed_unfinished': [883, 882, 1],
            'cumulative_teacher_attempts_completed_unfinished': [37, 36, 1], 'cumulative_actual_CPUfits': 36,
            'unfinished_usage_unknown_and_not_entire_project_history': True,
            'adaptive_TRAIN_finite_edit_not_full_online_repeat_official_TEST_or_causal_mechanism_confirmation': True,
            'no_no_ablation_teacher_arm_so_extra_feedback_effect_not_isolated': True}
        self.record('completion.json', result)
        RunStore.atomic_json(self.out/'progress.json', {'at': now(), 'state': 'completed', 'run_id': self.run_id,
            'completed_native_calls': 64, 'completed_teacher_calls': 1, 'actual_new_CPUfits': 1,
            'complete_forward8_metrics': result['complete_forward8_metrics']})
        print(json.dumps({'completed': self.run_id, 'forward': result['complete_forward8_metrics']}), flush=True)


def main():
    with (ROOT/'artifacts/gpu_generation.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = RecordCreditLearning(Path(sys.argv[1]))
        try:
            study.execute()
        except BaseException as error:
            failure = {'at': now(), 'state': 'failed', 'error': repr(error), 'traceback': traceback.format_exc(),
                'actual_new_native_teacher_CPUfits': [len(study.native), len(study.teachers), len(study.fit_records)],
                'actual_teacher_attempts': study.teacher_attempts,
                'no_retry_admission_answer_repair_or_selected_old_bank': True}
            study.record('failure.json', failure)
            RunStore.atomic_json(study.out/'progress.json', failure)
            raise


if __name__ == '__main__':
    main()
