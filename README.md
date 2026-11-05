# LegalSkillGuard

External skill learning for a fixed language-model executor. This repository preserves the completed OpenExempt utility-v6 study and its reproducible evidence. A new mixed-dataset rule-constrained reasoning stage is planned, not yet implemented.

## Start here

- [Project map](PROJECT_MAP.md): source, data, results and archive roles.
- [Stage handoff](docs/handoff_next_stage.md): actual implementation, results, reusable modules and next-stage scope.
- [Manuscript index](paper/README.md): English v16 and separate Chinese manuscript.
- [Integrity report](docs/PROJECT_INTEGRITY_20261105.json): post-cleanup verification and known test-version mismatches.
- [Latest publication update](GITHUB_LATEST.md): the scope of this repository update.

## Completed OpenExempt study

A frozen Qwen3-8B answers exemption classification (EC) and exemption valuation (EV) tasks. A teacher updates a bounded text-skill library; model weights are not trained. The custom profile has 2–4 public asset mentions, supplied statutes and allowable jurisdictions. It is not the official Advanced suite.

| Frozen library | EC native F1 (%) | EV native F1 (%) |
|---|---:|---:|
| Empty | 64.48 | 55.88 |
| First-batch library B1 | 83.51 | 84.25 |
| Evolved library B8 | 95.46 | 87.90 |

The full [eleven-condition table](paper/tables/utility_frozen_results_with_skillcommit_20261104.json) includes all controls and adapted baselines. The paper distinguishes initial skill acquisition from continued evolution and reports paired intervals. These are archived results, not new predictions.

## Reproduce and inspect

- [Training implementation](experiments/openexempt_online.py)
- [Main configuration](configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json)
- [Task and scorer](legal_skill_guard/openexempt.py)
- [Frozen evaluation](experiments/openexempt_frozen_eval.py)
- [Reproduction guide](docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md)
- [Supplementary Data 1](artifacts/research/manuscript_revision_astra_20261104/Supplementary_Data_1_20261104.zip.parts/README.md)
- [Newly archived TRAIN diagnostics](recovery/updates/20261105_handoff/README.md)

Exact historical source verification uses the immutable snapshots and manifests in Supplementary Data 1. This public navigation is newer than those snapshots. New predictions require a separate Run ID, actual runtime capture and fresh bindings; do not restart completed runs.

Scientific model identities, prompts, raw answers, unsuccessful outcomes and original scores remain evidence. Private authoring instructions, conversation logs, credentials, model weights and local environments are not repository source.

