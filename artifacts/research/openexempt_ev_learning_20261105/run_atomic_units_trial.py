"""One authorized TRAIN-only skill-granularity trial, not another formal run.

Two artifact-safe stages: generate one proposal; inspect it before any candidate
answer; evaluate the original saved proposal once. No production code is edited.
"""
from __future__ import annotations

import argparse
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

OUT = Path(__file__).resolve().parent / 'atomic_rule_units_run01'
PREVIOUS = ROOT/'artifacts/research/openexempt_ev_learning_20261104/bounded_train_pilot_run01'
CONFIG = ROOT/'configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json'
PROTOCOL = ROOT/'docs/research/OPENEXEMPT_EV_ATOMIC_UNITS_TRAIN32_20261105.md'
WIRE = ROOT/'runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01/teacher/b4_candidate2/wire_request.json'
POLICY = (
    'EV rule-unit revision policy. The intervention is the granularity of reusable '
    'instructions, NOT more reminders, another output example, variable notation, '
    'an answer plan, a solver or an additional inference call. Locate coupled '
    'eligibility/amount decisions behind the supplied actual failures and retained '
    'regressions. Replace the overloaded EV projection where warranted with '
    'independently editable rule units in the EXISTING skill schema. A unit should '
    'have one coherent factual trigger and statutory amount mechanism. Put the '
    'trigger, applicable citation, correct whole-asset valuation and local exception '
    'together instead of separating them across distant clauses. Independent '
    'alternatives must remain independent output objects, each using its own '
    'asset value, debtor condition and ceiling. Distinct debtor-count or category '
    'conditions must not silently borrow one another\'s limit. This is not a fixed '
    'number of skills or a mandatory one-record-per-statute catalogue. Split only '
    'where actual TRAIN errors support the finer unit; keep compact coherent '
    'unchanged rules verbatim. Preserve every supported eligibility condition, '
    'exclusion and independently applicable alternative when extracting a unit. '
    'Remove the extracted rule from its old EV projection rather than leave two '
    'competing copies. Keep other-task EC fields, IDs and scope exactly unchanged. '
    'An old shared record may retain only EC while new EV-only records hold its '
    'decomposed rules. Use ordinary differential CREATE/UPDATE/DELETE/MERGE '
    'against original parent IDs. Diagnose structural inadequacy as SKILL_DEFECT; '
    'use an empty anchor for newly created projections and an actual same-ID '
    'parent anchor for an existing one where available. Resolve genuinely absent '
    'conditions from the supplied statute and released TRAIN evidence, without '
    'turning every ceiling into a universal per-debtor multiplier. A rule unit '
    'must work from the EV public inputs alone; do not assume a hidden EC answer. '
    'Do not add V/C/D notation or JSON examples as a substitute for an actual '
    'change in edit units. Do not store instances, asset names, debtors, source '
    'IDs or copied target amounts in runtime text. Do not add fields, operators '
    'or an execution layer. The entire shared bank including unchanged EC and '
    'all metadata must fit the ORIGINAL 4096-token cap; concise units must replace '
    'overloaded text, not accumulate a second playbook. If no grounded real '
    'decomposition fits these constraints, return an explicit NOOP.'
)


class Trial(Online):
    def __init__(self, stage):
        self.cfg = read(CONFIG)
        self.cfg['teacher']['capacity_retry_attempts'] = 0
        self.run_id = 'openexempt_EV_atomic_units_TRAIN32_20261105_run01'
        self.out = OUT
        self.reference = read(PREVIOUS/'protocol.json')
        self.bank = self.reference['parent_bank']
        self.parents = read(PREVIOUS/'parent_records.json')
        self.rows = read(ROOT/self.cfg['input_packet'])['rows']
        self.bindings = dict(read(CONFIG.with_suffix('.frozen.json'))['files'])
        for p in (Path(__file__), PROTOCOL, WIRE, PREVIOUS/'protocol.json',
                  PREVIOUS/'parent_records.json'):
            self.bindings[str(p)] = sha(p)
        self.stop = False
        self.current_batch = 4
        self.native, self.teachers, self.reuse_events = [], [], []
        self.teacher_attempts = self.native_attempts = 0
        self.request_cache = {}
        self.gpu_started = None
        self.budget_lock = threading.Lock()
        self._dispatch = PhaseDispatch(self.cfg,
            environment=read(ROOT/self.cfg['inference_environment']),
            on_failure=lambda: setattr(self, 'stop', True))
        self.answer = self._dispatch.locked_requests(self.answer,
            lambda *args, **kwargs: direct_request_key(self.cfg, *args, **kwargs))
        self.meter = WireClient(self.cfg['generation'])
        if stage == 'propose':
            OUT.mkdir(exist_ok=False)
        else:
            frozen = read(OUT/'protocol.json')
            assert frozen['bindings_before_teacher'] == self.bindings
            assert not (OUT/'evaluation_started.json').exists(), 'No resume or rerun'
        for sig in (signal.SIGINT, signal.SIGTERM):
            signal.signal(sig, lambda *_: setattr(self, 'stop', True))
        self.check()
        assert self.meter.readiness()['ready']

    def call(self, *args, **kwargs):
        with self.budget_lock:
            if self.gpu_started is None:
                self.gpu_started = time.monotonic()
            if time.monotonic()-self.gpu_started >= 1800:
                raise TimeoutError('Stop dispatch for the original 900-second drain')
            if self.native_attempts >= 64:
                raise RuntimeError('Authorized EV generation limit reached')
            self.native_attempts += 1
        return Comparison.call(self, *args, **kwargs)

    def cohort(self):
        ids = set(self.reference['source_ids'])
        result = sorted((r for r in self.rows if r['family']=='EV'
                         and r['case_id'] in ids), key=lambda r:r['case_id'])
        assert len(result)==len(ids)==32
        return result

    def seed_parent_cache(self):
        parents = {r['case_id']:r for r in self.parents}
        identity = []
        for row in self.cohort():
            record = parents[row['case_id']]
            raw_path = ROOT/record['raw_call_path']
            original = read(raw_path.with_suffix('.input.json'))
            messages, schema, _ = actor_payload(row, self.bank, grounded=True,
                direct_numeric=True, asset_references=True)
            assert messages==original['messages'] and schema==original['schema']
            fingerprint = csha({'messages':messages, 'schema':schema,
                                'generation':self.cfg['generation']})
            previous = next(r for r in self.reference['parent_native_identity']
                            if r['case_id']==row['case_id'])
            assert fingerprint==previous['fingerprint'] and sha(raw_path)==previous['raw_sha256']
            self.request_cache[fingerprint] = {'response':copy.deepcopy(read(raw_path)['response']),
                'raw_call_path':record['raw_call_path']}
            identity.append(previous)
        return identity


