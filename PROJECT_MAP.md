# Source map

The current study evaluates OpenExempt classification (EC) and valuation (EV) with a fixed Qwen3-8B and a learned text-skill library.

| Component | Entry point |
|---|---|
| Online learning and publication | [openexempt_online.py](experiments/openexempt_online.py) |
| Task preparation and scoring | [openexempt.py](legal_skill_guard/openexempt.py) |
| Task projection and composition | [task_scoped_skills.py](legal_skill_guard/learning/task_scoped_skills.py) |
| Differential edits | [publication.py](legal_skill_guard/learning/publication.py) |
| Public asset/citation references | [legal_namespace.py](legal_skill_guard/learning/legal_namespace.py) |
| Model and teacher transports | [inference](legal_skill_guard/inference/), [experiment.py](legal_skill_guard/learning/experiment.py) |
| Phase scheduling | [phase_dispatch.py](legal_skill_guard/learning/phase_dispatch.py) |
| Frozen comparison | [openexempt_frozen_eval.py](experiments/openexempt_frozen_eval.py) |
| ACE adaptation | [openexempt_ace_online.py](experiments/openexempt_ace_online.py) |
| Text-experience adaptation | [openexempt_trace2skill.py](experiments/openexempt_trace2skill.py) |
| SkillCommit adaptation | [openexempt_skillcommit.py](experiments/openexempt_skillcommit.py) |

## Configuration

- [Main recipe](configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json)
- [Strict-policy control](configs/openexempt_v6_strict_policy_control_public_assets128_20261030_run01.json)
- [Teacher-evidence control](configs/openexempt_v6_teacher_execution_withheld_public_assets128_20261030_run01.json)
- [Frozen matrix](artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json)
- [Dependencies](pyproject.toml), [lock file](uv.lock), [inference setup](ops/inference-requirements.txt)

## Evidence

[paper/README.md](paper/README.md) links the manuscripts, tables and figures. Learned libraries and recorded study outcomes are under runs/. Complete current-study predictions, source snapshots and offline checks are in [Supplementary Data 1](artifacts/research/manuscript_revision_astra_20261104/Supplementary_Data_1_20261104.zip.parts/README.md).

Earlier consultation and ContractNLI configurations are historical studies, not the current paper task. A .frozen.json file is an experiment binding, not a disposable cache. Exact historical verification uses its archived source snapshot rather than newer navigation documents.
