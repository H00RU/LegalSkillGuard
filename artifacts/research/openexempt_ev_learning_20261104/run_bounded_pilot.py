"""One fixed, previously observed TRAIN packet; original actor and scoring only.

Development pilot, NOT a formal training run or a TEST result. At most two
teacher invocations and 64 candidate EV requests on the same 32 sources.
"""
from __future__ import annotations

import copy
import json
import signal
import sys
import threading
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from experiments.openexempt_online import (
    DIRECT_GUIDANCE, FAMILIES, Online, _head_admission, actor_payload,
    direct_request_key, native_claim_feedback, validate_edit_diagnoses,
    validate_task_projection_edit,
)
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.inference.native import WireClient
from legal_skill_guard.learning.experiment import Comparison, now, read, sha
from legal_skill_guard.learning.legal_namespace import validate_scopes
from legal_skill_guard.learning.phase_dispatch import PhaseDispatch
from legal_skill_guard.learning.publication import apply_differential_publication
from legal_skill_guard.learning.task_scoped_skills import task_view, validate_scoped_bank
from legal_skill_guard.openexempt import metrics
from legal_skill_guard.utils.hashing import canonical_json_sha256 as csha

OUT = Path(__file__).resolve().parent / 'bounded_train_pilot_run01'
OLD = ROOT / 'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01'
CONFIG = ROOT / 'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json'
WIRE = OLD / 'teacher/b4_candidate2/wire_request.json'
PROTOCOL = ROOT / 'docs/research/OPENEXEMPT_EV_DIRECTED_OPTIMIZATION_20261104.md'

# These are alternative general teaching policies, not hand-authored legal skills.
# Both use exactly the same historical packet, parent, schema and released labels.
HYPOTHESES = [
    ('minimal_value_binding',
     'EV revision policy: first localize each observed defect to (1) an absent or '
     'incorrect eligibility condition, (2) an absent independently applicable '
     'alternative, or (3) the value attached to an already correctly selected '
     'alternative. Use the smallest instruction edit that corrects the demonstrated '
     'decision. For (3), keep the existing eligibility catalogue and exclusions '
     'verbatim; edit only the faulty amount-binding clause. Make that clause bind '
     'the public debtor/ownership condition, the particular statutory ceiling and '
     'the WHOLE named asset value to the SAME citation. Do not transfer a ceiling '
     'or debtor multiplier from a different citation or jurisdiction. Preserve '
     'correct sibling alternatives and their distinct amounts. For (1) or (2), '
     'change only the evidenced condition or add the absent alternative; do not '
     'regenerate the whole jurisdiction. A genuinely absent task projection may '
     'be created normally. Repeated errors warrant a clearer local representation, '
     'not a wholesale rewrite of otherwise supported boundaries. In rejected '
     'candidate feedback, inspect losses of previously correct alternatives and '
     'changed amounts in unchanged co-visible guidance before repeating that '
     'proposal. Keep all correct unrelated when/procedure/avoid_when text verbatim. '
     'Do not use instance IDs, facts or amounts in runtime guidance.'),
    ('independent_output_illustration',
     'EV revision policy: preserve all supported eligibility and numeric rules '
     'in the current parent. When an amount/coverage error persists despite the '
     'correct rule, prefer one compact deidentified output-construction illustration '
     'inside the affected existing skill, not a longer rule catalogue or another '
     'generic checklist. The illustration should make clear that two independently '
     'eligible citations remain two separate output objects, each with its OWN '
     'whole-asset amount computed under its OWN condition and ceiling. If illustrative '
     'numbers are used, mark them hypothetical; never copy an actual training asset '
     'or target set. Use the existing diagnosis/anchor contract: an isolated '
     'EXECUTION_LAPSE preserves the exact knowledge prefix, when and avoid_when; '
     'a recurrent representational SKILL_DEFECT may be repaired locally while '
     'preserving correct unrelated clauses. A genuinely missing rule may be added '
     'from supplied law and evidence, without changing unrelated eligibility '
     'catalogues. Retain at most one compact illustration per affected block. '
     'Inspect rejected-candidate harm to previously correct alternatives; do not '
     'repeat the same broad rewrite. No new inference step, layer or solver.'),
]


