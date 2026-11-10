"""Final-checkpoint, bounded ContractNLI evidence-use diagnostic.

Use only the model's own acquired evidence and labels. Measure the conditional
likelihood of those same labels with original, removed, and deterministically
replaced evidence. No gold label is put in the prefix, no answer is repaired,
and these likelihoods never replace the primary native DEV predictions. This
tests evidence dependence, not a complete legal graph or Contract M2 oracle.
"""
from copy import deepcopy
from pathlib import Path
import argparse
import fcntl
import json
import sqlite3
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legal_skill_guard.lsl.data import load_json, write_json, sha
from legal_skill_guard.lsl.native_training import prompt
from legal_skill_guard.lsl.projection import compact
from legal_skill_guard.lsl.native_semantics import predict
from experiments.lsl_mix_native_initialization import BASE_MODEL

ARMS = ('Base', 'M1', 'HardEM', 'ExecutionFilter')
MODES = ('original', 'removed', 'replaced')


def variants(value, span_count):
    # Rotate only within equal decimal-width buckets. This preserves the
    # number of evidence IDs and avoids a label-dependent replacement policy.
    mapping = {}
    groups = {}
    for index in range(span_count):
        groups.setdefault(len(str(index)), []).append(index)
    for group in groups.values():
        mapping.update(zip(group, group[1:] + group[:1]))
    removed = deepcopy(value)
    replaced = deepcopy(value)
    for item in removed['answers']:
        if 'evidence' in item:
            item['evidence'] = {}
    for item in replaced['answers']:
        if 'evidence' in item:
            indices = sorted(mapping[int(index)] for index in item['evidence'])
            item['evidence'] = {str(index): True for index in indices}
    return {'original': value, 'removed': removed, 'replaced': replaced}


def token_row(record, value, tokenizer):
    response = compact(value)
    prefix = tokenizer.apply_chat_template(prompt(record), tokenize=True,
        add_generation_prompt=True, enable_thinking=False)
    encoded = tokenizer(response, add_special_tokens=False, return_offsets_mapping=True)
    labels = {}
    cursor = 0
    for answer in value['answers']:
        item = compact(answer)
        start = response.index(item, cursor)
        cursor = start + len(item)
        a = start + item.index(compact(answer['label']))
        b = a + len(compact(answer['label']))
        indices = [i for i, (x, y) in enumerate(encoded['offset_mapping']) if y > a and x < b]
        if not indices:
            raise ValueError('Own-label token alignment failed')
        labels[answer['id']] = indices
    ids = prefix + encoded['input_ids']
    if len(ids) > 32768:
        raise ValueError('Probe never truncates the public source or label prefix')
    return {'input_ids': ids, 'response_start': len(prefix),
        'response_ids': encoded['input_ids'], 'label_token_indices': labels}


def prepare(out, tokenizer):
    rows = [r for r in load_json(out / 'open_dataset.json')['records']
            if r['split'] == 'dev' and r['dataset'] == 'ContractNLI']
    assert len(rows) == 16
    plans = []
    for arm in ARMS:
        path = out / 'candidates' / ('epoch3-' + arm) / 'dev/results.json'
        generated = {r['source']: r['result'] for r in load_json(path)}
        for row in rows:
            public = {k: row[k] for k in ('key', 'dataset', 'public', 'runtime_public_sha256')}
            raw = generated[row['key']]
            value = raw.get('parsed')
            item = {'arm': arm, 'source': row['key'], 'source_results_sha256': sha(path),
                'gold_in_prefix': False, 'fallback_used': False}
            if raw.get('finish') != 'stop' or value is None:
                plans.append({**item, 'masked_reason': 'main_generation_failed'})
                continue
            try:
                native = predict(public, value)
                if not native['valid']:
                    raise ValueError('Invalid acquired evidence')
                versions = variants(value, len(row['public']['sentence_spans']))
                plans.append({**item, 'changed': {m: compact(v) != compact(value) for m, v in versions.items()},
                    'evidence_queries': sum('evidence' in a and bool(a['evidence']) for a in value['answers']),
                    'rows': {m: token_row(public, v, tokenizer) for m, v in versions.items()}})
            except (ValueError, KeyError, TypeError) as error:
                plans.append({**item, 'masked_reason': str(error)})
    return plans


