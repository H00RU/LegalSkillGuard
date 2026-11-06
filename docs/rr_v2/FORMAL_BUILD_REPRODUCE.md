# RR-v2 fixed 128-source shared build

This stage runs the original 128 TRAIN sources in their fixed order, in eight
batches, once from an empty library. It does not run the six-arm evaluation,
frozen tests, or manuscript work. Ordinary errors and fallback remain in the
records; they do not authorize additional samples or tuning.

The [build report](../../reports/legalskillguard_rr_v2_formal_build_20261106.md)
contains the observed completion state and costs. The run directory is
`artifacts/rr_v2_formal_build_20261106/run_citation_fix/`. Inspect `process_identity.json`, the
real PID/start ticks, `state.json`, and the cumulative ledger before any recovery.
An existing live controller must be observed, never duplicated.

## Configuration and accounting

- Executor: `Qwen/Qwen3-8B`, `enable_thinking=false`, temperature 0.6, top_p 0.95,
  top_k 20, seed 45, output limit 8192, context 32768, concurrency 1, retries 0.
- Teacher: `gpt-5.6-sol`, `reasoning_effort=high`, existing verified Codex CLI,
  retries 0. Temperature is not explicitly set; the effective backend default
  is not exposed.
- The same 6000 executor / 20 teacher cumulative ledger is retained. The original Goal baseline was 127 executor / 4 teacher; the aborted citation-contract run added 65 executor / 2 teacher, all retained. The corrected run starts at 192 / 6. This formal run allows at most two executor
  requests per source and two teacher requests per batch, including failures.
- Applicable existing oracle views retain their original source/view/reference
  binding. The combined four-extra-views-per-source limit is not reset.
- Old preflight records and summaries remain historical. They are not current
  source completions. B1/B8 and every batch checkpoint use this run's records.

`seal.json` binds scientific files, prompt/schema implementations, model
configuration, original source order and manifests, teacher transport, original
ledger origin, and the append-only allocation policy. Launch implementation is
local commit `f22bdf134686972c1551966a165e8be3e679f977`; public source is a curated
content mirror, without private local Git ancestry. The bound local root README
is retained unchanged locally; public navigation is an explicitly listed variant.

## Compatible reference-adapter continuation

The original generation binding is `54b353ac46fda34ba0237f2c000634a3ecca84b0cbc5c2f0054f854efd7d2194`.
After76 saved sources, the reference adapter rejected the original source77 SARA
query containing two positive statutory predicates. The original controller exited;
all351 cumulative call rows (341 executor /10 teacher), raw responses and76 records
were preserved before repair. Nothing was reset or repeated.

The safe reference-query parser now accepts the original conjunction and rejects
arbitrary goals. Current processing binding is
`7628be5932adcaa1e29c76e5901673998b69e9c26214799c124e8d1bcce3f2a0`,
local repair commit `ed6b7bd`. Model/prompt/schema/data/sampling are unchanged.
`run_citation_fix/processing_repair.json` seals the exact processing files,
compatibility proof hashes, and original76 record hashes. New records separately
carry `processing_binding` and `processing_revision`; generation/wire binding
continues to identify the exact originally paid contract.

All76 prior analyses and B-learning results re-executed exactly on recorded views.
All24 original SARA queries/targets match the fixed reference;164 existing related
checks and8 new safety/query regressions passed in separate runs. The actual paid
source77 response was recovered through production code with byte-identical
wire/request hash and zero new calls. Required original library dictionary ordering
was restored from that exact paid wire; semantic values were unchanged. Production
recovery does not lower already committed progress. These proofs are immutable
while the controller is live; do not rerun proof writers against a changed ledger.
See [repair evidence](../../reports/rr_v2_evidence/formal_build_20261106_citation_fix/sara_reference_recovery/).

## Inspect and verify saved results

From the existing project environment:

```bash
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/audit_build.py
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/check_completion.py
```

The first command checks the committed prefix, literal requests and responses,
thinking OFF, per-source caps, original ledger rows and views, source ordering,
empty initial library, checkpoints and frozen libraries. The second recomputes
shared-arm material and the ordinary MB control from exactly the same paid TRAIN
material. Material projection is not six-arm evaluation.

Only after the controller is terminal with all 128 sources and eight batches:

```bash
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/render_report.py --final --mechanisms
PYTHONPATH=. python reports/rr_v2_evidence/formal_build_20261106_citation_fix/check_completion.py --restore
```

Mechanism checking re-executes learning using each attempt's actually recorded
oracle-view sequence, without obtaining new labels or invoking models. The
cached-recovery check calls production `FormalRun.train`, captures state writes
in memory, rejects any generation/reservation, and requires all saved run bytes,
ledger tables, and terminal completion to remain identical. It uses TRAIN packets
only. These are offline checks, not fresh model predictions.

## Recover this run

If the original controller has exited, use its exact frozen version and ledger:

```bash
python -m experiments.rr_v2_formal_build run
```

The nonblocking controller lock prevents a second active controller. Preserved
completed outputs and current-run source records are reused without dispatch;
failed or ambiguous attempts remain charged and are not silently sent again.
The controller does not automatically evaluate after training. Do not use the
old preflight/thinking/repair commands as this run's recovery queue.

`prepare` is the one-time launch check, already completed. It requires the
preserved terminal 192/6 corrected-recovery baseline and rejects the subsequently spent ledger.
Do not repeat it, replace the live ledger with its backup, or launch a new run
to reproduce an already completed stage. A fresh experiment is outside this
delivery's execution scope.

## Artifacts and external requirements

The run saves `sources/`, literal `calls/`, eight `batches/B*.json` checkpoints,
`B1.frozen.json`, `B8.frozen.json`, and corresponding `B1.MB.frozen.json` /
`B8.MB.frozen.json`. Reports include source status, request usage and failures,
mechanism coverage, hashes, and unknown monetary charges explicitly.

The public export includes TRAIN evidence and a read-only calls/oracle table
export. Private SQLite metadata, credentials, machine-operation history, model
weights/environments, bound host binaries, and DEV/TEST packets or labels are
not exported. Source/data hashes and the publication manifest describe the
boundary; cloning the repository alone does not provision the bound local model
or reference runtime. Existing raw results and baseline backups remain local.

The aborted original run remains in `artifacts/rr_v2_formal_build_20261106/run/` and its preservation directory. Its source completions and teacher summaries are not current-run completions. The current teacher budget is at most14 more calls within the original20; a second attempt cannot spend the first invocation reserved for a future batch. The full-build allocation is357 (historical36 + aborted65 + corrected at most256), recovery131, future evaluation reserve5472. No historical call row or oracle count is reset.
