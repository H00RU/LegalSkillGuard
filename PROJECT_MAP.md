# Project map

Updated 5 November 2026. This branch contains the maintained project. The default main branch retains the earlier consultation snapshot and links here.

## Read in this order

1. [Stage handoff](docs/handoff_next_stage.md): completed v6 study, remaining evidence boundaries and proposed next stage.
2. [Paper index](paper/README.md): v16 manuscript and immutable evidence supplement.
3. [Reproduction guide](docs/research/PAPER_REPRODUCTION_GUIDE_20261102.md).
4. [Integrity report](docs/PROJECT_INTEGRITY_20261105.json): 629 passing tests and five pre-existing AST-lock mismatches.

## Directory roles

| Path | Role |
|---|---|
| legal_skill_guard/ | Core Python package, not another project |
| experiments/ | Main training, controls and comparator drivers; historical scripts are not a queue |
| configs/ | Actual recipes and immutable frozen manifests |
| data/ | Pinned benchmark material, packets and scoring targets, where included in the published evidence |
| runs/ | Saved predictions, teacher records, published libraries, scores and terminal states |
| paper/ | Completed v16 manuscript, figures and table sources |
| artifacts/ | Original research evidence and completed diagnostic records |
| ops/, patches/ | Service definitions, dependency pins and inference patches |
| tests/ | Behavioral and boundary checks |
| recovery/ | Archived distributions and verified publication updates |
| docs/ | Methods, protocols, handoff and verification information |

The current scientific entry is [openexempt_online.py](experiments/openexempt_online.py), using the [utility-v6 recipe](configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json). The original ten-arm TEST uses [its actual matrix](artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json), not a planning recipe.

All November 4–5 TRAIN diagnostics are archived separately from formal TEST results. Their proposals were not adopted as a replacement method. Source/data details are in the handoff and [diagnostic archive index](recovery/updates/20261105_handoff/README.md).

The proposed next stage uses at least five independent datasets, about 128 or 256 total training examples, and separate frozen tests of about 32 or 64 examples per dataset. Two mechanisms must each address a specified failure. Dataset choices and mechanisms remain unimplemented; the old EC/EV recipe is not automatically the new method.

