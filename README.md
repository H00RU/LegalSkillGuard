# LegalSkillGuard

External legal skill evolution for a fixed Qwen3-8B executor on OpenExempt. Model weights remain unchanged; a teacher revises a bounded text-skill library from released training feedback and observed execution.

## Study

The tasks are exemption classification (EC) and exemption valuation (EV). Both receive the original facts, supplied statutes, allowable jurisdictions and public asset/citation references. EV determines applicable alternatives as well as their protected amounts. The learning stream contains 128 source cases in eight batches; frozen libraries are compared on 128 source-disjoint cases.

| Frozen condition | EC native F1 (%) | EV native F1 (%) |
|---|---:|---:|
| Empty library | 64.48 | 55.88 |
| First-batch library | 83.51 | 84.25 |
| Evolved library | 95.46 | 87.90 |

The manuscript reports comparison conditions, complete-output metrics, paired uncertainty estimates, and the distinction between initial acquisition and continued evolution. These are archived study results, not a new experiment.

## Paper and implementation

- [Manuscripts, PDF and Word](paper/README.md)
- [Frozen comparison data](paper/tables/utility_frozen_results_with_skillcommit_20261104.json)
- [Source map](PROJECT_MAP.md)
- [Online learning](experiments/openexempt_online.py)
- [Task interface and scoring](legal_skill_guard/openexempt.py)
- [Task-scoped skills](legal_skill_guard/learning/task_scoped_skills.py)
- [Frozen evaluation](experiments/openexempt_frozen_eval.py)
- [Main configuration](configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json)
- [Reproduction guide](docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md)
- [Supplementary Data 1](artifacts/research/manuscript_revision_astra_20261104/Supplementary_Data_1_20261104.zip.parts/README.md)
- [Offline checks](artifacts/research/manuscript_revision_astra_20261104/SUPPLEMENT_README.md)

Exact historical verification uses the immutable source snapshots and manifests in Supplementary Data 1. Publication documentation may be newer than those snapshots. New runs require fresh Run IDs and freshly frozen configurations. Experimental model/teacher identities, prompts, unsuccessful outcomes and original scores remain research evidence.
