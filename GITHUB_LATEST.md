# Latest project and paper — 4 November 2026

## Read the paper

The current submission-language manuscript is English. Chinese is a separate explanatory manuscript.

| Document | Current file |
|---|---|
| English PDF v16 | [utility_v6_working_en.pdf](artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/utility_v6_working_en.pdf) |
| English Word v16 | [utility_v6_working_en.docx](artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/utility_v6_working_en.docx) |
| Chinese PDF v16 | [utility_v6_working_zh.pdf](artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/utility_v6_working_zh.pdf) |
| Chinese Word v16 | [utility_v6_working_zh.docx](artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/utility_v6_working_zh.docx) |
| English editable source | [Markdown](paper/utility_skill_manuscript_working_20261030.md) |
| Chinese editable source | [Markdown](paper/sections-zh/utility_skill_manuscript_working_20261030.md) |
| Full paper and experiment index | [paper/README.md](paper/README.md) |

The v16 revision centers on continued classification learning beyond the initial B1 library. Original scores and intervals are unchanged; executable algorithm/scoring definitions, real skill revisions and policy readouts are added. See the [revision note](docs/reports/PAPER_ASTRA_REVISION_20261104.md), [complete supplementary-data download](artifacts/research/manuscript_revision_astra_20261104/Supplementary_Data_1_20261104.zip.parts/README.md) and [offline supplement guide](artifacts/research/manuscript_revision_astra_20261104/SUPPLEMENT_README.md). The original v15 files remain preserved. The user separately authorized this v16 GitHub synchronization; its [upload record](docs/reports/GITHUB_V16_UPLOAD_20261104.md) is distinct from the earlier v15 receipts below. No scientific result, repository visibility or original main-branch history is changed.

## Source and experimental evidence

- [Project source map](PROJECT_MAP.md)
- [Eleven-condition results](paper/tables/utility_frozen_results_with_skillcommit_20261104.json)
- [Actual source-disjoint evaluation and reproduction guide](docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md)
- [Current SkillCommit implementation](experiments/openexempt_skillcommit.py)
- [Complete SkillCommit run](runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/completion.json)

## Backup layout

The existing `backup/legal-skill-evolve-20261101` branch is updated incrementally. The original `main` branch, earlier commits and November 1 recovery volumes are retained. The [November 4 recovery supplement](recovery/updates/20261104/README.md) records the new or changed project files relative to the original full backup, including raw run records that are not all displayed individually in the browsable source tree.

The update was independently fetched from GitHub and all 303 updated paths, including the three recovery volumes, matched their SHA256 digests. See the [upload report](docs/reports/GITHUB_UPDATE_20261104.md) and [verification receipt](recovery/updates/20261104/UPLOAD_VERIFIED.json) for the verified data commit. These receipt/navigation additions follow the data snapshot and change no scientific content. This backup update changes navigation, not experimental scores, model weights, task design, manuscript results or repository visibility.
