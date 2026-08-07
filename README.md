# LegalSkillGuard

LegalSkillGuard is a research scaffold for verifier-gated, self-evolving skills in
multi-turn Chinese legal consultation. **Phase 0 is complete** and Phase 1 baseline
implementation is in progress. The repository does not yet claim that the skill
evolution loop or formal paper experiments are implemented.

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

See [the Phase 0 report](reports/phase0_environment_and_data.md) for evidence and
entry criteria for Phase 1.

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
- `runs/` contains isolated runtime outputs; configuration and source hashes will be
  recorded in manifests in later phases.
- Empty module directories mirror the approved architecture and are intentionally
  reserved for their documented implementation phases.

## Research-use warning

This project is for benchmark research. It is not a legal-advice service and must not
be interpreted as evidence that a model is safe to practice law.
