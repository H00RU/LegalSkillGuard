"""Finite paired source-grounding diagnosis; remove after terminal preservation.

Use the actual terminal bank/tool, not a selected checkpoint. No teaching, fit,
current-answer repair, final-citation constraint, or official DEV/TEST access.
"""
from __future__ import annotations

import fcntl
import json
import sys
import traceback
from pathlib import Path

from experiments.witnessed_experience import WitnessedExperience
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.decision_evidence import (
    source_bound_reason_payload,
    witness_knowledge_view,
    witnessed_skill_payload,
)
from legal_skill_guard.learning.evidence_programs import evidence_proposals
from legal_skill_guard.learning.experiment import ROOT, now, points, read, sha
from legal_skill_guard.learning.member_learning import ENDPOINTS, paired_effect
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

STYLES = ('original_empty', 'original_skills', 'bounded_empty', 'bounded_skills')


class BoundedReasonDiagnosis(WitnessedExperience):
    def teacher_call(self, *args, **kwargs):
        raise AssertionError('No teacher in the fixed-bank execution diagnosis')

    def fit_prefix(self, *args, **kwargs):
        raise AssertionError('No fit in the fixed-tool execution diagnosis')

    def payload(self, row, style, proposals):
        assert style in STYLES
        messages, schema, delivery = witnessed_skill_payload(row, self.labels, proposals,
            self.cfg['bundled_solver_system'], self.materialized,
            mode='combined' if style.endswith('_skills') else 'empty')
        if style.startswith('bounded_'):
            messages, schema, anchor = source_bound_reason_payload(messages, schema, row)
            delivery['bounded_public_reason'] = anchor
        return messages, schema, delivery

    def answer_style(self, row, style, proposals, *, inherited=False):
        role = 'skills' if style.endswith('_skills') else 'joint_empty'
        messages, schema, delivery = self.payload(row, style, proposals)
        assert not delivery['excluded_same_source_witness_refs']
        assert not delivery['excluded_same_source_nonmember_refs']
        if inherited:
            assert style.startswith('original_')
            old = ROOT/'runs'/self.cfg['inherited_source_run']
            stage = 'b3_prequential_combined' if role == 'skills' else 'b3_prequential_empty'
            input_path = old/f'inputs/{stage}/{row["id"]}/{role}.json'
            native_path = old/f'native/{stage}/{row["id"]}/{role}.json'
            logical_path = old/f'logical_answers/{stage}/{row["id"]}/{role}.json'
            assert read(input_path) == {'messages': messages, 'schema': schema}
            native, logical = read(native_path)['response'], read(logical_path)
            assert logical['response'] == native
            assert logical['ordinary_tool_source_ids'] == self.prefix_ids
            assert logical['bank_sha256'] == csha(self.bank if role == 'skills' else [])
            self.record(f'inputs/{self.phase}/{row["id"]}/{role}.json', read(input_path))
            self.record(f'inherited_actual_calls/{row["id"]}/{role}.json', {
                'source_input': str(input_path), 'source_input_sha256': sha(input_path),
                'source_native': str(native_path), 'source_native_sha256': sha(native_path),
                'source_logical': str(logical_path), 'source_logical_sha256': sha(logical_path),
                'actual_original_response': native, 'new_native_calls': 0,
                'physical_call_already_counted_not_independent_exploration': True})
        else:
            native = self.generate(row, role, messages, schema)
        body = json.loads(messages[1]['content'])
        self.record(f'deliveries/{self.phase}/{row["id"]}/{role}.json', {
            **delivery, 'actual_native_raw_id': native['raw_id'], 'intervention': style,
            'inherited_actual_physical_call': inherited,
            'actual_source_read_selection': proposals['selection'],
            'actual_model_delivered_knowledge_tokens': self.memory_tokens if role == 'skills' else 0,
            'actual_visible_candidates': {'hypotheses': body['hypotheses'],
                'candidate_original_text': body['candidate_original_text']}})
        self.logical(row, role, native)

    def execute(self):
        assert self.cfg['study_kind'] == 'fixed_actual_bank_bounded_reason_16'
        assert len(self.documents) == 16 and len(self.prefix_ids) == 218
        assert [r['id'] for r in self.documents] == self.cfg['episode_ids']
        path = ROOT/self.cfg['terminal_parent_publication']
        assert path == max(path.parent.glob('online_b*.json'), key=lambda p: int(p.stem.split('_b')[1]))
        parent = read(path)
        assert parent['publication'] == self.bank
        assert read(ROOT/self.cfg['terminal_parent_receipt'])['state'] == 'terminal_results_preserved'
        assert self.cfg['generation'] == read(ROOT/self.cfg['inherited_source_config'])['generation']
        self.materialized = parent['materialized_runtime_memory']
        self.memory_tokens = self.meter.token_count(text=json.dumps(witness_knowledge_view(self.materialized),
            ensure_ascii=False, separators=(',', ':')))
        assert self.memory_tokens == parent['complete_model_delivered_knowledge_target8B_tokens'] <= 4096
        policy = read(ROOT/self.cfg['reading_calibration_completion'])['reading_policy']
        self.record('declaration.json', {'at': now(), 'config': self.cfg,
            'frozen_bindings': self.bindings.copy(), 'actual_fixed_terminal_bank': self.bank,
            'actual_materialized_memory': self.materialized, 'knowledge_tokens': self.memory_tokens,
            'shared_ordinary_source_ids': self.prefix_ids, 'shared_reading_policy': policy,
            'planned_new_native_teacher_CPUfits': [48, 0, 0], 'planned_logical_answers': 64,
            'inherited_already_paid_physical_answers': 16,
            'all_new_predictions_before_diagnostic_grading': True,
            'not_learning_episode_independent_confirmation_or_official_TEST': True})
        for block in range(2):
            self.current_batch = block+3
            for index, row in enumerate(self.documents[block*8:(block+1)*8]):
                proposals = evidence_proposals(self.prefix_model, row, self.labels,
                    reading_threshold=policy['threshold'])
                if block == 0:
                    for style in STYLES[:2]:
                        self.phase = f'inherited_b3_{style}'
                        self.answer_style(row, style, proposals, inherited=True)
                    styles = STYLES[2:] if index % 2 == 0 else STYLES[:1:-1]
                else:
                    offset = index % len(STYLES)
                    styles = STYLES[offset:]+STYLES[:offset]
                for style in styles:
                    self.phase = f'reason_b{block+3}_{style}'
                    self.answer_style(row, style, proposals)
        assert len(self.native) == 48 and len(self.answers) == 64
        assert not self.teachers and not self.teacher_attempts and not self.fit_records
        units = self.score(self.answers)
        self.units.extend(units)
        groups = {s: [u for u in units if u['stage'].endswith('_'+s)] for s in STYLES}
        assert all(len(v) == 16 for v in groups.values())
        metrics = {s: points(v) for s, v in groups.items()}
        gains = {style: {k: metrics[style+'_skills'][k]-metrics[style+'_empty'][k]
            for k in ENDPOINTS} for style in ('original', 'bounded')}
        result = {'at': now(), 'run_id': self.run_id, 'metrics': metrics,
            'fixed_first8_metrics': {s: points([u for u in v if u['document_id'] in self.cfg['episode_ids'][:8]])
                for s, v in groups.items()},
            'fixed_next8_metrics': {s: points([u for u in v if u['document_id'] in self.cfg['episode_ids'][8:]])
                for s, v in groups.items()},
            'conditional_skill_gains': gains,
            'skill_gain_interaction_bounded_minus_original': {k: gains['bounded'][k]-gains['original'][k]
                for k in ENDPOINTS},
            'paired_effects': {f'{a}_to_{b}': paired_effect(groups[a], groups[b],
                seed=2026101914+i, replicates=5000) for i, (a, b) in enumerate([
                    ('original_empty', 'original_skills'), ('bounded_empty', 'bounded_skills'),
                    ('original_empty', 'bounded_empty'), ('original_skills', 'bounded_skills')])},
            'actual_new_native_teacher_CPUfits': [48, 0, 0], 'inherited_actual_physical_calls': 16,
            'logical_answers': 64, 'complete_knowledge_tokens': self.memory_tokens,
            'not_token_matched_independent_repeat_learning_or_official_TEST': True,
            'no_teacher_fit_bank_admission_or_native_answer_repair': True,
            'all_adverse_cases_invalids_and_units': units,
            'prior_development_family_native_teacher_CPUfits': self.cfg['prior_development_family_native_teacher_CPUfits'],
            'total_development_family_native_teacher_CPUfits': [a+b for a, b in
                zip([48, 0, 0], self.cfg['prior_development_family_native_teacher_CPUfits'], strict=True)]}
        self.record('completion.json', result)
        RunStore.atomic_json(self.out/'progress.json', {'at': now(), 'state': 'completed',
            'run_id': self.run_id, 'completed_native_calls': 48, 'completed_teacher_calls': 0,
            'actual_new_CPUfits': 0, 'metrics': metrics})
        print(json.dumps({'complete': self.run_id, 'metrics': metrics}), flush=True)


def main():
    with (ROOT/'artifacts/gpu_generation.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        study = BoundedReasonDiagnosis(Path(sys.argv[1]))
        try:
            study.execute()
        except BaseException as error:
            failure = {'at': now(), 'state': 'failed', 'error': repr(error),
                'traceback': traceback.format_exc(), 'actual_new_native_teacher_CPUfits': [
                    len(study.native), len(study.teachers), len(study.fit_records)],
                'no_fallback_answer_repair_or_selected_bank': True}
            study.record('failure.json', failure)
            RunStore.atomic_json(study.out/'progress.json', failure)
            raise


if __name__ == '__main__':
    main()
