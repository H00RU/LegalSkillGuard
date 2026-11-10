"""Join the existing fixed matrix and finish only its bounded evidence tasks.

This controller never starts/restarts training or evaluation, and never marks
the Goal complete. The server must review the actual evidence afterwards.
"""
from pathlib import Path
import fcntl
import json
import os
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha


def main():
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    location = out / 'final_evidence_queue'
    location.mkdir(exist_ok=True)
    lock = (location / 'run.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    scripts = ['lsl_mix_finish_evidence.py', 'lsl_mix_credit_analysis.py', 'lsl_mix_learning_trace.py',
               'lsl_mix_contract_evidence_probe.py', 'lsl_mix_dev_review.py', 'lsl_mix_costs.py']
    cfg = {'scope': 'existing mixed256 three-epoch matrix plus its already specified bounded diagnostics',
        'TEST': False, 'extra_training_arms': 0, 'extra_generations': 0,
        'code': {s: sha(ROOT / 'experiments' / s) for s in scripts},
        'open_dataset_sha256': sha(out / 'open_dataset.json')}
    config = location / 'config.json'
    if config.exists() and load_json(config) != cfg:
        raise ValueError('Evidence queue binding changed')
    write_json(config, cfg)
    if (location / 'complete.json').exists():
        print('Bounded evidence already completed; preserving it')
        return
    def status(stage, **extra):
        write_json(location / 'status.json', {'stage': stage, 'pid': os.getpid(),
            'time': time.time(), 'goal_complete': False, **extra})
        print(json.dumps({'stage': stage, **extra}), flush=True)
    def verify():
        assert sha(out / 'open_dataset.json') == cfg['open_dataset_sha256']
        for script, expected in cfg['code'].items():
            if sha(ROOT / 'experiments' / script) != expected:
                raise ValueError('Live evidence script changed: ' + script)
    def run(script, *args):
        verify()
        status('running_bounded_evidence', script=script)
        subprocess.run([sys.executable, '-u', str(ROOT / 'experiments' / script), *map(str, args)],
                       cwd=ROOT, check=True)
    status('joining_existing_mixed_continuation')
    receipt = out / 'mixed_continuation/complete.json'
    unit = 'legal-lsl-mix256-continuation.service'
    while not receipt.exists():
        state = subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True).stdout.strip()
        if state != 'active':
            raise RuntimeError('Existing matrix is terminal without completion; preserve and diagnose: ' + state)
        time.sleep(15)
    while subprocess.run(['systemctl', '--user', 'is-active', unit], capture_output=True, text=True).stdout.strip() == 'active':
        time.sleep(1)
    banks = ['common-canonical', 'epoch1-provider', 'epoch2-provider']
    for bank in banks:
        run('lsl_mix_credit_analysis.py', '--bank', out / 'candidates' / bank / 'train')
    run('lsl_mix_learning_trace.py')
    run('lsl_mix_dev_review.py')
    run('lsl_mix_contract_evidence_probe.py')
    run('lsl_mix_costs.py')
    verify()
    write_json(location / 'complete.json', {'config_sha256': sha(config), 'existing_matrix_sha256': sha(receipt),
        'credit_banks': banks, 'DEV_epochs': [1, 2, 3], 'TEST_opened': False,
        'paper_started': False, 'goal_complete': False, 'server_review_required': True})
    status('fixed_evidence_complete_server_review_required')


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        location = ROOT / 'artifacts/lsl_mixed256_20261110/final_evidence_queue'
        location.mkdir(exist_ok=True)
        write_json(location / 'failure.json', {'error': type(error).__name__ + ': ' + str(error),
            'traceback': traceback.format_exc(), 'time': time.time(), 'goal_complete': False})
        raise
