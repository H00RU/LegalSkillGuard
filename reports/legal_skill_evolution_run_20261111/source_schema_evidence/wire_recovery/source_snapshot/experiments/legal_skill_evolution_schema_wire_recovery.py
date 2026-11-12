"""Retry only the nine rejected control requests after an offline wire repair.

Both independent teacher proposals and all nine actual candidate reads remain
unchanged. This is a serving compatibility repair, not a new learner iteration.
"""
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.source_schema import compile_schema
from experiments.legal_skill_evolution_schema_induction import evaluate_source
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot, status

RUN = 'legal_skill_evolution_schema_wire_recovery_20261112'


def read(path):return json.loads(path.read_text())


def run(root):
    prior = root / 'artifacts/legal_skill_evolution_schema_induction_20261112'
    folder = root / 'artifacts' / RUN;folder.mkdir(exist_ok=True)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        old, old_protocol = read(prior / 'completed.json'), read(prior / 'protocol.json')
        proof = read(prior / 'wire_compatibility_offline.json')
        if not (proof['all_original_grammar_strings_equal'] and proof['all_repaired_schemas_pass_server_check']
                and proof['old_failed_requests'] == 9 and proof['regressions_passed'] == 126):
            raise ValueError('Require actual failure reproduction, equivalent decoder grammars and strict host-check regressions')
        spec = compile_schema(read(prior / 'FreeStrongControl/teacher.json')['value'], restricted=False)
        if digest(spec) != old['updates']['FreeStrongControl']['candidate_hash']:
            raise ValueError('The learned baseline policy changed')
        code = list((root / 'legal_skill_guard/skill_evolution').glob('*.py')) + list((root / 'tests').glob('test_skill_evolution_*.py'))
        code += [Path(__file__).resolve(), root / 'experiments/legal_skill_evolution_schema_induction.py']
        protocol = {'run_id': RUN, 'same_goal': True, 'goal_complete': False,
            'repair': 'Remove uniqueItems only from decoder grammar; keep exact original prompt and strict original host schema. Installed vLLM rejects explicit array uniqueItems even though xgrammar ignores it.',
            'before': old_protocol['run_id'], 'old_protocol_hash': digest(old_protocol),
            'teacher_sources': old_protocol['teacher_sources'], 'frozen_TRAIN_probes': old_protocol['frozen_TRAIN_probes'],
            'workload': 'Retry each of the nine original HTTP400 control requests once after the explicit wire fix. No new teacher, candidate read, source, seed, policy or scientific update.',
            'source_probe_status': 'Same fixed original TRAIN probes; original policy frozen before prior grading. They are not a new blind set.',
            'teacher_result_sha256': hashlib.sha256((prior / 'FreeStrongControl/teacher.json').read_bytes()).hexdigest(),
            'candidate_original_reads_reused_without_new_calls': 9,
            'offline_evidence_sha256': hashlib.sha256((prior / 'wire_compatibility_offline.json').read_bytes()).hexdigest(),
            'executor_profile': old_protocol['executor_profile'], 'teacher_profile': old_protocol['teacher_profile'],
            'admission': old_protocol['admission'],
            'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(code)}}
        immutable_json(folder / 'protocol.json', protocol)
        path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        if any(r.get('reserved', 0) for r in physical_snapshot(path).values()):raise ValueError('Pending requests exist')
        if not (folder / 'ledger_before.json').exists():immutable_json(folder / 'ledger_before.json', physical_snapshot(path))
        ledger = EvolutionLedger(path, run_id=RUN,
            sources={'train': protocol['teacher_sources'] + protocol['frozen_TRAIN_probes'], 'dev': [], 'test': []}, binding=digest(protocol))
        reads = FrozenReads(FrozenExecutor(ledger, folder, protocol['executor_profile']))
        public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
        grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
        baseline = {}
        for batch in range(1, 9):
            for row in read(root / 'artifacts/legal_skill_evolution_20261111/formal_v5/NoSkill' / f'initial_B{batch}.json')['results']:
                baseline[row['source']] = row
        arm = 'FreeStrongControl';calibration = {}
        for key in protocol['teacher_sources']:
            status(folder, phase='unchanged_policy_after_wire_repair', source=key)
            calibration[key] = evaluate_source(folder, arm, spec, public[key], grading[key], baseline[key], reads)
        reference = old['updates'][arm]['history_reference']
        gain = sum(calibration[k]['native_grade'] - baseline[k]['native_grade'] for k in old_protocol['trigger']) / len(old_protocol['trigger'])
        retained = all(calibration[k]['native_grade'] >= reference[k] for k in old_protocol['history'])
        update = {**old['updates'][arm], 'strict_trigger_gain': gain, 'history_nonregression': retained,
                  'accepted': gain > 0 and retained, 'wire_repair_only': True}
        immutable_json(folder / arm / 'frozen_candidate.json', {'schema': spec, 'update': update,
            'scientific_candidate_unchanged_since_original_freeze': True})
        probes = []
        for key in protocol['frozen_TRAIN_probes']:
            status(folder, phase='same_fixed_TRAIN_probes_after_wire_repair', source=key)
            probes.append(evaluate_source(folder, arm, spec, public[key], grading[key], baseline[key], reads))
        merged = {**old, 'completed_utc': datetime.now(timezone.utc).isoformat(), 'protocol_hash': digest(protocol),
            'calibration': {**old['calibration'], arm: calibration}, 'updates': {**old['updates'], arm: update},
            'frozen_TRAIN_probes': {**old['frozen_TRAIN_probes'], arm: probes},
            'ledger_after': physical_snapshot(path), 'original_completed_result_retained': str(prior.relative_to(root)) + '/completed.json',
            'all_original_failures_charged': True, 'no_teacher_or_candidate_read_repeated': True,
            'goal_complete': False, 'semantic_and_contribution_review_pending': True}
        immutable_json(folder / 'completed.json', merged)
        status(folder, phase='terminal_semantic_review_pending', ledger=merged['ledger_after'])
        return merged


if __name__ == '__main__':
    x = run(Path(__file__).resolve().parents[1]);print(json.dumps({'updates': x['updates'], 'ledger': x['ledger_after']}))
