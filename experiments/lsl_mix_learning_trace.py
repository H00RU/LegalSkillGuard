"""Export actual per-optimizer-step learning traces without new model calls.

Training losses use the eight sources actually consumed at that step. They are
not held-out accuracy, and changes in batch composition can change these means.
Native and core acquisition gradients are kept separate throughout.
"""
from pathlib import Path
import csv
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    datasets = sorted({r['dataset'] for r in load_json(out / 'open_dataset.json')['records']})
    curves = []
    bindings = {}
    for arm in ('Base', 'M1', 'HardEM', 'ExecutionFilter'):
        cumulative = {d: {'sources': 0, 'native_gradient_sources': 0, 'core_gradient_sources': 0} for d in datasets}
        for epoch in (1, 2, 3):
            folder = out / 'acquisition' / arm / ('epoch%d' % epoch)
            if not (folder / 'complete.json').exists():
                continue
            sources = jsonl(folder / 'source_updates.jsonl')
            steps = jsonl(folder / 'optimizer_steps.jsonl')
            assert len(sources) == 256 and len({r['source'] for r in sources}) == 256
            assert len(steps) == 32 and [r['position'] for r in sources] == list(range(256))
            bindings[str(folder.relative_to(ROOT))] = {
                n: sha(folder / n) for n in ('config.json', 'source_updates.jsonl', 'optimizer_steps.jsonl', 'complete.json')}
            for index, optimizer in enumerate(steps):
                batch = sources[index * 8:(index + 1) * 8]
                by_dataset = {}
                for d in datasets:
                    selected = [r for r in batch if r['dataset'] == d]
                    seen = cumulative[d]
                    seen['sources'] += len(selected)
                    seen['native_gradient_sources'] += sum(r['native_source_probe_delta_l2'] > 0 for r in selected)
                    seen['core_gradient_sources'] += sum(r['core_probe_gradient_l2'] > 0 for r in selected)
                    by_dataset[d] = {**seen, 'batch_sources': len(selected),
                        'batch_native_loss': sum(r['native_loss'] for r in selected) / len(selected) if selected else None,
                        'batch_core_loss': sum(r['core_acquisition_loss'] for r in selected) / len(selected) if selected else None}
                curves.append({'arm': arm, 'epoch': epoch, 'optimizer_step': optimizer['step'],
                    'sources_this_epoch': (index + 1) * 8, 'batch_sources': 8,
                    'native_loss_mean': sum(r['native_loss'] for r in batch) / 8,
                    'core_loss_mean': sum(r['core_acquisition_loss'] for r in batch) / 8,
                    'core_gradient_sources': sum(r['core_probe_gradient_l2'] > 0 for r in batch),
                    'learning_rate': optimizer['lr'], 'gradient_norm': optimizer['gradient_norm'],
                    'by_dataset': by_dataset})
    composition = []
    for mode in ('ordinary', 'directed', 'contrast'):
        for epoch in (1, 2, 3):
            folder = out / 'composition' / mode / ('epoch%d' % epoch)
            if not (folder / 'complete.json').exists():
                continue
            sources = jsonl(folder / 'source_updates.jsonl')
            steps = jsonl(folder / 'optimizer_steps.jsonl')
            assert len(sources) == 256 and len(steps) == 32
            bindings[str(folder.relative_to(ROOT))] = {n: sha(folder / n)
                for n in ('config.json', 'source_updates.jsonl', 'optimizer_steps.jsonl', 'complete.json')}
            for index, step in enumerate(steps):
                batch = sources[index * 8:(index + 1) * 8]
                composition.append({'mode': mode, 'epoch': epoch, 'optimizer_step': (epoch - 1) * 32 + index + 1,
                    'batch_sources': 8, 'loss_mean': sum(r['loss'] for r in batch) / 8,
                    'squares': sum(r['squares'] for r in batch),
                    'nonzero_interaction': sum(r['nonzero_interaction'] for r in batch),
                    'joint_head_gradient_sources': sum(r['joint_head_source_gradient_l2'] > 0 for r in batch)})
    result = {'physical_model_requests': 0, 'teacher_calls': 0, 'log_sha256': bindings,
        'losses_are_online_TRAIN_not_validation': True, 'source_order_and_configuration_changed': False,
        'ordinary_native_gradient_is_not_core_skill_success': True,
        'acquisition': curves, 'composition': composition,
        'DEV': {str(e): load_json(out / 'dev' / ('epoch%d' % e) / 'summary.json')
                for e in (1, 2, 3) if (out / 'dev' / ('epoch%d' % e) / 'complete.json').exists()}}
    write_json(out / 'learning_trace.json', result)
    keys = ['arm', 'epoch', 'optimizer_step', 'sources_this_epoch', 'batch_sources',
            'native_loss_mean', 'core_loss_mean', 'core_gradient_sources', 'learning_rate', 'gradient_norm']
    with (out / 'learning_trace.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        writer.writerows({k: row[k] for k in keys} for row in curves)
    print(json.dumps({'acquisition_steps': len(curves), 'composition_steps': len(composition),
                      'DEV_epochs_complete': list(result['DEV']), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
