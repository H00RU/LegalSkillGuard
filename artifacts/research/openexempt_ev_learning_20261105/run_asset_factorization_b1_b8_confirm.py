"""Bounded frozen-B1/B8 TRAIN32 confirmation; no production adoption."""
from __future__ import annotations
import collections
import copy
import fcntl
import json
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from jsonschema import ValidationError, validate
from experiments.openexempt_online import Online, actor_payload, native_claim_feedback
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import decode_asset_references, decode_reference, public_asset_catalog, public_catalog
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.openexempt import evaluate, metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

BASE = Path(__file__).resolve().parent
OUT = BASE / 'asset_factorization_B1_B8_TRAIN32_run01'
SCREEN = BASE / 'asset_factorization_TRAIN8_run01'
CONFIG = ROOT / 'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json'
PROTOCOL = ROOT / 'docs/research/OPENEXEMPT_EV_FACTORIZED_B1_B8_TRAIN32_20261105.md'
REFERENCE = BASE / 'own_EC_context_TRAIN32_run01/protocol.json'
OLD = ROOT / 'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01'


class Confirmation:
    check, progress, grade = Comparison.check, Online.progress, Online.grade

    def __init__(self):
        self.cfg = read(CONFIG)
        self.original_generation = copy.deepcopy(self.cfg['generation'])
        self.cfg['generation']['timeout_seconds'] = 600
        self.out, self.stop, self.current_batch = OUT, False, 4
        self.run_id = 'openexempt_EV_factorized_B1_B8_TRAIN32_20261105_run01'
        self.native, self.teachers, self.reuse_events = [], [], []
        self.teacher_attempts, self.physical_attempts, self.started = 0, 0, None
        self.lock = threading.Lock()
        ref = read(REFERENCE); self.ids = sorted(ref['source_ids'])
        self.current = set(ref['current_source_ids'])
        self.screen_ids = set(read(SCREEN / 'protocol.json')['source_ids'])
        assert len(self.ids) == 32 and len(self.current) == 16
        self.rows = read(ROOT / self.cfg['input_packet'])['rows']
        self.by_row = {(r['case_id'], r['family']): r for r in self.rows}
        pubs = {a: read(OLD / 'publications' / ('b1.json' if a == 'B1' else 'b8.json')) for a in ['B1', 'B8']}
        self.banks = {a: p['bank'] for a, p in pubs.items()}
        self.bank = self.banks['B8']
        assert self.bank == read(OLD / 'completion.json')['bank']
        self.bindings = dict(read(CONFIG.with_suffix('.frozen.json'))['files'])
        for p in [Path(__file__), PROTOCOL, REFERENCE, OLD / 'publications/b1.json',
                  OLD / 'publications/b8.json', OLD / 'completion.json', SCREEN / 'protocol.json',
                  SCREEN / 'terminal.json', SCREEN / 'independent_verification_v1.json']:
            self.bindings[str(p)] = sha(p)
        replay = {a: {(r['case_id'], r['family']): r for r in
                      next(d for d in reversed(p['training_decisions']) if d['accepted'])['actual_replay']}
                  for a, p in pubs.items()}
        self.whole = {a: [] for a in self.banks}
        for cid in self.ids:
            row = self.by_row[cid, 'EV']
            for arm in self.banks:
                if arm == 'B8' or row['batch'] == 1:
                    record = replay[arm][cid, 'EV']
                else:
                    path = OLD / 'batches' / f"b{row['batch']}_prequential_records.json"
                    self.bindings[str(path)] = sha(path)
                    record = next(r for r in read(path)['frozen_after_B1'] if r['case_id'] == cid and r['family'] == 'EV')
                messages, schema, _ = actor_payload(row, self.banks[arm], grounded=True, direct_numeric=True, asset_references=True)
                raw = ROOT / record['raw_call_path']; inp = raw.with_suffix('.input.json')
                original = read(inp)
                assert original['messages'] == messages and original['schema'] == schema, (cid, arm)
                self.bindings[str(raw)], self.bindings[str(inp)] = sha(raw), sha(inp)
                self.whole[arm].append(copy.deepcopy(record))
        assert read(SCREEN / 'protocol.json')['generation'] == self.cfg['generation']
        assert read(SCREEN / 'terminal.json')['diagnostic_screen_passed']
        self.cache = {}
        for inp in sorted((SCREEN / 'native').glob('*.input.json')):
            d = read(inp); raw = inp.with_name(inp.name.removesuffix('.input.json') + '.json')
            fingerprint = csha({'messages': d['messages'], 'schema': d['schema'], 'generation': self.cfg['generation']})
            assert fingerprint not in self.cache
            self.cache[fingerprint] = raw
            self.bindings[str(raw)], self.bindings[str(inp)] = sha(raw), sha(inp)
        self.jobs = [(cid, arm, asset) for cid in self.ids for arm in ['B1', 'B8']
                     for asset in public_asset_catalog(self.by_row[cid, 'EV'])]
        fingerprints = [self.payload(*job)[3] for job in self.jobs]
        assert len(fingerprints) == len(set(fingerprints)) == 186
        cached = sum(f in self.cache for f in fingerprints)
        assert cached == 17 and len(fingerprints) - cached == 169
        self._dispatch = PhaseDispatch(self.cfg, environment=read(ROOT / self.cfg['inference_environment']),
                                       on_failure=lambda: setattr(self, 'stop', True))
        for sig in [signal.SIGINT, signal.SIGTERM]: signal.signal(sig, lambda *_: setattr(self, 'stop', True))
        self.check()
        assert WireClient(self.cfg['generation']).readiness()['ready']
        OUT.mkdir(exist_ok=False)
        RunStore.immutable_json(OUT / 'protocol.json', {
            'at': now(), 'TRAIN_only_not_formal_learning_or_TEST': True, 'source_ids': self.ids,
            'current_source_ids': sorted(self.current), 'screen_source_ids': sorted(self.screen_ids),
            'frozen_banks': self.banks, 'historical_whole_case_controls': self.whole,
            'generation': self.cfg['generation'], 'original_generation': self.original_generation,
            'planned_logical_requests': 186, 'planned_new_EV_generations': 169, 'planned_exact_wire_reuses': cached,
            'max_new_EV_generations': 176, 'max_teacher_calls': 0, 'max_actor_wall_seconds': 2700,
            'no_per_case_equal_compute_claim': True, 'frozen_files': self.bindings,
            'adoption_training_and_paper_changes_require_user_confirmation': True})

    def payload(self, cid, arm, asset):
        row = self.by_row[cid, 'EV']
        messages, schema, supplied = actor_payload(row, self.banks[arm], grounded=True, direct_numeric=True, asset_references=True)
        messages, schema = copy.deepcopy(messages), copy.deepcopy(schema)
        changes = 0
        for message in messages:
            for old, new in [
                ('Include every listed ID, using [] when no exemption is applicable.',
                 'This request covers exactly the focus asset_ref specified in the last message; output only that key, using [] when no exemption is applicable. Other asset mentions and all facts remain context.'),
                ('exactly all supplied case-local asset_ref keys',
                 'exactly the focus case-local asset_ref key specified in the last message')]:
                changes += message['content'].count(old)
                message['content'] = message['content'].replace(old, new)
        assert changes == 2
        schema['required'] = [asset]; schema['properties'] = {asset: schema['properties'][asset]}
        messages.append({'role': 'user', 'content': json.dumps({'focus_asset_ref': asset}, separators=(',', ':'))})
        fingerprint = csha({'messages': messages, 'schema': schema, 'generation': self.cfg['generation']})
        return messages, schema, supplied, fingerprint

    def answer(self, job):
        self.check()
        cid, arm, asset = job
        row = self.by_row[cid, 'EV']; messages, schema, supplied, fingerprint = self.payload(*job)
        path = OUT / 'native' / f'{cid}_{arm}_{asset}.json'
        RunStore.immutable_json(path.with_suffix('.input.json'), {
            'messages': messages, 'schema': schema, 'bank_sha256': csha(self.banks[arm]),
            'public_asset_catalog': public_asset_catalog(row), 'public_citation_catalog': public_catalog(row),
            'delivered_skill_ids': [s['id'] for s in supplied], 'fingerprint': fingerprint})
        if fingerprint in self.cache:
            source = self.cache[fingerprint]; original = read(source.with_suffix('.input.json'))
            assert original['messages'] == messages and original['schema'] == schema
            response = read(source)['response']
            alias = {'calls': [], 'response': response, 'reused_from': str(source.relative_to(ROOT)),
                     'source_sha256': sha(source), 'exact_wire_reuse_not_new_generation': True,
                     'fingerprint': fingerprint, 'bank_sha256': csha(self.banks[arm])}
            RunStore.immutable_json(path, alias)
            with self.lock: self.reuse_events.append(alias)
            self.progress('factorized_B1_B8_confirmation', current_arm=arm, current_document_id=cid)
        else:
            with self.lock:
                if self.physical_attempts >= 176 or time.monotonic() - self.started >= 2100:
                    raise TimeoutError('Authorized confirmation budget exhausted; no retry')
                self.physical_attempts += 1
            response = Comparison.call(self, path, messages, schema, self.cfg['generation']['max_tokens'], {
                'stage': 'factorized_B1_B8_confirmation', 'arm': arm, 'document_id': cid,
                'family': 'EV', 'call_role': 'openexempt', 'focus_asset_ref': asset,
                'bank_sha256': csha(self.banks[arm])})
        parsed = submission = None; error = None
        try:
            submission = json.loads(response['content']); validate(submission, schema)
            if response['finish_reason'] != 'stop': raise ValueError('Incomplete native output')
            values = decode_asset_references(copy.deepcopy(submission), {asset: public_asset_catalog(row)[asset]})
            parsed = {a: [{'citation': decode_reference(c['citation_ref'], public_catalog(row)), 'claim_value': c['claim_value']}
                          for c in cs] for a, cs in values.items()}
        except (ValidationError, ValueError, KeyError, TypeError) as exc: error = repr(exc)
        result = {'case_id': cid, 'arm': arm, 'asset_ref': asset, 'decoded_answer': parsed,
                  'parse_error': error, 'submission': submission, 'raw_call_path': str(path.relative_to(ROOT)),
                  'prompt_tokens': response['prompt_tokens'], 'completion_tokens': response['completion_tokens']}
        RunStore.immutable_json(path.with_suffix('.answer.json'), result)
        return result

    def run(self):
        self.started = time.monotonic()
        pieces = self._dispatch.native(self.answer, self.jobs)
        RunStore.immutable_json(OUT / 'all_subcall_predictions_before_grading.json', pieces)
        arms = {'whole_B1': self.whole['B1'], 'whole_B8': self.whole['B8'], 'factorized_B1': [], 'factorized_B8': []}
        for arm in self.banks:
            for cid in self.ids:
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
                    'bank_sha256': csha(self.banks[arm]), 'parsed': None if errors else {'answer': answer},
                    'parse_error': repr(errors) if errors else None, 'raw_subcall_paths': [p['raw_call_path'] for p in selected]})
        RunStore.immutable_json(OUT / 'full_case_predictions_before_grading.json', arms)
        for rs in arms.values(): self.grade(rs)
        RunStore.immutable_json(OUT / 'scored_records.json', arms)
        report = {}
        for arm, records in arms.items():
            cohorts = {'all32': set(self.ids), 'current16': self.current,
                       'prior16': set(self.ids)-self.current, 'screen8': self.screen_ids,
                       'remaining24': set(self.ids)-self.screen_ids}
            report[arm] = {name: metrics([r for r in records if r['case_id'] in cs])['EV'] for name, cs in cohorts.items()}
            counts = collections.Counter()
            for r in records:
                target = read(ROOT / self.cfg['grading_directory'] / f"{r['case_id']}.json")['targets']['EV']
                answer = r['parsed']['answer'] if r['parse_error'] is None else None
                assert evaluate(self.by_row[r['case_id'], 'EV'], answer, target) == r['score']
                fb = native_claim_feedback(r, target)
                counts.update({k: int(fb.get(k, 0)) for k in ['invalid_response', 'correct', 'missing', 'incorrect_value', 'extra_or_duplicate']})
            report[arm]['errors'] = dict(counts)
        gains = {a: {k: 100*(report['factorized_'+a]['all32'][k]-report['whole_'+a]['all32'][k])
                     for k in ['f1', 'full_output_f1']} for a in self.banks}
        evolution = {view: {c: {k: 100*(report[view+'_B8'][c][k]-report[view+'_B1'][c][k])
                              for k in ['f1', 'full_output_f1']}
                          for c in ['all32', 'current16', 'prior16', 'screen8', 'remaining24']}
                     for view in ['whole', 'factorized']}
        both = [(a, b) for a, b in zip(arms['whole_B8'], arms['factorized_B8']) if a['parse_error'] is None and b['parse_error'] is None]
        valid_gain = {k: 100*sum(b['score'][k]-a['score'][k] for a,b in both)/32 for k in ['f1', 'full_output_f1']}
        retain = all(report['factorized_B8'][c][k]+1e-12 >= report['whole_B8'][c][k]
                     for c in ['current16', 'prior16'] for k in ['f1', 'full_output_f1'])
        passed = (all(v>=2 for v in gains['B8'].values()) and retain and all(v>0 for v in valid_gain.values())
                  and report['factorized_B8']['all32']['invalid_format'] <= report['whole_B8']['all32']['invalid_format']
                  and report['factorized_B8']['errors'].get('incorrect_value',0) < report['whole_B8']['errors'].get('incorrect_value',0))
        costs = {a: {k: sum(p[k] for p in pieces if p['arm']==a) for k in ['prompt_tokens','completion_tokens']} for a in self.banks}
        result = {'at': now(), 'state': 'completed', 'conditions': report, 'factorization_gain_pp': gains,
            'B8_minus_B1_pp': evolution, 'B8_both_parseable_net_contribution_pp': valid_gain,
            'B8_execution_confirmation_passed': passed,
            'factorized_B8_exceeds_B1_both_metrics': all(v>0 for v in evolution['factorized']['all32'].values()),
            'actual_new_EV_generations': len(self.native), 'physical_attempts': self.physical_attempts,
            'exact_wire_reuses': len(self.reuse_events), 'logical_subtask_predictions': len(pieces),
            'new_teacher_calls': 0, 'actor_phase_elapsed_seconds': time.monotonic()-self.started,
            'actual_new_prompt_tokens': sum(r['response']['prompt_tokens'] for r in self.native),
            'actual_new_completion_tokens': sum(r['response']['completion_tokens'] for r in self.native),
            'logical_per_condition_deployment_tokens_including_cached_predictions': costs,
            'formal_method_or_paper_changed': False, 'adoption_requires_user_confirmation': True}
        RunStore.immutable_json(OUT / 'terminal.json', result)
        self.progress('terminal', state='completed')
        print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    runner = None
    try:
        with (ROOT / 'artifacts/openexempt_training.lock').open('w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            runner = Confirmation(); runner.run()
    except BaseException as exc:
        if OUT.exists() and not (OUT / 'failure.json').exists():
            RunStore.immutable_json(OUT / 'failure.json', {'at': now(), 'error': repr(exc),
                'traceback': traceback.format_exc(), 'physical_attempts': runner.physical_attempts if runner else None,
                'actual_completed_new_calls': len(runner.native) if runner else None,
                'failed_usage_unknown_not_zero': True, 'no_fallback_retry_or_partial_case_scoring': True})
        raise
