# LegalSkillGuard

LegalSkillGuard is a research implementation of verifier-gated, self-evolving skills
for multi-turn Chinese legal consultation. **The Phase 0–4 framework and public-30
engineering pilot are complete.** This includes structured consultation state,
executable skill contracts, TF-GRPO group attribution, static candidate checks, paired
acceptance auditing, immutable skill versions, and rollback.

This milestone validates the complete engineering loop; it is not the paper's formal
held-out result. Phase 5 still needs the frozen full-data split, three-seed RQ1 and
ablation matrix, uncertainty estimates, and the planned Qwen3.5-9B comparison.

## Current acceptance status

- The official DLawBench deterministic smoke test passes.
- The official public release validates at commit
  `9f6325f29f07b296fac110a6e1880bdd5d9ca538`.
- The public checkout contains 30 Chinese-law and 30 U.S.-law cases, not the
  264/197 cases reported for the paper corpus.
- Public case records do not contain per-case legal-domain metadata.
- NVIDIA A40, driver 570.133.20, CUDA Driver API and a real CUDA 12.2 kernel test pass.
- The LeCoDe public code is pinned, but its dialogue files require an approved,
  institutionally signed application and cannot be downloaded autonomously.
- Phase 2 passes every acceptance gate on 20 matched acceptance cells: executable
  skills improve the predeclared primary utility over B1 by `+0.112033`.
- Phase 3 completes 50 groups of four trajectories, 200 official evaluations, 46
  informative diagnoses, and produces three traceable, statically valid candidates.
- Phase 4 completes 20 paired audits and correctly routes the selected candidate to
  `REPAIR`: mean reward improves, but the 30% harmful-pair rate exceeds the frozen 15%
  limit. The active library therefore remains `seed_v0.1.0`.

See [the Phase 0 report](reports/phase0_environment_and_data.md) for evidence and
data limitations. Stage evidence is in the
[Phase 1 report](reports/phase1_no_skill_baseline.md),
[Phase 2 report](reports/phase2_state_and_static_skills.md),
[Phase 3 report](reports/phase3_tfgrpo_skill_generation.md), and
[Phase 4 report](reports/phase4_paired_audit_and_rollback.md).

## Reproduce Phases 2–4

The recorded pilot uses Qwen3-4B revision
`1cfa9a7208912126459214e8b04321603b3df60c`, one request/evaluator worker, and seed 42.
Runtime outputs live under `runs/` and are intentionally excluded from Git; reports and
machine-readable summaries under `reports/` are versioned.

