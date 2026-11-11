"""One frozen affected-candidate replay, not a new acquisition/learning epoch."""
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.skill_evolution.objects import Library, Skill, digest, apply_revision_package
from legal_skill_guard.skill_evolution.study import Study, load_json, PILOT_ARMS
from legal_skill_guard.skill_evolution.teacher import compile_block
from legal_skill_guard.skill_evolution.runtime import retrieve
from legal_skill_guard.skill_evolution.revisions import VersionTable, trigger_revision_reachability

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = ROOT / 'artifacts/legal_skill_evolution_20261111/pilot_v11'
FOLDER = ROOT / 'artifacts/legal_skill_evolution_20261111/repair_v13'
PROFILE = ROOT / 'configs/legal_skill_evolution_repair_v13_20261111.json'


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def original_candidates(arm, batch):
    paths = sorted((ORIGINAL / arm / f'B{batch}_candidates').glob('*.json'))
    if paths:return [(int(p.stem), load_json(p)) for p in paths]
    return [(e['candidate_index'], e) for e in load_json(ORIGINAL / arm / f'B{batch}.json')['provisional_edits']
            if e['batch'] == batch]


def prepare():
    with sqlite3.connect(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        if db.execute("select count(*) from calls where status='reserved'").fetchone()[0]:
            raise ValueError('Reconcile the in-flight request before preparing repair')
        times = dict(db.execute('select id,reserved_at from calls'))
    public = {r['key']: r for r in load_json(ROOT / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    plan, groups = [], []
    for arm in PILOT_ARMS:
        for batch in range(1, 5):
            old_path = ORIGINAL / arm / f'B{batch - 1}.json'
            old = Library.load(old_path)
            prior = load_json(ORIGINAL / arm / f'update_B{batch}.json')['logical_candidate_parent_executions']
            upper = 0
            for index, candidate in original_candidates(arm, batch):
                reasons = []
                table = candidate.get('table') or {}
                for cell in table.get('mixed_version_table', []):
                    for v in (cell.get('trace') or {}).get('views', []):
                        if any('read unresolved:' in f['error'] for f in v['execution'].get('failed_candidates', [])):
                            reasons.append('actual_unknown_read_rejected_before_program')
                revisions = candidate.get('revisions')
                for r in revisions or []:
                    s = Skill.from_dict(r['new'])
                    bound = {p.get('read_id') for p in s.premises.values() if p['mode'] == 'read'}
                    if any(reader['id'] not in bound for reader in s.reads):reasons.append('unbound_reader_was_executed')
                error = None
                if not revisions and candidate.get('raw_block'):
                    try:
                        revisions = compile_block(candidate['raw_block'], old, public, arm)
                        reasons.append('recorded_draft_identity_recovered')
                    except ValueError as exc:
                        error = str(exc)
                if not reasons:continue
                if not table:
                    context = load_json(ORIGINAL / arm / f'update_context_B{batch}.json')
                    initial = load_json(ORIGINAL / arm / f'initial_B{batch}.json')
                    current = {r['source']: r for r in initial['results']}
                    order = initial['binding']['source_ids']
                    trigger = sorted(current, key=lambda k: (current[k]['selection_grade'] is None,
                        current[k]['selection_grade'] if current[k]['selection_grade'] is not None else 0, order.index(k)))[:3]
                    history = [k for k in context['cohort'] if k not in trigger]
                else:trigger, history = table['trigger'], table['history']
                row = {'arm': arm, 'batch': batch, 'candidate': index, 'reasons': sorted(set(reasons)),
                    'old_library': str(old_path.relative_to(ROOT)), 'old_library_hash': old.hash,
                    'trigger': trigger, 'history': history, 'revisions': revisions, 'compile_error': error}
                if revisions:
                    new = apply_revision_package(old, revisions, old.hash)
                    retrieval = {k: {v['id']: list(dict.fromkeys(retrieve(new, public[k], v) + retrieve(old, public[k], v)))
                        for v in public[k]['views']} for k in trigger + history}
                    proof = trigger_revision_reachability(old, new, retrieval, trigger, [r['skill_id'] for r in revisions])
                    row['trigger_reachability'] = proof
                    upper += (1 << len(revisions)) * len(trigger + history) if proof['any_changed_reachable'] else 0
                plan.append(row)
            if prior + upper > 192:raise ValueError(f'Original plus repair exceeds fixed logical budget: {arm}/{batch}')
            groups.append({'arm': arm, 'batch': batch, 'original_logical_executions': prior,
                           'repair_logical_upper_bound': upper, 'combined_upper_bound': prior + upper})
    immutable_json(FOLDER / 'repair_queue.json', {'created_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'original frozen candidates and original replay cohorts; no new teacher, sources or learning epoch',
        'original_results_unchanged': True, 'groups': groups, 'queue': plan})
    old_profile = load_json(ROOT / 'configs/legal_skill_evolution_pilot_v11_20261111.json')
    profile = {**old_profile, 'run_id': 'legal_skill_evolution_repair_v13_20261111',
        'artifacts': str(FOLDER.relative_to(ROOT)), 'prior_logical_replay_executions': {},
        'exact_replay_profiles': [f'configs/legal_skill_evolution_pilot_v{i}_20261111.json'
            for i in range(1, 12) if (ROOT / f'configs/legal_skill_evolution_pilot_v{i}_20261111.json').exists()]}
    profile['exact_replay_profiles'].append('configs/legal_skill_evolution_repair_v12_20261111.json')
    old_manifest = load_json(ORIGINAL / 'execution_manifest.json')
    code = {p: sha(ROOT / p) for p in old_manifest['code']}
    code[str(Path(__file__).relative_to(ROOT))] = sha(Path(__file__))
    for p in list((ROOT / 'legal_skill_guard/skill_evolution').glob('*.py')) + [ROOT / 'tests/test_skill_evolution_coupling.py']:
        code[str(p.relative_to(ROOT))] = sha(p)
    data = {p: sha(ROOT / p) for p in old_manifest['data']}
    for p in [FOLDER / 'repair_queue.json'] + [ROOT / r['old_library'] for r in plan]:data[str(p.relative_to(ROOT))] = sha(p)
    profile['generation_binding'] = {'code_hash': digest(code), 'data_hash': digest(data),
        'executor_hash': digest(profile['executor']), 'teacher_hash': digest(profile['teacher'])}
    immutable_json(PROFILE, profile)
    immutable_json(FOLDER / 'execution_manifest.json', {'code': code, 'data': data, 'profile_sha256': sha(PROFILE)})
    for relative in code:
        target = FOLDER / 'source_snapshot' / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and sha(target) != sha(ROOT / relative):raise ValueError('Frozen repair source changed')
        shutil.copyfile(ROOT / relative, target)
    # Preserve the earliest actual direct baseline, including the documented
    # deterministic complete-native-field recovery, rather than resampling it.
    baseline = {}
    for i in range(1, 12):
        for path in (ORIGINAL.parent / f'pilot_v{i}' / 'native_direct_baselines').glob('*.json'):
            value = load_json(path)
            event = value['execution']['events'][-1]
            call = event.get('physical_call_id', event.get('call_id'))
            rank = (times.get(call, float('inf')), i)
            if path.name not in baseline or rank < baseline[path.name][0]:baseline[path.name] = (rank, path, value)
    for name, (_, path, value) in baseline.items():immutable_json(FOLDER / 'native_direct_baselines' / name, value)
    print(json.dumps({'fixed_affected_candidates': len(plan), 'teacher_requests_planned': 0,
        'logical_candidate_parent_upper_bound': sum(g['repair_logical_upper_bound'] for g in groups), 'new_model_calls': 0}), flush=True)


def run():
    profile, manifest = load_json(PROFILE), load_json(FOLDER / 'execution_manifest.json')
    if sha(PROFILE) != manifest['profile_sha256']:raise ValueError('Repair profile changed')
    for p, expected in {**manifest['code'], **manifest['data']}.items():
        if sha(ROOT / p) != expected:raise ValueError('Frozen repair dependency changed: ' + p)
    study = Study(ROOT, profile)
    study.executor.readiness()
    for row in load_json(FOLDER / 'repair_queue.json')['queue']:
        target = FOLDER / row['arm'] / f"B{row['batch']}_c{row['candidate']}.json"
        if target.exists():continue
        if row['compile_error'] or not row['trigger_reachability']['any_changed_reachable']:
            immutable_json(target, {**row, 'new_physical_calls': 0, 'logical_executions': 0,
                'selection': 'unresolved' if row['compile_error'] else 'provably_no_trigger_effect',
                'unmeasured_outcomes': 'unknown'})
            continue
        old, revisions = Library.load(ROOT / row['old_library']), row['revisions']
        new = apply_revision_package(old, revisions, old.hash)
        cohort = row['trigger'] + row['history']
        retrieval = {k: {v['id']: list(dict.fromkeys(retrieve(new, study.records[k], v) + retrieve(old, study.records[k], v)))
            for v in study.records[k]['views']} for k in cohort}
        table = VersionTable(tuple(r['new_hash'] for r in revisions), tuple(row['trigger']), tuple(row['history']))
        tokens = {}
        for mask in range(1 << len(revisions)):
            library = apply_revision_package(old, [r for i, r in enumerate(revisions) if mask & (1 << i)], old.hash)
            tokens[mask] = 0
            for key in cohort:
                result = study.parent(key, library, retrieval_sets=retrieval[key])
                table.observe(mask, key, result['selection_grade'], result)
                tokens[mask] += sum((e.get('usage') or {}).get('total_tokens', 0)
                    for v in result['views'] for e in v['execution']['events'] if e.get('kind') == 'READ_LOCAL')
        chosen = table.choose({m: tokens[m] - tokens[0] for m in tokens})
        receipt = {**row, 'table': table.export(), 'selected_mask': chosen,
            'logical_executions': (1 << len(revisions)) * len(cohort),
            'not_new_learning_epoch': True, 'original_sequential_library_history_unchanged': True}
        immutable_json(target, receipt)
        print(json.dumps({'stage': 'affected_candidate_revalidation', 'arm': row['arm'], 'batch': row['batch'],
            'candidate': row['candidate'], 'selected_mask': chosen, 'classification': table.classify()}, ensure_ascii=False), flush=True)
    immutable_json(FOLDER / 'completed.json', {'completed_utc': datetime.now(timezone.utc).isoformat(),
        'fixed_queue_complete': True, 'new_teacher_requests': 0, 'formal_training_started': False,
        'goal_complete': False})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'run'])
    args = parser.parse_args()
    prepare() if args.action == 'prepare' else run()