class Pilot(Online):
    """Use production actor/teacher methods without creating a formal Online run."""
    def __init__(self):
        self.cfg = read(CONFIG)
        self.cfg['teacher']['capacity_retry_attempts'] = 0  # strict two-call ceiling
        self.run_id = 'openexempt_ev_bounded_train_pilot_20261104_run01'
        self.out = OUT
        self.bindings = dict(read(CONFIG.with_suffix('.frozen.json'))['files'])
        for p in (Path(__file__), PROTOCOL, WIRE):
            self.bindings[str(p)] = sha(p)
        self.stop = False
        self.current_batch = 4
        self.native, self.teachers, self.reuse_events = [], [], []
        self.teacher_attempts = 0
        self.request_cache = {}
        self.bank = read(OLD / 'publications/b3.json')['bank']
        self.rows = read(ROOT / self.cfg['input_packet'])['rows']
        self._dispatch = PhaseDispatch(self.cfg,
            environment=read(ROOT / self.cfg['inference_environment']),
            on_failure=lambda: setattr(self, 'stop', True))
        self.answer = self._dispatch.locked_requests(self.answer,
            lambda *args, **kwargs: direct_request_key(self.cfg, *args, **kwargs))
        self.budget_lock = threading.Lock()
        self.gpu_started = None
        self.native_attempts = 0
        self.meter = WireClient(self.cfg['generation'])
        OUT.mkdir(exist_ok=False)
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, 'stop', True))
        self.check()
        assert self.meter.readiness()['ready']

    def call(self, *args, **kwargs):
        with self.budget_lock:
            if self.gpu_started is None:
                self.gpu_started = time.monotonic()
            if time.monotonic() - self.gpu_started >= 2700:
                # Stop dispatch by 45 minutes; four in-flight calls each timeout
                # at 900s, keeping the entire actor phase within one hour.
                raise TimeoutError('Bounded GPU dispatch time exhausted')
            if self.native_attempts >= 64:
                raise RuntimeError('Fixed two-by-32 EV request budget exhausted')
            self.native_attempts += 1
        return Comparison.call(self, *args, **kwargs)


def error_counts(records, runner):
    result = {k: 0 for k in ('invalid_response', 'correct', 'missing',
                             'incorrect_value', 'extra_or_duplicate')}
    for r in records:
        target = read(ROOT / runner.cfg['grading_directory'] /
                      f"{r['case_id']}.json")['targets']['EV']
        feedback = native_claim_feedback(r, target)
        for k in result:
            result[k] += int(feedback.get(k, 0))
    return result