```bash
# Phase 2: B2/B3, same-cell B1 comparator, official scoring, and acceptance report.
.venv/bin/python scripts/run_phase2_static_skills.py \
  --config configs/experiments/phase2_static_skills.yaml \
  --run-id phase2_acceptance_seed42_a \
  --methods B2_static_text_skills
.venv/bin/python scripts/run_phase2_static_skills.py \
  --config configs/experiments/phase2_static_skills.yaml \
  --run-id phase2_acceptance_b3_seed42_v2 \
  --methods B3_static_executable_skills
.venv/bin/python scripts/select_phase2_acceptance.py \
  --run-id phase2_acceptance_selected_seed42_v1 \
  --b2-run phase2_acceptance_seed42_a \
  --b3-run phase2_acceptance_b3_seed42_v2
.venv/bin/python scripts/evaluate_phase1_official.py \
  --config configs/experiments/phase2_static_skills.yaml \
  --run-id phase2_acceptance_selected_seed42_v1 --workers 1
.venv/bin/python scripts/run_phase1_baseline.py \
  --config configs/experiments/phase2_no_skill_comparator.yaml \
  --run-id phase2_b1_acceptance_seed42_v2 --workers 1 \
  --methods B1_prompted_multiturn
.venv/bin/python scripts/evaluate_phase1_official.py \
  --config configs/experiments/phase2_no_skill_comparator.yaml \
  --run-id phase2_b1_acceptance_seed42_v2 --workers 1
.venv/bin/python scripts/analyze_phase2_static.py \
  --run-id phase2_acceptance_selected_seed42_v1 \
  --baseline-run phase2_b1_acceptance_seed42_v2

# Phase 3: K=4 group sampling, official scoring, advantages, teacher, and report.
.venv/bin/python scripts/collect_phase3_groups.py \
  --config configs/experiments/phase3_tfgrpo.yaml \
  --run-id phase3_groups50_seed42_a
.venv/bin/python scripts/evaluate_phase1_official.py \
  --config configs/experiments/phase3_tfgrpo.yaml \
  --run-id phase3_groups50_seed42_a --workers 1
.venv/bin/python scripts/score_phase3_groups.py --run-id phase3_groups50_seed42_a
.venv/bin/python scripts/generate_phase3_skills.py --run-id phase3_groups50_seed42_a
.venv/bin/python scripts/analyze_phase3_evolution.py \
  --run-id phase3_groups50_seed42_a

# Phase 4: pre-audit candidate selection, 20 paired rollouts, official scoring,
# acceptance decision, version/rollback checks, and report.
.venv/bin/python scripts/select_phase4_candidate.py \
  --phase3-run phase3_groups50_seed42_a
.venv/bin/python scripts/collect_phase4_audit.py \
  --config configs/experiments/phase4_paired_audit.yaml \
  --candidate runs/phase3/phase3_groups50_seed42_a/evolution/candidates/evolved.final_with_unverified_claim_guard.yaml \
  --run-id phase4_evolved_final_guard_seed42_a --pair-limit 20
.venv/bin/python scripts/evaluate_phase1_official.py \
  --config configs/experiments/phase4_paired_audit.yaml \
  --run-id phase4_evolved_final_guard_seed42_a --workers 1
.venv/bin/python scripts/score_phase4_audit.py \
  --config configs/experiments/phase4_paired_audit.yaml \
  --run-id phase4_evolved_final_guard_seed42_a
.venv/bin/python scripts/analyze_phase4_audit.py \
  --run-id phase4_evolved_final_guard_seed42_a
```

The Phase 2 selection command preserves pre-score provenance: B2 comes from the
original deterministic rollout and B3 from the post-fix rerun. Reproducing from an
empty `runs/` tree should use a new run-id and record the resulting selection rather
than overwrite these audited identifiers.

## Reproduce Phase 1

After preparing DLawBench and the pinned local model snapshot:

```bash
../.tools/bin/uv run python scripts/verify_phase1_model.py
../.tools/bin/uv run python scripts/run_phase1_baseline.py \
  --run-id phase1_pilot_deterministic_seed42_a
../.tools/bin/uv run python scripts/analyze_phase1_run.py \
  --run-id phase1_pilot_deterministic_seed42_a
../.tools/bin/uv run python scripts/evaluate_phase1_official.py \
  --run-id phase1_pilot_deterministic_seed42_a
```

The frozen configuration deliberately uses one request at a time. vLLM 0.10.2 online
serving is not batch-invariant; higher worker counts are throughput diagnostics, not the
selected reproducible protocol.

## Reproduce Phase 0

The project uses Python 3.11. From the repository root:

```bash
../.tools/bin/uv sync --group dev
../.tools/bin/uv run python scripts/run_phase0.py
../.tools/bin/uv run pytest
```

The upstream repository is expected at `third_party/DLawBench`. The runner creates
an immutable, revision-keyed copy under `data/raw/dlawbench/`, writes machine-readable
evidence to `reports/artifacts/`, and regenerates the Phase 0 report.

## Layer boundaries

- `data/raw/` is immutable after preparation.
- `legal_skill_guard/data_visibility.py` is the Phase 0 trust boundary. Lawyer and
  online-state views exclude beliefs, court records, and evaluation rubrics.
- `third_party/` contains untouched upstream code and is not part of our package.
- `runs/` contains isolated runtime outputs with source, prompt, model, data, split,
  configuration, and evaluator provenance in manifests.
- `skills/seed/` is the authored v0 library; `skills/versions/` is immutable, while
  rejected, deferred, and repair candidates cannot alter the active pointer.

## Research-use warning

This project is for benchmark research. It is not a legal-advice service and must not
be interpreted as evidence that a model is safe to practice law.