def propose(runner):
    wire = read(WIRE)
    body = json.loads(wire['user_prompt'])
    assert body['current_parent_library']==runner.bank
    assert body['training_evidence_manifest']['selected_source_ids']==runner.reference['source_ids']
    identity = runner.seed_parent_cache()
    RunStore.immutable_json(OUT/'protocol.json', {
        'at':now(), 'hypothesis':'independently_editable_statutory_rule_units',
        'policy':POLICY, 'parent_bank_sha256':csha(runner.bank),
        'source_ids':runner.reference['source_ids'],
        'current_source_ids':runner.reference['current_source_ids'],
        'same_original_teacher_packet_and_schema':True,
        'comparison_is_seen_TRAIN_development_not_TEST_or_formal_build':True,
        'teacher_invocations_max':1, 'new_EV_calls_max':64, 'actor_phase_seconds_max':2700,
        'generation':runner.cfg['generation'], 'complete_library_token_cap':4096,
        'minimum_each_mean_F1_gain_pp':1.0,
        'require_positive_net_gain_on_both_parseable_pairs':True,
        'original_EV_admission_contract':runner.cfg['admission_contract'],
        'parent_native_identity':identity, 'bindings_before_teacher':runner.bindings})
    response = runner.teacher_call('atomic_rule_units', wire['system_prompt']+'\n'+POLICY,
                                   wire['user_prompt'], wire['output_schema'])
    candidate = apply_differential_publication(runner.bank, response['delta'], FAMILIES,
        runner.reference['source_ids'], guidance_schema=DIRECT_GUIDANCE)
    RunStore.immutable_json(OUT/'candidate_unreviewed.json', {'candidate':candidate,
        'proposal':response, 'semantic_review_required_before_any_candidate_answer':True})
    audit = validate_edit_diagnoses(runner.bank, candidate, response['diagnoses'],
                                    runner.reference['source_ids'])
    validate_task_projection_edit(runner.bank, candidate, 'EV')
    validate_scoped_bank(candidate)
    validate_scopes(candidate, runner.rows[0]['components']['statutes'])
    before = {s['id']:s for s in task_view(runner.bank,'EV')}
    after = {s['id']:s for s in task_view(candidate,'EV')}
    old_counts = {ns:sum(s['guidance']['jurisdiction']==ns for s in before.values())
                  for ns in {s['guidance']['jurisdiction'] for s in before.values()}}
    created = sorted(after.keys()-before.keys())
    changed_old = sorted(k for k in before if before[k]!=after.get(k))
    finer = any(sum(s['guidance']['jurisdiction']==ns for s in after.values())>n
                for ns,n in old_counts.items())
    ec_rows = [r for r in runner.rows if r['family']=='EC']
    for row in ec_rows:
        a = actor_payload(row,runner.bank,grounded=True,direct_numeric=True,asset_references=True)
        b = actor_payload(row,candidate,grounded=True,direct_numeric=True,asset_references=True)
        assert a[:2]==b[:2], 'Protected EC payload changed'
    tokens = runner.meter.token_count(text=json.dumps(candidate,ensure_ascii=False,separators=(',',':')))
    result = {'at':now(), 'candidate':candidate, 'candidate_sha256':csha(candidate),
        'edit_audit':audit, 'created_EV_projection_ids':created,
        'changed_existing_EV_projection_ids':changed_old,
        'finer_rule_granularity_realized':bool(created and changed_old and finer),
        'tokens':tokens, 'all128_EC_payloads_identical':len(ec_rows)==128,
        'mechanical_checks_pass':bool(tokens<=4096 and created and changed_old and finer),
        'candidate_answers_generated':False, 'teacher_attempts':runner.teacher_attempts}
    RunStore.immutable_json(OUT/'proposal.json',result)
    runner.progress('awaiting_main_agent_semantic_review', teacher_attempts=runner.teacher_attempts)
    print(json.dumps({k:v for k,v in result.items() if k not in ['candidate','edit_audit']},ensure_ascii=False),flush=True)


