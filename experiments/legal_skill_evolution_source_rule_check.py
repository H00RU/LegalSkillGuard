"""One actual rejected proposal, one changed rule-reading path, no teacher.

Re-execute the original old/new table and its fixed TRAIN reuse parent. This
tests source acquisition, not a fresh independent method comparison.
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
    prior = root / 'artifacts/legal_skill_evolution_contract_updates_20261112'
    recovery = root / 'artifacts/legal_skill_evolution_contract_read_recovery_20261112'
    if not (recovery / 'completed.json').exists():raise ValueError('Previous run must be terminal')
    keys = read(prior / 'protocol.json')['previously_fixed_source_order']
    run_id = 'legal_skill_evolution_source_rule_check_20261112'
    folder = root / 'artifacts' / run_id
    paths = list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    paths += list((root / 'tests').glob('test_skill_evolution_*.py')) + [Path(__file__).resolve()]
    seed = Library.load(prior / 'FreeEvolution/B2.json')
    raw = prior / 'FreeEvolution/teacher_B3.json'
    profile = read(original / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    protocol = {'run_id': run_id, 'same_goal': True, 'goal_complete': False,
        'question': 'Does the concrete source-rule reading repair resolve the observed hypothesis-dependent Boolean and unexpanded defined groups, without changing the actual proposed legal programs?',
        'changes': ['Rule READ excludes the separately supplied native question, native view ID and current_question argument; retains full rule material and other explicit arguments.',
            'Use already-public source sentence boundaries, retaining all non-whitespace source text and exact offsets, without native evidence labels.',
            'Common source-reading instruction requests the explicit definition for a requested member class; unknowns are not defaulted.'],
        'already_fixed_original_TRAIN_parents': keys, 'trigger': keys[2], 'history': keys[:2],
        'frozen_reuse': keys[3], 'proposal_arm': 'FreeEvolution', 'batch': 3,
        'same_actual_old_library_hash': seed.hash,
        'unchanged_raw_teacher_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
        'workload': 'One existing two-revision package, its complete four-cell/three-parent table, then the previously fixed fourth TRAIN parent once. No new proposals, teacher, seed or source.',
        'teacher_dispatch_disabled': True, 'offline_regressions_passed': 91,
        'native_admission': 'Unchanged strict trigger improvement and every history parent nondecreasing; unresolved and fallback remain ordinary outcomes.',
        'interpretation': 'A repair and real prerequisite check. A joint-needed table from this existing Free proposal would not by itself establish CoRev pattern learning, cross-source use or advantage over a strong control.',
        'no_new_full_training_DEV_TEST_or_paper': True, 'automatic_retries': 0,
        'executor_profile': profile['executor'],
        'code_sha256': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}}
    immutable_json(folder / 'protocol.json', protocol)
    with (folder / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if (folder / 'completed.json').exists():return read(folder / 'completed.json')
        ledger_path = original / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
        before = physical_snapshot(ledger_path)
        if any(x.get('reserved', 0) for x in before.values()):raise ValueError('Reconcile actual pending requests first')
        immutable_json(folder / 'ledger_before.json', before)
        study = object.__new__(Study)
        study.root, study.folder, study.stage = root, folder, 'source_rule_check'
        study.profile = {**deepcopy(profile), 'prior_logical_replay_executions': {}}
        prepared = original / 'artifacts/legal_skill_evolution_20261111/prepared/train'
        records = {s['key']: s for s in read(prepared / 'public.json')};grading = read(prepared / 'grading.json')
        study.records, study.grading = {k: records[k] for k in keys}, {k: grading[k] for k in keys}
        study.source_ids = {'train': keys, 'dev': [], 'test': []}
        study.batches, study.order, study.arms = [[k] for k in keys[:3]], keys[:3], ('FreeEvolution',)
        study.ledger = EvolutionLedger(ledger_path, run_id=run_id, sources=study.source_ids, binding=digest(protocol))
        study.executor = FrozenExecutor(study.ledger, folder, profile['executor'])
        study.executor.exact_replay_roots = [prior, original / profile['artifacts'],
            recovery / 'AllPorts+CoRev_B2', recovery / 'FreeEvolution_B3']
        for rel in profile.get('exact_replay_profiles', []):
            previous = read(original / rel)
            if digest(previous['executor']) != digest(profile['executor']):raise ValueError('Frozen model profile differs')
            study.executor.exact_replay_roots.append(original / previous['artifacts'])
        study.reads = FrozenReads(study.executor);study.runtime = SkillRuntime(study.reads)
        study.teacher = None
        p = study.library_path('FreeEvolution', 2)
        if p.exists():
            if Library.load(p).hash != seed.hash:raise ValueError('Actual old library changed')
        else:seed.save(p)
        immutable_json(folder / 'FreeEvolution/teacher_B3.json', read(raw))
        study.initial_batch('FreeEvolution', 3)
        update = study.update('FreeEvolution', 3)
        reuse = study.parent(keys[3], Library.load(study.library_path('FreeEvolution', 3)))
        after = physical_snapshot(ledger_path)
        if after['teacher']['total'] != before['teacher']['total']:raise ValueError('Unexpected teacher dispatch')
        result = {'utc': datetime.now(timezone.utc).isoformat(), 'goal_complete': False,
            'update': update, 'reuse_result': reuse,
            'ledger_before': before, 'ledger_after': after,
            'new_teacher_calls': 0, 'semantic_review_pending': True}
        immutable_json(folder / 'completed.json', result)
        return result


if __name__ == '__main__':
    result = main();print(json.dumps({'completed': True, 'goal_complete': False,
        'ledger': result['ledger_after'], 'new_teacher_calls': 0}))
