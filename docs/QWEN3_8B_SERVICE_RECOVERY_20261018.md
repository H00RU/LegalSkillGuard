# Qwen3-8B service restoration

The user explicitly authorized restoration on 2026-10-18 after the original
RAM-only service died. This permits retrieving the **same Qwen3-8B**, not a new
model, paid API, task change, resumption of negative training, or a new teacher.

## Identity and storage

- Model: `Qwen/Qwen3-8B`, BF16, official HF revision
  `b968826d9c46dd6066d109eabc6255188de91218`.
- Weights: `/media/sangfor/vdb/legal-skill-runtime/models/Qwen3-8B/` followed by
  the full HF revision. All five shards must match the official HF LFS SHA256.
- The direct official Qwen ModelScope transport is pinned at
  `7c9709d23bd2136dac1d6ea1fe30f4107d681cd6`; its five hashes and sizes were
  checked against HF before use. This is byte-identical transport, not a model
  substitution. Tokenizer/config files come from the pinned HF revision.
- Complete independent environment:
  `/media/sangfor/vdb/legal-skill-runtime/inference-qwen3-8b-vllm0102`.
  Critical versions follow the retained September inference lock:
  vLLM0.10.2, torch2.8.0, transformers4.56.2, triton3.4.0, xgrammar0.1.23.
  The final transitive freeze and dependency check are saved, not presumed equal
  to the lost environment.
- Recovery progress/metadata/manifests:
  `/media/sangfor/vdb/legal-skill-runtime/qwen3-8b-restoration-20261018`.
- No original weight SHA was recovered. Do not claim bitwise identity to the
  original loaded model merely because the model name is unchanged.

## Background lifecycle

Canonical units and recovery entry are in `ops/`; user-systemd holds links.
The preparation job downloads/verifies all files and installs the environment,
then starts the inference unit. It does not start a training experiment.
Resumable download transport was changed after slow-path measurements;
operational preparation restarts are visible in the journal, not hidden.

```bash
systemctl --user status legal-qwen3-8b-restore.service
systemctl --user status legal-qwen3-8b.service
journalctl --user -u legal-qwen3-8b.service -n 80 --no-pager
curl --noproxy '*' http://127.0.0.1:8000/health
```

The user's `Linger=yes` was already enabled; it was not changed. Units survive
conversation disconnects. The inference unit uses `Restart=no`: engine failure
is not silently hidden by restart or by client fallback. Logs go to the system
journal, outside the project log path that was lost in the earlier incident.

## Research boundary and readiness

Serving remains localhost8000 with the same served name, context32768,
max-num-seqs1, KV5GiB, seed42, BF16, original reasoning/xgrammar flags and
generation-config settings. No two-model ensemble or new routing was added.
Existing stopped runs and their raw records are not resumed or rewritten.

File/env preparation and a process being live are **not** sufficient readiness:
check health, actual structured generation, and the one-token logprobs path
implicated in the incident. Synthetic operational checks are not paper scores.
If checks succeed, save the new process identity, package versions and actual
response status/usage. Do not claim full scientific Goal completion from this.

For future acceleration, independent requests under a fixed bank can be
concurrent; dependent bank updates cannot. One shared model with two sequences
avoids duplicating BF16 weights. It still requires actual client concurrency,
enough KV memory and a measured throughput/correctness comparison under a new
execution configuration. None of those changes are silently included here.
