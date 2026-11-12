"""Recover one rejected strong-control response without another teacher call.

Same first-update context, unchanged raw output and native admission rule. Later
parents are frozen probes of this B2 asset, not a replacement B3 training build.
"""
from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.objects import Library, digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads, SkillRuntime
from legal_skill_guard.skill_evolution.study import Study
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot


def read(p):return json.loads(p.read_text())


def main():
    root = Path(__file__).resolve().parents[1]
    original = Path('/home/yndx/hhy/legal-skill-redesign-20261109')
    previous = root / 'artifacts/legal_skill_evolution_contract_updates_20261112'
    if not (previous / 'completed.json').exists():raise ValueError('Original run must be terminal and preserved')
    old_protocol = read(previous / 'protocol.json')
    keys = old_protocol['previously_fixed_source_order']
    jobs = [{'arm': 'AllPorts+CoRev', 'batch': 2, 'frozen_probes': keys[2:]},
            {'arm': 'FreeEvolution', 'batch': 3, 'frozen_probes': keys[3:]}]
    run_id = 'legal_skill_evolution_contract_read_recovery_20261112'
    folder = root / 'artifacts' / run_id
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve()]
    protocol = {'run_id': run_id, 'same_goal': True, 'goal_complete': False,
        'purpose': 'Restore actual AllPorts B2 and Free B3 responses after fixing READ lineage and exact named-source-heading contracts; no legal values or quotes filled.',
        'old_run_preserved': True, 'original_protocol_hash': digest(old_protocol),
        'already_fixed_original_TRAIN': keys,
        'jobs': [{**j, 'same_trigger': keys[j['batch'] - 1], 'same_history': keys[:j['batch'] - 1],
            'raw_teacher_file_sha256': hashlib.sha256((previous / j['arm'] / f"teacher_B{j['batch']}.json").read_bytes()).hexdigest(),
            'actual_old_library_hash': Library.load(previous / j['arm'] / f"B{j['batch'] - 1}.json").hash} for j in jobs],
        'teacher_calls': 0, 'teacher_dispatch_disabled': True,
        'comparison_limit': 'Two separate original-context recoveries. AllPorts B3 was not retrained on the recovered B2 library; do not merge these assets or replace the original two-update trajectory.',
        'admission': 'Same complete old/new table, strict trigger gain and every history parent nondecreasing.',
        'offline_diagnosis': 'Actual raw AllPorts response compiles when only empty current-READ lineage is omitted from static constant-origin validation. All nonempty lineage, constant origins, source obligations and source provenance remain checked. Runtime requires typed known values with current-source spans.',
        'model_profile': old_protocol['executor_profile'], 'automatic_retries': 0,
        'offline_regressions_passed': 89,
        'no_new_sources_DEV_TEST_full_training_or_teacher': True,
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}
    immutable_json(folder / 'protocol.json', protocol)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before = physical_snapshot(ledger_path)
        if any(v.get('reserved', 0) for v in before.values()):raise ValueError('Reconcile actual pending requests first')
        immutable_json(folder / 'ledger_before.json', before)
        profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
        prepared = original / 'artifacts/legal_skill_evolution_20261111/prepared/train'
        records = {r['key']: r for r in read(prepared / 'public.json')}
        grading = read(prepared / 'grading.json')
        sources = {'train': keys, 'dev': [], 'test': []}
        ledger = EvolutionLedger(ledger_path, run_id=run_id, sources=sources, binding=digest(protocol))
        replay_roots = [previous, original / profile['artifacts']]
        for rel in profile.get('exact_replay_profiles', []):
            prior = read(original / rel)
            if digest(prior['executor']) != digest(profile['executor']):raise ValueError('Executor profile differs')
            replay_roots.append(original / prior['artifacts'])
        outcomes = []
        for job in jobs:
            arm, batch = job['arm'], job['batch']
            study = object.__new__(Study)
            study.root, study.folder, study.stage = root, folder / (arm + '_B' + str(batch)), 'contract_read_recovery'
            study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}}
            study.records = {k: records[k] for k in keys};study.grading = {k: grading[k] for k in keys}
            study.source_ids = sources
            study.batches, study.order, study.arms = [[k] for k in keys[:batch]], keys[:batch], (arm,)
            study.ledger = ledger
            study.executor = FrozenExecutor(ledger, study.folder, profile['executor'])
            study.executor.exact_replay_roots = list(replay_roots)
            study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
            study.teacher = None  # No teacher instance exists on this recovery path.
            seed = Library.load(previous / arm / f'B{batch - 1}.json');p = study.library_path(arm, batch - 1)
            if p.exists():
                if Library.load(p).hash != seed.hash:raise ValueError('Actual old library changed')
            else:seed.save(p)
            immutable_json(study.folder / arm / f'teacher_B{batch}.json', read(previous / arm / f'teacher_B{batch}.json'))
            study.initial_batch(arm, batch)
            update = study.update(arm, batch)
            final = Library.load(study.library_path(arm, batch))
            probes = [study.parent(k, final) for k in job['frozen_probes']]
            outcomes.append({**job, 'update': update, 'frozen_probe_results': probes})
            replay_roots.append(study.folder)
        result = {'utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'teacher_response_reused_exactly': True, 'new_teacher_calls': 0,
            'jobs': outcomes,
            'ledger_before': before, 'ledger_after': physical_snapshot(ledger_path),
            'comparison_limit': protocol['comparison_limit']}
        if result['ledger_after']['teacher']['total'] != before['teacher']['total']:
            raise ValueError('Unexpected teacher dispatch')
        immutable_json(folder / 'completed.json', result)
        return result


if __name__ == '__main__':
    result = main();print(json.dumps({'completed': True, 'goal_complete': False,
        'ledger': result['ledger_after'], 'new_teacher_calls': 0}))