def execute():
    runner = Pilot()
    wire = read(WIRE)
    body = json.loads(wire['user_prompt'])
    ids = body['training_evidence_manifest']['selected_source_ids']
    current_ids = set(body['current_source_case_ids'])
    assert len(ids) == len(set(ids)) == 32 and len(current_ids) == 16
    assert body['current_parent_library'] == runner.bank
    rows = [r for r in runner.rows if r['family'] == 'EV' and r['case_id'] in ids]
    rows.sort(key=lambda r: r['case_id'])
    latest = {}
    for batch in range(1, 5):
        first = read(OLD / 'batches' / f'b{batch}_prequential_records.json')['skills']
        latest.update({(r['case_id'], r['family']): r for r in first})
        if batch < 4:
            for d in read(OLD / 'publications' / f'b{batch}.json')['training_decisions']:
                if d['accepted']:
                    latest = {(r['case_id'], r['family']): r for r in d['actual_replay']}
    parents = [latest[r['case_id'], 'EV'] for r in rows]
    # Verify original full actor messages/schema before reusing actual parent
    # native responses; no synthetic parent or merely matching bank hashes.
    identity = []
    for row, parent in zip(rows, parents):
        messages, schema, _ = actor_payload(row, runner.bank, grounded=True,
            direct_numeric=True, asset_references=True)
        raw = ROOT / parent['raw_call_path']
        old_input = read(raw.with_suffix('.input.json'))
        assert messages == old_input['messages'] and schema == old_input['schema']
        fingerprint = csha({'messages': messages, 'schema': schema,
                            'generation': runner.cfg['generation']})
        runner.request_cache[fingerprint] = {
            'response': copy.deepcopy(read(raw)['response']),
            'raw_call_path': parent['raw_call_path']}
        identity.append({'case_id': row['case_id'], 'fingerprint': fingerprint,
                         'raw_call_path': parent['raw_call_path'], 'raw_sha256': sha(raw)})
    RunStore.immutable_json(OUT/'protocol.json', {
        'at': now(), 'development_TRAIN_pilot_not_TEST_or_formal_training': True,
        'packet': str(WIRE.relative_to(ROOT)), 'packet_sha256': sha(WIRE),
        'source_ids': ids, 'current_source_ids': sorted(current_ids),
        'source_selection': 'unchanged historical B4 EV communication packet',
        'parent_bank': runner.bank, 'parent_bank_sha256': csha(runner.bank),
        'unchanged_common_generation': runner.cfg['generation'],
        'hypotheses_in_fixed_order': HYPOTHESES,
        'max_teacher_invocations': 2, 'max_new_EV_requests': 64,
        'max_GPU_wall_seconds_including_drain': 3600,
        'stop_after_first_qualifying_hypothesis': True,
        'minimum_pilot_mean_native_and_full_gain_pp': 1.0,
        'original_admission_applied_only_to_fixed_pilot_cohorts_not_full_seen_TRAIN': True,
        'requires_fresh_full_run_with_all_seen_TRAIN_gate_before_paper_use': True,
        'parent_native_identity': identity, 'frozen_files': runner.bindings})
    RunStore.immutable_json(OUT/'parent_records.json', parents)
    results = []
    for name, policy in HYPOTHESES:
        runner.check()
        if runner.teacher_attempts >= 2:
            break
        proposal = runner.teacher_call(name, wire['system_prompt'] + '\n' + policy,
                                       body, wire['output_schema'])
        candidate = apply_differential_publication(runner.bank, proposal['delta'],
            FAMILIES, ids, guidance_schema=DIRECT_GUIDANCE)
        audit = validate_edit_diagnoses(runner.bank, candidate, proposal['diagnoses'], ids)
        validate_task_projection_edit(runner.bank, candidate, 'EV')
        validate_scoped_bank(candidate)
        validate_scopes(candidate, rows[0]['components']['statutes'])
        assert task_view(candidate, 'EC') == task_view(runner.bank, 'EC')
        tokens = runner.meter.token_count(text=json.dumps(candidate, ensure_ascii=False,
                                                       separators=(',', ':')))
        result = {'hypothesis': name, 'candidate': candidate, 'edit_audit': audit,
                  'tokens': tokens, 'parent_records': str(OUT/'parent_records.json'),
                  'qualifies_for_one_full_training': False}
        if candidate == runner.bank or tokens > runner.cfg['library_token_hard_cap']:
            result['reason'] = 'NOOP_or_original_token_cap'
        else:
            records = runner.grade(runner._dispatch.native(
                lambda r: runner.answer(r, candidate, name, 'candidate'), rows))
            RunStore.immutable_json(OUT/f'{name}_scored_records.json', records)
            pick = lambda values, current: [r for r in values
                if (r['case_id'] in current_ids) == current]
            pm, cm = metrics(parents)['EV'], metrics(records)['EV']
            admission = _head_admission('EV',
                metrics(pick(parents, True)), metrics(pick(records, True)),
                metrics(pick(parents, False)), metrics(pick(records, False)),
                contract=runner.cfg['admission_contract'])
            gains = {k: 100*(cm[k]-pm[k]) for k in ('f1', 'full_output_f1')}
            result.update({'parent_metrics': pm, 'candidate_metrics': cm,
                'pilot_cohort_admission': admission, 'gains_pp': gains,
                'parent_errors': error_counts(parents, runner),
                'candidate_errors': error_counts(records, runner),
                'qualifies_for_one_full_training': bool(admission['accepted']
                    and min(gains.values()) >= 1.0 - 1e-10)})
        RunStore.immutable_json(OUT/f'{name}_result.json', result)
        results.append(result)
        print(json.dumps({k: v for k, v in result.items() if k not in
            ('candidate', 'edit_audit', 'pilot_cohort_admission')}, ensure_ascii=False), flush=True)
        if result['qualifies_for_one_full_training']:
            break
    RunStore.immutable_json(OUT/'terminal.json', {'at': now(), 'state': 'completed',
        'results': results, 'actual_new_native_calls': len(runner.native),
        'native_attempts': runner.native_attempts, 'teacher_attempts': runner.teacher_attempts,
        'actual_successful_teachers': len(runner.teachers),
        'actor_phase_elapsed_seconds': (time.monotonic()-runner.gpu_started
            if runner.gpu_started is not None else 0),
        'old_results_or_paper_changed': False})


if __name__ == '__main__':
    try:
        execute()
    except BaseException as exc:
        if OUT.is_dir() and not (OUT/'failure.json').exists():
            RunStore.immutable_json(OUT/'failure.json', {'at': now(), 'error': repr(exc),
                'traceback': traceback.format_exc(), 'no_fallback_or_synthetic_result': True})
        raise
