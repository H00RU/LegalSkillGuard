"""Preserve two immutable Text45 milestones; never control or score learning."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tarfile
import time
import traceback

from experiments.openexempt_online import preserve
from legal_skill_guard.experiment.storage import RunStore
from legal_skill_guard.learning.experiment import now, read, sha

ROOT = Path('/media/sangfor/vdb/legal-skill-evolve')
RUN = 'legal_openexempt_trace2skill_text_public_assets128_seed45_20261023_run02'
R = ROOT / 'runs' / RUN
CFG = ROOT / 'configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run02.json'
OUT = ROOT / 'artifacts/launches/openexempt_text45_milestone_preservation_20261023'
TEXT_PID, TEXT_START = 2156118, '474271148'
MODEL_PID, MODEL_START = 3613253, '446037091'


def ticks(pid):
    p = Path('/proc') / str(pid) / 'stat'
    return p.read_text().split()[21] if p.exists() else None


def capture(stage, files):
    names = sorted({str(p.relative_to(ROOT)) for p in files})
    members = {n: sha(ROOT / n) for n in names}
    manifest = OUT / (stage + '_manifest.json')
    RunStore.immutable_json(manifest, {
        'at': now(), 'stage': stage, 'members': members,
        'no_score_or_bank_selection_no_TEST_no_training_control': True,
    })
    names.append(str(manifest.relative_to(ROOT)))
    members[names[-1]] = sha(manifest)
    saved = preserve(RUN, 'milestone_' + stage + '_20261023', names)
    archives = []
    for item in saved['paths']:
        p = Path(item['path'])
        if sha(p) != item['sha256']:
            raise RuntimeError('Archive hash mismatch: ' + str(p))
        seen = set()
        with tarfile.open(p, 'r:gz') as tar:
            for m in tar:
                if not m.isfile():
                    continue
                if m.name not in members:
                    raise RuntimeError('Unexpected archive member: ' + m.name)
                actual = hashlib.sha256(tar.extractfile(m).read()).hexdigest()
                if actual != members[m.name]:
                    raise RuntimeError('Archived member changed: ' + m.name)
                seen.add(m.name)
        if seen != set(names):
            raise RuntimeError('Incomplete milestone archive')
        archives.append({**item, 'device': p.stat().st_dev,
                         'verified_members': len(seen)})
    if len(archives) != 2 or len({p['device'] for p in archives}) != 2:
        raise RuntimeError('Two distinct backup devices are required')
    RunStore.immutable_json(OUT / (stage + '_preserved.json'), {
        'at': now(), 'stage': stage, 'archives': archives,
        'manifest_sha256': sha(manifest), 'members': members,
        'no_new_inference_teacher_grading_or_training_control': True,
    })
    print(json.dumps({'at': now(), 'preserved': stage,
                      'members_per_disk': len(names)}), flush=True)


def main():
    if OUT.exists():
        raise FileExistsError('One exact observer only; do not overwrite its evidence')
    if ticks(TEXT_PID) != TEXT_START or ticks(MODEL_PID) != MODEL_START:
        raise RuntimeError('Exact learner and original model must be live')
    OUT.mkdir()
    common = [CFG, CFG.with_suffix('.frozen.json'), Path(__file__).resolve(),
              R / 'initialization.json']
    RunStore.immutable_json(OUT / 'initialized.json', {
        'at': now(), 'observer_pid': os.getpid(), 'run': RUN,
        'exact_text_PID_start': [TEXT_PID, TEXT_START],
        'original_model_PID_start': [MODEL_PID, MODEL_START],
        'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in common},
        'milestones': ['sealed_source256', 'published_final_skill'],
        'no_restarts_no_scoring_no_model_calls_no_TEST': True,
    })
    captured = set()
    while True:
        if 'sealed_source256' not in captured and (R / 'source_records.json').is_file():
            records = read(R / 'source_records.json')
            if len(records) != 256 or {(v['case_id'], v['family']) for v in records} != {
                    (i, f) for i in range(181, 309) for f in ('EC', 'EV')}:
                raise RuntimeError('Only the complete original256 sources may seal')
            files = [*common, R / 'source_records.json',
                     *(R / 'native/source_first_forecasts').glob('*.json')]
            capture('sealed_source256', files)
            captured.add('sealed_source256')
        if 'sealed_source256' in captured and (R / 'publications/final.json').is_file():
            files = [*common, *(p for p in R.rglob('*') if p.is_file()
                     and p.name != 'progress.json' and '/cache/' not in str(p)
                     and '/native/final_TRAIN_replay/' not in str(p))]
            capture('published_final_skill', files)
            RunStore.immutable_json(OUT / 'complete.json', {
                'at': now(), 'two_milestones_preserved': True,
                'learner_may_still_be_replaying_not_completed_training': True,
                'no_learner_or_model_stop': True,
            })
            return
        if ticks(TEXT_PID) != TEXT_START or ticks(MODEL_PID) != MODEL_START:
            raise RuntimeError('Original handle ended before both milestones; inspect learner terminal evidence')
        time.sleep(45)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if OUT.is_dir() and not (OUT / 'observation_failed.json').exists():
            RunStore.immutable_json(OUT / 'observation_failed.json', {
                'at': now(), 'error': repr(exc), 'traceback': traceback.format_exc(),
                'observer_failure_not_a_training_failure_or_restart_command': True,
            })
        raise
