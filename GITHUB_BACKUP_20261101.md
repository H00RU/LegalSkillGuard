# Legal skill-evolution project backup — 1 November 2026

This branch preserves the reconstructed project and completed OpenExempt EC/EV study.
The repository's existing `main` branch is not overwritten.

## Read the current work

- Source map and active/historical entry points: [PROJECT_MAP.md](PROJECT_MAP.md).
- Current status and scientific boundaries: [docs/CURRENT_GOAL.md](docs/CURRENT_GOAL.md).
- English manuscript source: [paper/utility_skill_manuscript_working_20261030.md](paper/utility_skill_manuscript_working_20261030.md).
- English Word/PDF: [Word](artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_en.docx), [PDF](artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_en.pdf).
- Chinese auxiliary manuscript: [Word](artifacts/research/manuscript_review_20261030/utility_v6_bilingual_completed_frozen_v09_20261101/utility_v6_working_zh.docx), [source](paper/sections-zh/utility_skill_manuscript_working_20261030.md).
- Experimental table data: [paper/tables/utility_frozen_results_20261101.json](paper/tables/utility_frozen_results_20261101.json).
- Full handoff: [docs/reports/UTILITY_V6_PAPER_HANDOFF_20261101.md](docs/reports/UTILITY_V6_PAPER_HANDOFF_20261101.md).

The English manuscript is the submission master; the Chinese manuscript is separate auxiliary material.
The source tree, configuration, old manuscript versions, tests, current figures,
research reports and writing skills are retained. No scientific source is changed
to perform this upload. Existing scientific files and the original Git index are
unchanged; a new `PROJECT_MAP.md` supplies navigation without moving any files.

## Raw research data and recovery

Large generated trajectories are not silently discarded because of `.gitignore`.
They are preserved in a complete, checksummed recovery archive alongside the
browsable source backup. See [recovery/README.md](recovery/README.md) for scope,
verification, archive status and restoration instructions.

Existing local root-disk and media-disk backups remain in place. Model weights,
account credentials and reinstallable Python environments are not GitHub content.
Research worktrees stored under the local `.venv` directory are research material,
not disposable dependencies, and are included in the recovery scope.
