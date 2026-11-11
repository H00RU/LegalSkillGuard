"""Measure existing teacher intervals and ledger charges; never dispatch."""
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from experiments.legal_skill_evolution_formal import PROFILE
from legal_skill_guard.skill_evolution.objects import digest
from legal_skill_guard.skill_evolution.teacher_transport import unpack

ROOT = Path(__file__).resolve().parents[2]
REPORT = Path(__file__).resolve().parent


def interval_summary(intervals):
    if any(end <= start for start, end in intervals):
        raise ValueError('A measured invocation must have a positive, ordered interval')
    if not intervals:return {'invocations': 0, 'peak_overlap': 0, 'total_invocation_seconds': 0,
                              'union_seconds': 0, 'wall_span_seconds': None, 'observed_overlap_factor': None}
    boundaries = sorted([(start, 1) for start, _ in intervals] + [(end, -1) for _, end in intervals])
    active, peak = 0, 0
    for _, change in boundaries:
        active += change;peak = max(peak, active)
    merged = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:merged[-1][1] = max(merged[-1][1], end)
        else:merged.append([start, end])
    total = sum(end - start for start, end in intervals)
    span = max(end for _, end in intervals) - min(start for start, _ in intervals)
    return {'invocations': len(intervals), 'peak_overlap': peak, 'total_invocation_seconds': total,
        'union_seconds': sum(end - start for start, end in merged), 'wall_span_seconds': span,
        'observed_overlap_factor': total / span}


def timestamp(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:raise ValueError('Invocation times must retain their timezone')
    return parsed.timestamp()


def main():
    profile = json.loads(PROFILE.read_text());folder = ROOT / profile['artifacts']
    profiles = [profile] + [json.loads((ROOT / p).read_text()) for p in profile.get('exact_replay_profiles', [])]
    physical_roots = {p['run_id']: ROOT / p['artifacts'] for p in profiles
                      if p['run_id'].startswith('legal_skill_evolution_formal_')}
    manifest = json.loads((ROOT / 'reports/legal_skill_evolution_plan_20261111/candidate_source_manifest.json').read_text())
    train = {r['key'] for dataset in manifest['datasets'].values() for r in dataset['train']}
    with sqlite3.connect('file:' + str(ROOT / 'artifacts/rr_v2_preflight/research_ledger.sqlite3') + '?mode=ro', uri=True) as db:
        teacher_rows = db.execute('select id,status,reserved_at,result from calls where role=? and id like ?',
                                 ('teacher', 'legal_skill_evolution_formal_%')).fetchall()
        executor_times = [r[0] for r in db.execute('select reserved_at from calls where role=? and id like ?',
                                                 ('executor', 'legal_skill_evolution_formal_%'))]
    batches = []
    for path in sorted(folder.glob('teacher_prefetch_B*_completed.json')):
        complete = json.loads(path.read_text());batch = complete['batch']
        started = json.loads((folder / f'teacher_prefetch_B{batch}_started.json').read_text())
        start, end = started['started_unix'], timestamp(complete['completed_utc'])
        calls, intervals = [], []
        for identity, status, at, raw in teacher_rows:
            if not start <= at <= end:continue
            request_path = physical_roots[identity.split(':', 1)[0]] / 'calls' / digest(identity) / 'request.json'
            request = json.loads(request_path.read_text())
            context = json.loads(request['user_prompt'])
            if context.get('encoding') == 'lossless_shared_JSON_values_v1':context = unpack(context)
            if context['batch'] != batch:continue
            arm = context['arm']
            if (request['source_ids'] != started['source_cohorts'][arm]
                    or not set(request['source_ids']) <= train or request['config'] != profile['teacher']):
                raise ValueError('An actual teacher request changed its fixed cohort or model configuration')
            body = json.loads(raw) if raw else {}
            invocation = body.get('invocation', {})
            if invocation.get('started_at') and invocation.get('finished_at'):
                intervals.append((timestamp(invocation['started_at']), timestamp(invocation['finished_at'])))
            calls.append({'physical_ledger_id': identity, 'arm': arm, 'status': status,
                'reserved_at': at, 'adapter_attempt': invocation.get('attempt'),
                'invocation_started_at': invocation.get('started_at'),
                'invocation_finished_at': invocation.get('finished_at'), 'usage': invocation.get('usage'),
                'source_ids': request['source_ids']})
        measured = interval_summary(intervals)
        arm_counts = Counter(c['arm'] for c in calls)
        if set(arm_counts) != set(started['source_cohorts']) or any(n != 1 for n in arm_counts.values()):
            raise ValueError('Completed teacher phase must retain every original physical dispatch')
        batches.append({'batch': batch, 'phase_complete': True, 'teacher_calls': calls,
            'teacher_status_counts': dict(Counter(c['status'] for c in calls)),
            'teacher_dispatches_by_arm': dict(Counter(c['arm'] for c in calls)),
            'phase_wall_seconds': end - start, 'invocation_intervals': measured,
            'executor_dispatches_during_teacher_interval': sum(start <= at <= end for at in executor_times),
            'fixed_model_and_TRAIN_cohorts_verified': True,
            'worker_limit_respected': measured['peak_overlap'] <= profile['teacher_proposal_workers'],
            'new_generation_probes': 0})
    result = {'captured_utc': datetime.now(timezone.utc).isoformat(), 'new_model_calls': 0,
        'batches': batches, 'TEST_opened': False,
        'measurement_scope': 'Observed completed CLI invocation intervals, ledger dispatches and unchanged per-arm input cohorts.',
        'interpretation': 'The overlap factor compares summed observed invocation durations with their observed wall span. It is not a separately rerun serial-control speedup or evidence for Lift/CoRev.'}
    (REPORT / 'actual_teacher_overlap.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'completed_prefetch_batches_measured': len(batches), 'new_model_calls': 0,
        'summary': [{'batch': r['batch'], 'peak_overlap': r['invocation_intervals']['peak_overlap'],
                     'teacher_dispatches': len(r['teacher_calls']), 'phase_wall_seconds': r['phase_wall_seconds']}
                    for r in batches]}))


if __name__ == '__main__':main()
