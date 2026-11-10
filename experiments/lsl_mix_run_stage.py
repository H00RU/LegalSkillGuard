"""Run the existing fixed stages under the verified four-request admission.

This changes HTTP scheduling only. Original scientific modules, request bytes,
ledger namespaces, checkpoints, native scoring and failed results are retained.
The controller is recorded separately from their immutable bindings.
"""
from pathlib import Path
import argparse
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha
from experiments.lsl_mix_dev_resume import resume_stream
from experiments.lsl_mix_native_initialization import append


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('kind', choices=('generate', 'local', 'dev'))
    parser.add_argument('--stage')
    parser.add_argument('--split', choices=('train', 'dev'), default='train')
    parser.add_argument('--checkpoint')
    parser.add_argument('--alias', default='Base')
    parser.add_argument('--epoch', type=int, choices=(1, 2, 3))
    args = parser.parse_args()
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    policy = {'maximum_actual_HTTP_concurrency': 4, 'original_upper_bound': 8,
        'request_payloads_changed': False, 'failed_requests_automatically_retried': False,
        'controller_sha256': sha(Path(__file__)),
        'admission_sha256': sha(ROOT / 'experiments/lsl_mix_dev_resume.py'), 'TEST': False}
    path = out / 'dispatch_policy.json'
    if path.exists() and load_json(path) != policy:
        raise ValueError('Verified transport admission changed')
    write_json(path, policy)
    append(out / 'dispatch_policy_events.jsonl', {'time': time.time(), 'kind': args.kind,
        'stage': args.stage, 'split': 'dev' if args.kind == 'dev' else args.split, 'epoch': args.epoch,
        'policy_sha256': sha(path), 'physical_requests_by_controller_itself': 0})
    import experiments.lsl_mix_candidate_generation as generation
    import experiments.lsl_mix_local_candidates as local
    import experiments.lsl_mix_dev as dev
    generation.dispatch_stream = resume_stream
    local.dispatch_many = resume_stream
    dev.dispatch_stream = resume_stream
    dev.SYSTEMS = json.loads(json.dumps(dev.SYSTEMS))
    if args.kind == 'generate':
        if not args.stage or not args.checkpoint:
            parser.error('generate requires stage and exact checkpoint')
        generation.generate(out, Path(args.checkpoint).resolve(), args.stage, args.split, args.alias)
    elif args.kind == 'local':
        if not args.stage or args.split != 'train':
            parser.error('local is restricted to the existing TRAIN proposal stage')
        local.run(out, args.stage, args.alias, args.split)
    else:
        if args.epoch is None:
            parser.error('dev requires the existing epoch')
        dev.main(args.epoch)


if __name__ == '__main__':
    main()
