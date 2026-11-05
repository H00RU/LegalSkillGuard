# Stage handoff: completed utility-v6 study and next research stage

Updated 5 November 2026. This is the portable public handoff. Machine-local operation records and authoring instructions are retained outside the public repository. They are not scientific inputs or a replacement for the records below.

## 1. Scientific version and execution state

The completed study is OpenExempt exemption classification (EC) and exemption valuation (EV), with fixed Qwen3-8B weights and an evolving text-skill library. The current paper is utility_v6_working_en.pdf, v16; Chinese is a separate manuscript. No new complete training or TEST predictions were generated during the handoff and filesystem cleanup.

- [English editable source](../paper/utility_skill_manuscript_working_20261030.md)
- [English PDF v16](../artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/utility_v6_working_en.pdf)
- [Chinese editable source](../paper/sections-zh/utility_skill_manuscript_working_20261030.md)
- [Render manifest](../artifacts/research/manuscript_review_20261030/utility_v6_astra_revision_v16_delivery_20261104/render_manifest.json)

The English PDF SHA256 is dd55f19448eeaa6baf0efce11af4df4b947dda995dbc55faa9d892cbd1d58f13.
The source workspace was on reconstructed-main at 1c184e05f3d5e68b57f321eb75a7000746c0c6eb with additional uncommitted work; that commit alone is not the complete paper version. Run-specific frozen manifests and immutable supplemental sources identify the actual experiment.

No training client was active at handoff; the existing inference service remained running. Historical PIDs, progress files, protocols and waiting scripts are not current launch instructions.

## 2. Actual code, recipes and learned banks

| Component | Actual entry |
|---|---|
| Main 128-source, eight-batch training | experiments/openexempt_online.py |
| Main recipe | configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json and its frozen manifest |
| Actual original TEST matrix | artifacts/launches/openexempt_v6_final_after_withheld_20261031_run01/actual_final_matrix_config.json |
| Frozen evaluator | experiments/openexempt_frozen_eval.py |
| Task and original scoring adapter | legal_skill_guard/openexempt.py |
| Skill projections and edits | legal_skill_guard/learning/task_scoped_skills.py and publication.py |
| Public asset/citation encodings | legal_skill_guard/learning/legal_namespace.py |
| Executor and teacher transport | legal_skill_guard/inference/native.py and codex_cli_client.py |
| Strict-policy control | configs/openexempt_v6_strict_policy_control_public_assets128_20261030_run01.json |
| Teacher-execution-evidence control | configs/openexempt_v6_teacher_execution_withheld_public_assets128_20261030_run01.json |
| SkillCommit adaptation | experiments/openexempt_skillcommit.py and configs/openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05.json |

The main run root is runs/legal_openexempt_complete_output_utility_public_assets128_20261030_run01/.
Read publications/b1.json and publications/b8.json for complete actual libraries, teacher/ and candidates/ for proposals, native/ for requests/responses, and batches/ for first-encounter records.

B1 bank hash: b4bcf4f2b0ac2027bd0a6764ea0e5275d64b3b451deff31a3dfbb06e4ee18896.
B8 bank hash: 48746352543b1a75627eb3cc9480a2257f42107fde544080aefbadc9cd2fca5d.

The source-workspace audit checked 379 main, 549 evaluation and 648 SkillCommit bindings, 816 distinct files, without differences. Updated public navigation is not the immutable historical source snapshot; use Supplementary Data 1 for exact historical binding verification.

## 3. Learning, data and scoring

The main learner starts empty, processes eight batches of 16 sources, saves forecasts before releasing current training labels, and proposes one EC and one EV update per batch. The teacher was the recorded gpt-5.6-sol/high CLI adapter. Sixteen successful teacher responses produced nine accepted task-coordinate updates. Model weights were not updated; this is not the earlier multi-turn consultation or four-trajectory TFGRPO pipeline.

The library cap is 4096 tokens. Task/jurisdiction projections provide relevant text. EC and EV are independently answered in the formal method. Candidates and actual compositions are replayed on seen training sources under the recorded complete-output utility policy. Rejected proposals remain available. This training selection is not a separate validation set.

Pinned OpenExempt revision: ec6fa2547431096588ce2d3ef107b8adc33cd4fe, CC BY 4.0.

- TRAIN: data/packets/openexempt_closed_feedback_public_assets128_20261021/inputs.json; labels in grading_only/.
- TEST: data/packets/openexempt_IID128_confirmatory_TEST_20261030/inputs.json; labels in grading_only/.
- Each split has 128 underlying sources and 256 EC/EV views; source_key overlap is zero.
- This custom 2–4-asset profile supplies statutes and allowable jurisdictions. It is not official Advanced.
- Targets originate from the pinned generator/solver. Construction-only fields and the solver are not actor tools.
- Native scoring is preserved through legal_skill_guard/openexempt.py and the pinned evaluator. EV matches citation and requires amount relative error strictly below 5%.
- Native F1 and complete-output F1 differ; neither is case-level accuracy. Invalid and unfavorable outputs remain in the records.

TEST results have been observed. Subsequent TRAIN diagnoses and the later same-TEST SkillCommit supplement are not new untouched confirmations.

