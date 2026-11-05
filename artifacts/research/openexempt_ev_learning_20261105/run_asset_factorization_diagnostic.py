"""Two-arm TRAIN8 capacity diagnostic, not a production adapter."""
from __future__ import annotations

import collections
import copy
import fcntl
import hashlib
import json
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jsonschema import validate
from experiments.openexempt_online import Online, actor_payload, native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import (
    allowable_namespaces, decode_asset_references, decode_reference,
    public_asset_catalog, public_catalog,
)
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.openexempt import evaluate, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

BASE = Path(__file__).resolve().parent
OUT = BASE / 'asset_factorization_TRAIN8_run01'
PROTOCOL = ROOT / 'docs/research/OPENEXEMPT_EV_ASSET_FACTORIZATION_TRAIN8_20261105.md'
CONFIG = ROOT / 'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json'
OLD = ROOT / 'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01'
REFERENCE = BASE / 'own_EC_context_TRAIN32_run01/protocol.json'
PARENTS = ROOT / 'artifacts/research/openexempt_ev_learning_20261104/bounded_train_pilot_run01/parent_records.json'


class Diagnostic:
    check = Comparison.check
    call = Comparison.call
    progress = Online.progress
    grade = Online.grade

    def __init__(self):
        self.cfg = read(CONFIG)
        self.original_generation = copy.deepcopy(self.cfg['generation'])
        self.cfg['generation']['timeout_seconds'] = 600
        self.run_id = 'openexempt_EV_asset_factorization_TRAIN8_20261105_run01'
        self.out, self.stop, self.current_batch = OUT, False, 4
        self.native, self.teachers, self.reuse_events = [], [], []
        self.teacher_attempts, self.attempts, self.started = 0, 0, None
        self.lock = threading.Lock()
        reference = read(REFERENCE)
        self.bank = reference['bank']
        self.rows = read(ROOT / self.cfg['input_packet'])['rows']
        self.by_row = {(r['case_id'], r['family']): r for r in self.rows}
        self.current = set(reference['current_source_ids'])
        self.ids, covered = [], set()
        rank = lambda cid: hashlib.sha256(self.by_row[cid, 'EV']['source_key'].encode()).hexdigest()
        for cohort in [self.current, set(reference['source_ids']) - self.current]:
            groups = collections.defaultdict(list)
            for cid in cohort:
                groups[tuple(sorted(allowable_namespaces(self.by_row[cid, 'EV'])))].append(cid)
            chosen = [min(groups[sc], key=rank) for sc in sorted(groups, key=lambda sc: (sc in covered, sc))[:4]]
            if len(chosen) < 4:
                chosen += sorted(cohort - set(chosen), key=rank)[:4-len(chosen)]
            self.ids += chosen
            covered.update(tuple(sorted(allowable_namespaces(self.by_row[c, 'EV']))) for c in chosen)
        assert self.ids == [229, 240, 243, 244, 213, 201, 193, 192]
        self.jobs = [(cid, arm, ref) for cid in sorted(self.ids) for arm in ['empty', 'skills']
                     for ref in public_asset_catalog(self.by_row[cid, 'EV'])]
        assert len(self.jobs) == 38 and len(self.jobs) <= 64
        self.bindings = dict(read(CONFIG.with_suffix('.frozen.json'))['files'])
        for p in [Path(__file__), PROTOCOL, REFERENCE, PARENTS]:
            self.bindings[str(p)] = sha(p)
        self.controls = {'empty': [], 'skills': []}
        parents = {r['case_id']: r for r in read(PARENTS)}
        for cid in self.ids:
            row = self.by_row[cid, 'EV']
            batch_path = OLD / 'batches' / f"b{row['batch']}_prequential_records.json"
            self.bindings[str(batch_path)] = sha(batch_path)
            empty = next(r for r in read(batch_path)['empty_direct_numeric'] if r['case_id'] == cid and r['family'] == 'EV')
            for arm, record in [('empty', empty), ('skills', parents[cid])]:
                bank = [] if arm == 'empty' else self.bank
                messages, schema, _ = actor_payload(row, bank, grounded=True, direct_numeric=True, asset_references=True)
                raw = ROOT / record['raw_call_path']; inp = raw.with_suffix('.input.json')
                original = read(inp)
                assert messages == original['messages'] and schema == original['schema']
                self.bindings[str(raw)], self.bindings[str(inp)] = sha(raw), sha(inp)
                self.controls[arm].append(copy.deepcopy(record))
        self._dispatch = PhaseDispatch(self.cfg, environment=read(ROOT / self.cfg['inference_environment']),
                                       on_failure=lambda: setattr(self, 'stop', True))
        for sig in [signal.SIGINT, signal.SIGTERM]:
            signal.signal(sig, lambda *_: setattr(self, 'stop', True))
        self.check()
        assert WireClient(self.cfg['generation']).readiness()['ready']
        OUT.mkdir(exist_ok=False)
        RunStore.immutable_json(OUT / 'protocol.json', {
            'at': now(), 'TRAIN_diagnostic_not_main_or_TEST': True, 'source_ids': self.ids,
            'current_source_ids': sorted(set(self.ids) & self.current), 'parent_bank': self.bank,
            'source_selection_public_scope_then_source_key_hash_no_scores': True,
            'jobs': self.jobs, 'max_calls': 64, 'planned_calls': len(self.jobs), 'max_teacher_calls': 0,
            'generation': self.cfg['generation'], 'original_generation': self.original_generation,
            'per_call_not_per_case_compute_equal': True, 'max_actor_wall_seconds': 1800,
            'original_whole_case_controls': self.controls, 'frozen_files': self.bindings,
            'formal_adoption_requires_user_confirmation': True})

    def answer(self, job):
        cid, arm, ref = job
        row = self.by_row[cid, 'EV']; bank = [] if arm == 'empty' else self.bank
        messages, schema, supplied = actor_payload(row, bank, grounded=True, direct_numeric=True, asset_references=True)
        messages, schema = copy.deepcopy(messages), copy.deepcopy(schema)
        edits = 0
        for m in messages:
            for old, new in [
                ('Include every listed ID, using [] when no exemption is applicable.',
                 'This request covers exactly the focus asset_ref specified in the last message; output only that key, using [] when no exemption is applicable. Other asset mentions and all facts remain context.'),
                ('exactly all supplied case-local asset_ref keys', 'exactly the focus case-local asset_ref key specified in the last message')]:
                edits += m['content'].count(old)
                m['content'] = m['content'].replace(old, new)
        assert edits == 2
        schema['required'] = [ref]
        schema['properties'] = {ref: schema['properties'][ref]}
        messages.append({'role': 'user', 'content': json.dumps({'focus_asset_ref': ref}, separators=(',', ':'))})
        assets, catalog = public_asset_catalog(row), public_catalog(row)
        path = OUT / 'native' / f'{cid}_{arm}_{ref}.json'
        RunStore.immutable_json(path.with_suffix('.input.json'), {
            'messages': messages, 'schema': schema, 'bank_sha256': csha(bank),
            'full_public_asset_catalog_retained': assets, 'public_citation_catalog': catalog,
            'delivered_skill_ids': [s['id'] for s in supplied], 'focus_asset_ref': ref,
            'no_gold_EC_predictions_amount_parser_or_solver_in_actor_input': True})
        with self.lock:
            if self.started is None: self.started = time.monotonic()
            if self.attempts >= 64 or time.monotonic() - self.started >= 1200:
                raise TimeoutError('Bounded dispatch exhausted; no retries')
            self.attempts += 1
        response = self.call(path, messages, schema, self.cfg['generation']['max_tokens'], {
            'stage': 'asset_factorization_diagnostic', 'arm': arm, 'document_id': cid,
            'family': 'EV', 'call_role': 'openexempt', 'focus_asset_ref': ref, 'bank_sha256': csha(bank)})
        parsed = submission = None; error = None
        try:
            submission = json.loads(response['content']); validate(submission, schema)
            if response['finish_reason'] != 'stop': raise ValueError('Incomplete native output')
            values = decode_asset_references(copy.deepcopy(submission), {ref: assets[ref]})
            parsed = {a: [{'citation': decode_reference(c['citation_ref'], catalog), 'claim_value': c['claim_value']}
                          for c in claims] for a, claims in values.items()}
        except Exception as exc:
            from jsonschema import ValidationError
            if not isinstance(exc, (ValidationError, ValueError, TypeError, KeyError)): raise
            error = repr(exc)
        result = {'case_id': cid, 'arm': arm, 'asset_ref': ref, 'decoded_answer': parsed,
                  'submission': submission, 'parse_error': error, 'raw_call_path': str(path.relative_to(ROOT))}
        RunStore.immutable_json(path.with_suffix('.answer.json'), result)
        return result

    def run(self):
        pieces = self._dispatch.native(self.answer, self.jobs)
        RunStore.immutable_json(OUT / 'all_subcall_predictions_before_grading.json', pieces)
        arms = {'whole_empty': self.controls['empty'], 'whole_skills': self.controls['skills'],
                'factorized_empty': [], 'factorized_skills': []}
        for arm in ['empty', 'skills']:
            for cid in sorted(self.ids):
                selected = [p for p in pieces if p['case_id'] == cid and p['arm'] == arm]
                assert {p['asset_ref'] for p in selected} == set(public_asset_catalog(self.by_row[cid, 'EV']))
                errors = [p['parse_error'] for p in selected if p['parse_error']]
                answer = {}
                if not errors:
                    for p in selected:
                        assert not answer.keys() & p['decoded_answer'].keys()
                        answer.update(p['decoded_answer'])
                arms['factorized_' + arm].append({
                    'case_id': cid, 'source_key': self.by_row[cid, 'EV']['source_key'], 'family': 'EV',
                    'bank_sha256': csha([] if arm == 'empty' else self.bank),
                    'parsed': None if errors else {'answer': answer}, 'parse_error': repr(errors) if errors else None,
                    'raw_subcall_paths': [p['raw_call_path'] for p in selected], 'no_host_semantic_answer_changes': True})
        RunStore.immutable_json(OUT / 'full_case_predictions_before_grading.json', arms)
        for records in arms.values(): self.grade(records)
        RunStore.immutable_json(OUT / 'scored_records.json', arms)
        report = {}
        for arm, records in arms.items():
            errs = collections.Counter()
            for r in records:
                target = read(ROOT / self.cfg['grading_directory'] / f"{r['case_id']}.json")['targets']['EV']
                answer = r['parsed']['answer'] if r['parse_error'] is None else None
                assert evaluate(self.by_row[r['case_id'], 'EV'], answer, target) == r['score']
                fb = native_claim_feedback(r, target)
                errs.update({k: int(fb.get(k, 0)) for k in ['invalid_response', 'correct', 'missing', 'incorrect_value', 'extra_or_duplicate']})
            report[arm] = {'all8': metrics(records)['EV'], 'errors': dict(errs),
                'current4': metrics([r for r in records if r['case_id'] in self.current])['EV'],
                'prior4': metrics([r for r in records if r['case_id'] not in self.current])['EV']}
        gains = {arm: {k: 100 * (report['factorized_' + arm]['all8'][k] - report['whole_' + arm]['all8'][k])
                      for k in ['f1', 'full_output_f1']} for arm in ['empty', 'skills']}
        both = [(a, b) for a, b in zip(sorted(arms['whole_skills'], key=lambda r: r['case_id']),
                                      arms['factorized_skills']) if a['parse_error'] is None and b['parse_error'] is None]
        valid_gain = {k: 100 * sum(b['score'][k] - a['score'][k] for a, b in both) / 8 for k in ['f1', 'full_output_f1']}
        keep = all(report['factorized_skills'][c][k] + 1e-12 >= report['whole_skills'][c][k]
                   for c in ['current4', 'prior4'] for k in ['f1', 'full_output_f1'])
        screen = (all(v >= 2 for v in gains['skills'].values()) and keep
                  and report['factorized_skills']['all8']['invalid_format'] <= report['whole_skills']['all8']['invalid_format']
                  and report['factorized_skills']['errors'].get('incorrect_value', 0) < report['whole_skills']['errors'].get('incorrect_value', 0)
                  and all(v > 0 for v in valid_gain.values()))
        result = {'at': now(), 'state': 'completed', 'conditions': report, 'factorization_gain_pp': gains,
            'change_in_skill_minus_empty_gap_pp': {k: gains['skills'][k] - gains['empty'][k] for k in gains['skills']},
            'both_parseable_skill_net_contribution_pp': valid_gain, 'diagnostic_screen_passed': screen,
            'screen_is_not_training_admission_or_formal_adoption': True, 'new_teacher_calls': 0,
            'actual_new_EV_generations': len(self.native), 'original_whole_case_responses_reused': 16,
            'actor_phase_elapsed_seconds': time.monotonic() - self.started,
            'prompt_tokens': sum(r['response']['prompt_tokens'] for r in self.native),
            'completion_tokens': sum(r['response']['completion_tokens'] for r in self.native),
            'formal_method_changed': False, 'adoption_requires_user_confirmation': True}
        RunStore.immutable_json(OUT / 'terminal.json', result)
        self.progress('terminal', state='completed')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    runner = None
    try:
        with (ROOT / 'artifacts/openexempt_training.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            runner = Diagnostic(); runner.run()
    except BaseException as exc:
        if OUT.exists() and not (OUT / 'failure.json').exists():
            RunStore.immutable_json(OUT / 'failure.json', {'at': now(), 'error': repr(exc),
                'traceback': traceback.format_exc(), 'actual_completed_calls': len(runner.native) if runner else None,
                'failed_usage_unknown_not_zero': True, 'no_fallback_retry_or_partial_case_scoring': True})
        raise