def likelihood(model, row):
    import torch
    from torch.nn import functional as F
    ids = torch.tensor([row['input_ids'][:-1]], device='cuda')
    base = model.get_base_model()
    with torch.inference_mode(), torch.autocast('cuda', dtype=torch.bfloat16):
        hidden = base.model(input_ids=ids, attention_mask=torch.ones_like(ids), use_cache=False).last_hidden_state[0]
        selected = sorted({i for values in row['label_token_indices'].values() for i in values})
        positions = [row['response_start'] - 1 + i for i in selected]
        logits = base.lm_head(hidden[positions]).float()
        target = torch.tensor([row['response_ids'][i] for i in selected], device='cuda')
        losses = F.cross_entropy(logits, target, reduction='none').cpu().tolist()
    by_index = dict(zip(selected, losses))
    return {key: sum(by_index[i] for i in indices) / len(indices)
            for key, indices in row['label_token_indices'].items()}


def main():
    out = ROOT / 'artifacts/lsl_mixed256_20261110'
    location = out / 'contract_evidence_probe'
    location.mkdir(exist_ok=True)
    cfg = {'checkpoint_epoch': 3, 'arms': ARMS, 'DEV_contracts_per_arm': 16,
        'modes': MODES, 'teacher_forced_labels': 'own generated labels, never native gold labels',
        'replacement': 'cyclic +1 within decimal-width ID bucket; source text/query/labels unchanged',
        'purpose': 'evidence-prefix dependence, not complete graph semantics or Contract M2 proof',
        'primary_predictions_changed': False, 'generation_HTTP_requests': 0,
        'thinking': False, 'code_sha256': sha(Path(__file__)), 'TEST': False}
    config = location / 'config.json'
    # Compare canonical JSON values: tuples persist as arrays.
    cfg = json.loads(json.dumps(cfg))
    if config.exists() and load_json(config) != cfg:
        raise ValueError('Frozen bounded evidence diagnostic changed')
    write_json(config, cfg)
    if '--freeze-only' in sys.argv:
        print('Final-checkpoint evidence diagnostic frozen; model forwards=0')
        return
    if (location / 'complete.json').exists():
        print('Evidence probe already complete; preserving it')
        return
    if not (out / 'mixed_continuation/complete.json').exists():
        raise RuntimeError('Finish the fixed three-epoch matrix before this bounded diagnostic')
    with sqlite3.connect(out.parent / 'rr_v2_preflight/research_ledger.sqlite3') as db:
        if db.execute("select 1 from calls where status='reserved'").fetchone():
            raise RuntimeError('Pending physical requests must finish before GPU handoff')
    for epoch in (1, 2, 3):
        state = subprocess.run(['systemctl', '--user', 'is-active', 'legal-lsl-mix256-serving-e%d' % epoch],
                               capture_output=True, text=True).stdout.strip()
        if state == 'active':
            raise RuntimeError('Serving still owns the GPU')
    lock = (out / 'acquisition/gpu_train.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    torch.set_num_threads(4)
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, local_files_only=True)
    plans = prepare(out, tokenizer)
    write_json(location / 'plan.json', plans)
    paths = {a: Path(load_json(out / 'acquisition' / a / 'epoch3/complete.json')['checkpoint']) for a in ARMS}
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa', low_cpu_mem_usage=True).to('cuda')
    model = PeftModel.from_pretrained(base, paths['Base'], adapter_name='Base', is_trainable=False)
    for arm in ARMS[1:]:
        model.load_adapter(paths[arm], adapter_name=arm, is_trainable=False)
    results = []
    forwards = 0
    started = time.monotonic()
    for plan in plans:
        item = {k: v for k, v in plan.items() if k != 'rows'}
        if 'rows' in plan:
            model.set_adapter(plan['arm'])
            model.eval()
            scores = {'original': likelihood(model, plan['rows']['original'])}
            forwards += 1
            for mode in MODES[1:]:
                if plan['changed'][mode]:
                    scores[mode] = likelihood(model, plan['rows'][mode])
                    forwards += 1
                else:
                    scores[mode] = scores['original']
            item.update(own_label_token_mean_NLL=scores,
                delta_NLL={m: {key: scores[m][key] - value for key, value in scores['original'].items()}
                           for m in MODES[1:]})
        results.append(item)
        write_json(location / 'results.json', results)
    write_json(location / 'complete.json', {'sources': len(plans), 'local_forward_calls': forwards,
        'physical_generations': 0, 'teacher_calls': 0, 'seconds': time.monotonic() - started,
        'checkpoint_sha256': {a: sha(p / 'adapter_model.safetensors') for a, p in paths.items()},
        'config_sha256': sha(config), 'not_a_primary_accuracy_or_M2_success_claim': True})
    print(json.dumps({'diagnostic_sources': len(results), 'local_forward_calls': forwards, 'new_generations': 0}))


if __name__ == '__main__':
    main()
