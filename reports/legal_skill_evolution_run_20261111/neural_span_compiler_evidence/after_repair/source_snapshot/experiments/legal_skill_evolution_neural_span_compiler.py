"""Fixed actual-source viability test, before independent new acquisition.

Same previously acquired asset in both paths; no independent acquisition credit.
The diagnostic isolates literal coverage versus neural scoped source binding.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from legal_skill_guard.rr.checkpoint import immutable_json
from legal_skill_guard.rr.client import WireError
from legal_skill_guard.skill_evolution.clients import FrozenExecutor
from legal_skill_guard.skill_evolution.ledger import EvolutionLedger
from legal_skill_guard.skill_evolution.native import grade_view
from legal_skill_guard.skill_evolution.neural_span_compiler import (
    frames_from_rules, read_records, joint_control)
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.runtime import FrozenReads
from legal_skill_guard.skill_evolution.source_schema import TASKS
from legal_skill_guard.skill_evolution.span_compiler import execute, locate
from experiments.legal_skill_evolution_role_TRAIN import physical_snapshot
from experiments.legal_skill_evolution_span_compiler import warm_base

RUN = 'legal_skill_evolution_neural_span_compiler_v2_20261113'
ARMS = ('LocalBindings', 'SameInformationJoint')


def read(path):return json.loads(path.read_text())


def prepare(root):
    folder = root / 'artifacts' / RUN;folder.mkdir(exist_ok=True)
    if (folder / 'protocol.json').exists():return folder, read(folder / 'protocol.json')
    old = read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json')
    asset_path = root / 'reports/legal_skill_evolution_run_20261111/span_compiler_evidence/shared_compiler_baseline_v1.json'
    asset = read(asset_path)
    # Chosen by already documented failure kinds, before any new generations:
    # one missed explicit recipient, one unrelated-action contamination, and
    # both existing literal-grammar diagnostics. Not a new blind cohort.
    keys = [old['teacher_sources'][1], old['teacher_sources'][5], *old['frozen_TRAIN_probes']]
    paths = [Path(__file__).resolve(), root / 'legal_skill_guard/skill_evolution/neural_span_compiler.py',
        root / 'tests/test_skill_evolution_neural_span_compiler.py',
        root / 'tests/test_skill_evolution_source_schema.py',
        root / 'experiments/legal_skill_evolution_binding_decoder_check.py']
    paths += list((root / 'legal_skill_guard/skill_evolution').glob('*.py'))
    snapshots = {}
    for p in sorted(set(paths)):
        rel = p.relative_to(root);target = folder / 'source_snapshot' / rel
        target.parent.mkdir(parents=True, exist_ok=True);target.write_bytes(p.read_bytes())
        snapshots[str(rel)] = hashlib.sha256(p.read_bytes()).hexdigest()
    profile = read(root / 'configs/legal_skill_evolution_formal_v5_20261111.json')
    before = physical_snapshot(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3')
    if any(v.get('reserved', 0) for v in before.values()):raise ValueError('Reconcile pending calls')
    protocol = {'created_utc': datetime.now(timezone.utc).isoformat(), 'same_goal': True, 'goal_complete': False,
        'run_id': RUN, 'arms': list(ARMS), 'sources': keys,
        'teacher_sources_of_shared_asset': old['teacher_sources'],
        'question': 'Does semantic current-clause binding recover genuine core paths missed by literal source constructors, without the observed cross-clause role contamination?',
        'comparison': 'Shared actual prior FreeStrongControl acquisition. Not independent acquisition or a claimed contribution. Same current full source, acquired examples, lexicons and legal procedure available to the joint control.',
        'workload': 'One current-source binding or joint execution per arm per each of four fixed original TRAIN parents. No teacher, unchanged retries, seed scan or full matrix.',
        'sources_are_existing_TRAIN_diagnostics_not_blind': True,
        'change_from_last_run': 'Neural current-clause recognition replaces mandatory literal constructor-head equality. Fields bind actual nonoverlapping source slots inside the selected clause; source-dependent lexical recognition remains local.',
        'repair_from_first_request': 'Original call settled normally but copied old examples and all ten bindings were rejected. The installed bounded-string decoder also rejects the real escaped-quote example; remove string-length keywords only from decoding, retaining original prompt and host checks. Explicitly separate old demonstrations and place current source last. No original binding is rewritten or granted core credit.',
        'decoder_offline_evidence': 'artifacts/legal_skill_evolution_neural_span_compiler_20261112/exact_decoder_repair_evidence.json',
        'semantic_review': 'Native grades are observed after execution. Exact quote/type checks do not establish relation meaning; manually inspect each used record against the actual source. Never repair bindings with labels.',
        'decision': 'If this front end has no viable correct new-source core path, do not acquire another matching library or expand its workload. If viable, independent acquisition and meaningful update comparison remain required.',
        'executor_profile': profile['executor'], 'new_teacher_calls': 0,
        'asset_sha256': hashlib.sha256(asset_path.read_bytes()).hexdigest(),
        'source_snapshot': snapshots, 'ledger_before': before}
    immutable_json(folder / 'shared_asset.json', {'spec': asset['spec'], 'frames': frames_from_rules(asset['spec'], asset['rules'])})
    immutable_json(folder / 'protocol.json', protocol)
    with sqlite3.connect(root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') as db:
        immutable_json(folder / 'ledger_rows_before.json', db.execute('select * from calls order by id').fetchall())
    return folder, protocol


def run(root):
    folder, protocol = prepare(root)
    if (folder / 'completed.json').exists():return read(folder / 'completed.json')
    ledger_path = root / 'artifacts/rr_v2_preflight/research_ledger.sqlite3'
    ledger = EvolutionLedger(ledger_path, run_id=RUN, sources={'train': protocol['sources'], 'dev': [], 'test': []}, binding=digest(protocol))
    executor = FrozenExecutor(ledger, folder, protocol['executor_profile']);executor.readiness()
    reads = FrozenReads(executor)
    asset = read(folder / 'shared_asset.json');spec, frames = asset['spec'], asset['frames']
    public = {s['key']: s for s in read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/public.json')}
    grading = read(root / 'artifacts/legal_skill_evolution_20261111/prepared/train/grading.json')
    old = read(root / 'artifacts/legal_skill_evolution_span_compiler_20261112/protocol.json');base = warm_base(root, old)
    results = {}
    # Source-first paired execution; all physical requests remain serial.
    for key in protocol['sources']:
        source = public[key]
        for arm in ARMS:
            saved = folder / arm / (key.replace(':', '_') + '.json')
            if saved.exists():results.setdefault(arm, []).append(read(saved));continue
            event = None;records = [];error = None;outputs = {}
            try:
                if arm == 'LocalBindings':
                    records, event = read_records(reads, source, spec, frames)
                    for v in source['views']:
                        if v['id'] in TASKS:
                            outputs[v['id']] = execute(spec['procedure'], {'task_id': v['id'], 'question': v['public']['question']}, {'records': records})
                else:
                    raw, event = joint_control(reads, source, spec, frames, TASKS)
                    for task, value in raw.items():
                        valid_quotes, rejected_quotes = [], []
                        for quote in value['source_quotes']:
                            try:locate(source['views'][0]['public']['source_text'], quote);valid_quotes.append(quote)
                            except ValueError as e:rejected_quotes.append({'quote': quote, 'error': str(e)})
                        outputs[task] = {'handled': value['answer'] is not None and bool(valid_quotes),
                            'answer': value['answer'], 'used_records': [],
                            'valid_source_quotes': valid_quotes, 'rejected_source_quotes': rejected_quotes}
            except WireError:raise
            except (ValueError, TypeError, KeyError) as e:error = type(e).__name__ + ': ' + str(e)
            oldviews = {v['view']: v for v in base[key]['views']};rows = []
            for view in source['views']:
                value = outputs.get(view['id']);core = value is not None and value['handled'] and error is None
                answer = value['answer'] if core else oldviews[view['id']]['execution']['answer']
                score = grade_view(source['dataset'], view, grading[key][view['id']], answer) if core else oldviews[view['id']]['score']
                rows.append({'view': view['id'], 'answer': answer, 'score': score,
                    'core_executed': core, 'fallback': not core, 'execution': value,
                    'error': error, 'fallback_basis': None if core else 'Preserved actual common warm-library/NoSkill result; no new-core credit'})
            result = {'source': key, 'arm': arm, 'views': rows, 'records': records, 'source_event': event,
                'native_grade': sum(v['score']['grade'] for v in rows) / len(rows),
                'core_views': sum(v['core_executed'] for v in rows),
                'core_correct': sum(v['core_executed'] and v['score']['correct'] for v in rows),
                'fallback_views': sum(v['fallback'] for v in rows), 'source_semantic_review_pending': True}
            immutable_json(saved, result);results.setdefault(arm, []).append(result)
            print(json.dumps({'source': key, 'arm': arm, 'records': len(records), 'core': result['core_views'], 'correct': result['core_correct'], 'grade': result['native_grade']}), flush=True)
        local = results['LocalBindings'][-1]
        raw = (local.get('source_event') or {}).get('bindings', {}).get('records', [])
        if len(raw) >= 2 and not local['records']:
            partial = {'protocol_hash': digest(protocol), 'results': results,
                'reason': 'All repeated local bindings failed source/frame checks. Preserve paired control and diagnose before further physical requests.',
                'ledger_after': physical_snapshot(ledger_path), 'goal_complete': False}
            immutable_json(folder / 'source_binding_failure_boundary.json', partial)
            return partial
    completed = {'protocol_hash': digest(protocol), 'results': results,
        'ledger_before': protocol['ledger_before'], 'ledger_after': physical_snapshot(ledger_path),
        'independent_new_acquisition': False, 'source_semantic_review_pending': True,
        'contribution_established': False, 'goal_complete': False}
    immutable_json(folder / 'completed.json', completed)
    return completed


if __name__ == '__main__':
    p = argparse.ArgumentParser();p.add_argument('stage', choices=['prepare', 'run']);args = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.stage == 'prepare':print(prepare(root)[0])
    else:run(root)