## 4. Frozen results and interpretation

All scores below are native F1 percentages.

| Condition | EC | EV |
|---|---:|---:|
| Empty | 64.48 | 55.88 |
| Static law skills | 60.40 | 55.34 |
| ACE original interface | 65.00 | 58.68 |
| ACE common interface | 66.59 | 66.92 |
| Text experience | 55.08 | 53.31 |
| Own B1 frozen | 83.51 | 84.25 |
| Main B8 | 95.46 | 87.90 |
| Strict policy | 80.29 | 89.01 |
| Teacher execution evidence withheld | 86.98 | 80.38 |
| Historical projection library | 87.63 | 83.91 |
| SkillCommit | 67.98 | 64.82 |

The [machine-readable table](../paper/tables/utility_frozen_results_with_skillcommit_20261104.json) is authoritative.
The original ten-condition records are in runs/legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01/scored_records.json. The additional 256 SkillCommit records are in runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/TEST_scored_records.json, giving 2816 total.

Main B8 minus B1 is +11.95 pp EC, adjusted interval [7.33,16.60], and +3.65 pp EV, interval [-2.82,10.28]. Main EV minus strict-policy EV is -1.11 pp, interval [-6.20,3.65]. Continued classification learning is supported; significant continued EV improvement or uniform superiority over controls is not established. Each condition has one actual learned build; independent learning repetitions were deferred.

B1/B8 have seven records each, 13/14 task blocks and 2461/3993 tokens. Later learning mainly revises existing content. The main build used 1207 physical executor generations and 16 successful teacher responses; request aliases are not independent new generations.

## 5. Completed diagnoses, not adopted methods

Original scripts, protocols, calls and derived analyses are preserved under artifacts/research/openexempt_ev_learning_20261104/ and artifacts/research/openexempt_ev_learning_20261105/. See the [diagnostic index](../recovery/updates/20261105_handoff/README.md).

- Original B3–B6 EV proposals failed their gates: correcting amounts could increase omissions or disrupt previously correct jurisdictions. Additional format failures did not explain these declines.
- Local binding edits and compact execution examples gave small aggregate gains but harmed current sources.
- Atomic rule units improved aggregate TRAIN32 scores but failed current-source retention; transferring them unchanged to B8 exceeded the existing 4096-token cap.
- Supplying the actor's EC prediction to EV reduced omissions, but increased amount errors. Native-ID presentation improved averages while still failing current retention.
- Per-asset execution passed an eight-source screen but failed the actual B1/B8 TRAIN32 retention criterion. B8 native/complete F1 rose from 85.51/84.85 to 92.58/91.48 overall, while current 16-source native F1 fell from 96.03 to 92.42. It did not establish a larger evolution benefit and required more calls.
- The latter confirmation retained a budget-stopped first phase and one bounded resource continuation: 169 new EV generations, 17 exact old-response reuses and zero teachers. Its result is not a formal TEST score.
- SkillCommit retrieval diagnostics found concentrated retrieval, not a proved cache or tail-truncation bug. Its original score was not changed.

These results do not show that any diagnostic mechanism solved the EV bottleneck. They are not substituted into the paper's main-method column.

## 6. Integrity and recovery

The post-cleanup audit independently reproduced all 2816 saved scores and eleven aggregates and traced all 2816 raw HTTP responses and pre-grading predictions. No differences were found. The full offline suite reported 629 passing tests and five pre-existing AST-lock failures. The same five failed in the pre-move snapshot, with identical relevant source/test hashes. No test constants or scientific code were changed to hide them.

Details: [integrity report](PROJECT_INTEGRITY_20261105.json).
The repository's core source, configuration, test and deployment files were already identical to the pre-update research branch; this update primarily adds evidence and cleaned documentation.

For exact source restoration and offline checks, use [Supplementary Data 1](../artifacts/research/manuscript_revision_astra_20261104/SUPPLEMENT_README.md) and the [reproduction guide](research/PAPER_REPRODUCTION_GUIDE_20261102.md).
Use Python 3.11 and the recorded dependencies. Serving is a separate pinned Qwen3-8B/vLLM 0.10.2 environment with the recorded EOS patch. SkillCommit additionally uses the declared BGE-base-en-v1.5 CPU adaptation. Weights, credentials and host virtual environments are not uploaded.

Completed Run IDs cannot be safely resumed with an invented --resume flag. Fresh learning/inference needs a new Run ID, actual runtime capture and a new freeze. No new model or teacher calls are needed to verify the existing scores.

## 7. Next stage: proposed, not implemented

The proposed scope is rule-constrained skill reasoning across at least five genuinely independent datasets. Mixed training totals about 128 or 256 examples, not that many per dataset. After learning, freeze the actual library and test each dataset separately on about 32 or 64 examples. Two mechanisms should each address a clearly stated failure and have corresponding controlled evidence.

Datasets, licenses, splits, sampling order, task interfaces, mechanisms, scoring aggregation and budgets are not yet selected or validated. OpenExempt jurisdictions are not independent datasets. The previous stage used no validation set; this handoff does not silently introduce one. Existing results and old libraries remain unchanged, and new tasks must use distinct run/data paths.