def counts(records,runner):
    result = {k:0 for k in ['invalid_response','correct','missing','incorrect_value','extra_or_duplicate']}
    for record in records:
        target = read(ROOT/runner.cfg['grading_directory']/f"{record['case_id']}.json")['targets']['EV']
        fb = native_claim_feedback(record,target)
        for k in result:result[k]+=int(fb.get(k,0))
    return result


def evaluate_candidate(runner):
    proposal = read(OUT/'proposal.json')
    review = read(OUT/'semantic_review.json')
    assert review['proposal_file_sha256']==sha(OUT/'proposal.json')
    assert review['candidate_sha256']==proposal['candidate_sha256']
    if not proposal['mechanical_checks_pass'] or not review['proceed_to_original_actor']:
        RunStore.immutable_json(OUT/'terminal.json', {'at':now(),
            'state':'closed_before_candidate_generation', 'proposal':proposal,
            'review':review,'new_EV_generations':0,'new_teacher_invocations':1,
            'qualifies_for_one_full_training':False})
        return
    runner.bindings[str(OUT/'proposal.json')]=sha(OUT/'proposal.json')
    runner.bindings[str(OUT/'semantic_review.json')]=sha(OUT/'semantic_review.json')
    runner.seed_parent_cache()
    RunStore.immutable_json(OUT/'evaluation_started.json', {'at':now(),
        'candidate_sha256':proposal['candidate_sha256'],'frozen_files':runner.bindings,
        'all_forecasts_saved_before_unified_scoring':True})
    candidate = proposal['candidate']
    records = runner._dispatch.native(lambda r:runner.answer(r,candidate,'atomic_rule_units','candidate'),
                                      runner.cohort())
    RunStore.immutable_json(OUT/'predictions_before_grading.json',records)
    runner.grade(records)
    RunStore.immutable_json(OUT/'scored_records.json',records)
    current = set(runner.reference['current_source_ids'])
    pick = lambda rs,c:[r for r in rs if (r['case_id'] in current)==c]
    pm,cm = metrics(runner.parents)['EV'],metrics(records)['EV']
    gate = _head_admission('EV',metrics(pick(runner.parents,True)),metrics(pick(records,True)),
        metrics(pick(runner.parents,False)),metrics(pick(records,False)),
        contract=runner.cfg['admission_contract'])
    before = {r['case_id']:r for r in runner.parents}
    both = [(before[r['case_id']],r) for r in records
            if before[r['case_id']]['parse_error'] is None and r['parse_error'] is None]
    gains = {k:100*(cm[k]-pm[k]) for k in ['f1','full_output_f1']}
    valid_gains = {k:sum(b['score'][k]-a['score'][k] for a,b in both)/32*100
                   for k in ['f1','full_output_f1']}
    qualifies = bool(gate['accepted'] and min(gains.values())>=1.0-1e-10
                     and min(valid_gains.values())>1e-10)
    result = {'at':now(),'state':'completed','parent_metrics':pm,'candidate_metrics':cm,
        'gain_pp':gains,'both_parseable_pair_net_contribution_pp':valid_gains,
        'original_pilot_cohort_EV_gate':gate,'parent_errors':counts(runner.parents,runner),
        'candidate_errors':counts(records,runner),'actual_new_EV_generations':len(runner.native),
        'exact_complete_request_reuses':len(runner.reuse_events),
        'new_teacher_invocations':1,'actor_phase_elapsed_seconds':(
            time.monotonic()-runner.gpu_started if runner.gpu_started is not None else 0),
        'qualifies_for_one_full_training':qualifies,
        'original_paper_or_production_code_changed':False}
    RunStore.immutable_json(OUT/'terminal.json',result)
    runner.progress('terminal',state='completed',qualifies_for_one_full_training=qualifies)
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['propose','evaluate'])
    args=parser.parse_args()
    try:
        runner=Trial(args.stage)
        (propose if args.stage=='propose' else evaluate_candidate)(runner)
    except BaseException as exc:
        if OUT.exists():
            dest=OUT/(args.stage+'_failure.json')
            if not dest.exists():RunStore.immutable_json(dest,{'at':now(),'error':repr(exc),
                'traceback':traceback.format_exc(),'no_fallback_or_quality_retry':True})
        raise
