# Appendix D. Experimental details and evidence boundaries

Working appendix, updated 23 October 2026. Companion to [manuscript v0.11](manuscript_v1_20261021.md). Exact v0.10 text is retained in the [previous appendix snapshot](revisions/appendix_D_v010_before_complete128_20261023.md). This document describes the executed main TRAIN method and declared remaining experiments. It does not add an experiment, change a score, or imply that a planned comparison has finished. Pending final results, release permissions, and submission metadata remain explicit.

## D.1 Tasks, sources and information access

The task is statutory exemption application, not three-way classification, document matching, or client simulation. For EC, the actor returns the applicable citation set for each public asset. For EV, it returns citation–amount claims. The allowable jurisdiction framework is supplied as part of the public task. EC and EV are independently answered views of the same source, not independent cases; a predicted EC answer is not an input to EV. The actor receives the benchmark's public givens, not the private symbolic case used to construct targets.

The fixed TRAIN stream contains sources 181–308, eight batches of 16, and two tasks per source. OpenExempt is pinned at `ec6fa2547431096588ce2d3ef107b8adc33cd4fe`; the custom generation seed is 2026102101. The configuration specifies 2–4 assets, 2–4 domiciles, a married-case ratio of 0.5, Arizona, Illinois, Oregon, Pennsylvania and Wisconsin, and no irrelevant facts or asset/domicile opinions. Supplied legal frameworks can include federal provisions. This is not the official Advanced Competency profile. The first 48 sources and partial predictions for two later sources had already been inspected during development. All 128 remain TRAIN/development data; “first encounter” refers to the learner, not to a researcher-unseen sample.

A separate IID test packet is declared to contain 128 source cases. Its byte hash can be verified without reading its semantic contents. No TEST task, target, prediction or outcome has been used to choose a method, prompt, library, metric or threshold. TEST execution remains pending. No validation set is used; replay on already seen TRAIN is optimization, not independent evaluation.

| Role or artifact | Permitted information | Excluded information |
|---|---|---|
| Main/empty/static inference actor | Public current task, schema and labels; declared delivered text | Current task's target or feedback, private symbolic construction, solver tool, later/test feedback |
| Main skill teacher | Saved current predictions and released targets; up to 16 selected past sources; current bank and bounded failure records | Unanswered-source or TEST targets; a test-driven library choice |
| ACE reflector and curator | Own saved TRAIN trajectory, released same-case target and controls; accumulated batch reflections | Feedback in first-encounter predictions; imported main bank, answers or teacher responses |
| Text-adaptation analyst | Own complete 256 saved source forecasts, then released TRAIN targets and verifier feedback | A source answer imported from another learner; TEST feedback |
| Blind static library | Public statutory material, without cases, trajectories or targets | TRAIN/TEST examples or outcome-based selection |
| Grader | A saved prediction and its target under the pinned evaluator | Acting as an inference tool or supplying a generated answer to an actor |

The main run saves every logical condition for the batch before grading and learning. ACE similarly saves all batch conditions first; the offline text adaptation saves all 256 own source forecasts before releasing TRAIN labels to its analyst. Private construction fields are not a model input. Initializing the original evaluator with an empty statute list does not invoke the benchmark solver to answer a task.

## D.2 Actor, teacher and direct output contract

| Setting | Executed main seed-45 TRAIN value |
|---|---|
| Actor | Qwen3-8B, bf16, weights frozen |
| Model revision | `b968826d9c46dd6066d109eabc6255188de91218` |
| Hardware and serving | One A40, one vLLM 0.10.2 instance; xgrammar 0.1.23 |
| Context / output cap | 32,768 / 8,192 tokens |
| Generation | Thinking on; temperature 0.6; top-p 0.95; top-k 20 |
| Seeds | Learning generation 45; server 42 |
| Concurrency / prefix cache | One sequence; prefix caching off |
| Teacher | `gpt-5.6-sol`, high reasoning effort |
| Main complete-library cap | 4,096 Qwen tokens, including serialized metadata |
| Candidate limit | At most two teacher attempts per batch; each may edit multiple records |

Additional learning generations use seeds 145 and 245. All final frozen libraries are to be evaluated at common generation seed 45. Three independently learned banks are not three independent inference repetitions on each test source. Fresh teacher invocations and actual outputs are retained; deterministic request reuse within a run is separately recorded.

The main, empty and static conditions share the direct answer system instruction and schema. Public asset references map to literal public mentions, and citation references map to the public legal vocabulary. Decoding is not a hidden eligibility classifier: it does not add a citation, fix an amount, infer ownership or select a successful answer. EV numerical reasoning remains in the frozen model; no arithmetic interpreter, supplementary inference model or answer-dependent retry is used. Native ACE keeps its declared reasoning/bullet-ID/final-answer wrapper and generator prompt, so its difference from direct empty is not an isolated memory intervention.

## D.3 Exact endpoint definitions

Native precision, recall and F1 are produced by the pinned OpenExempt evaluator, not by a semantic LLM judge. The evaluation wrapper passes one case at a time and then takes an equal case mean separately for EC and EV. These are not the evidence-span F1 or three-class accuracy used in earlier project tasks.

For each target asset, native matching first uses the normalized asset description, then a `rapidfuzz.partial_ratio` match with score strictly greater than 90 when an exact match is unavailable. Citation matching follows the upstream normalization, including stripping/lowercasing and its section-sign whitespace rule. Given matched citation outcomes, precision is `TP/(TP+FP)` and recall is `TP/(TP+FN)`, each zero when its denominator is zero; F1 is zero when precision plus recall is zero. EC averages these asset-level scores within the target case. Precision and recall are averaged separately; the reported mean F1 is not recomputed from the reported mean precision and recall.

EV requires a matching normalized citation and an accepted amount. The implemented amount error is exactly zero when prediction equals target. Otherwise it is `abs(prediction/(target+1) - 1)`, and a match requires this value to be strictly below 0.05. A credited target citation is removed from the available match map, so repeating a claim does not create another true positive. The case score averages target-asset scores. This original rule is preserved: it should not be paraphrased as an exact-value endpoint or a conventional symmetric five-percent tolerance. The evaluator's optional amount-relative-error diagnostic is not a primary endpoint here.

Native grading can ignore claims on unmatched extra predicted assets. EC also assigns zero F1 to an empty-target asset for both a correct empty answer and an incorrect nonempty answer. Consequently native EC can have a case-specific maximum below one. We retain native values and separately report a complete-output endpoint. That audit matches each predicted asset at most once, counts unmatched predictions as false positives, pools claim TP/FP/FN within the case, and then averages case F1. EC uses stripped/lowercased decoded citation sets; EV uses the original amount matcher. The shared citation-reference decoder supplies public citation strings before either scorer runs. This secondary claim-micro-within-case score is not the original asset-macro score, even when there are no extra assets.

For example, with two target assets requiring two and one citations, respectively, a prediction that supplies both citations for the first asset and none for the second has native EC F1 `(1+0)/2 = 0.50`. Its within-case claim-micro F1 is `2×2/(2×2+0+1) = 0.80`. This is a hand-constructed counting example, not a selected benchmark case or a result. Both scores can be correct under their distinct definitions.

Negative-target-asset and officially unscored-asset claim counts are reported separately. These counts preserve list multiplicity, whereas EC claim-set matching deduplicates citations. Invalid predictions remain in denominators at the original evaluator's zero score; no invalid-output exclusion or outcome-based repair is introduced. Nonfinite original scores cause a recorded failure rather than an invented replacement.

### TRAIN-only score-ceiling audit

For all 128 TRAIN sources, we supplied the already released target itself to the original grader and independently checked the analytic positive-target-asset fraction. This is a grader diagnostic, not an actor result, a gold-answer baseline or an inference tool. All 256 target-self checks matched the analytic maximum. No TEST contents or outcomes were accessed.

| Complete TRAIN interval | Source n | Native EC maximum (%) | Main EC first forecasts (%) | Native EV maximum (%) |
|---|---:|---:|---:|---:|
| B1–B8 | 128 | 96.88 | 82.03 | 100.00 |
| B2–B8 | 112 | 96.95 | 84.68 | 100.00 |
| B3–B8 | 96 | 96.79 | 84.85 | 100.00 |

Eleven EC sources contain a negative-target asset; no EV target map in this stream contains an empty-claim asset. Complete-output target-self F1 is 100% for both tasks. The B3–B8 EC headroom is still 11.94 points, so the native ceiling does not explain away weak continued EC improvement. These numbers do not renormalize Table 1, change admission or define a new primary endpoint. The [complete TRAIN diagnostic](../artifacts/research/openexempt_legal_scope_20261020/Run03_all128_TRAIN_native_target_self_F1_ceiling_and_residual_headroom_20261022.json) binds every source, target file and evaluator byte hash.

## D.4 Library optimization, management and failure accounting

Each main update receives all 16 current sources and at most 16 past sources, with both task views. Historical communication prioritizes a difficult witness per publicly allowed legal context, then observed proposal regressions and remaining parent failures; source IDs break ties. The teacher also receives full public statutes and at most the last 1,024 characters of each included actual reasoning trace. Those excerpts are not verified causal explanations. Admission replays all seen sources, rather than just the communication subset.

For each task, co-visible jurisdictions, moved record identities and changed shared guidance define connected edit components. Acceptance requires current improvement and retention of native F1, complete-output F1, negative/unscored-asset claim counts and invalid counts for the affected contexts and corresponding final bank. Training-group averages can improve while an individual case worsens. A composed bank can reuse a response only when its complete request is exactly an already observed parent or proposal request; no answer is selected by its score. An accepted partial composition becomes the next actual parent. The immediately preceding batch may supply at most eight unresolved task witnesses per proposal. The batch still writes exactly one final publication, including an unchanged library when nothing is accepted. All nine actual admitted compositions contain 1,152 repeated TRAIN task views, with exact original-response reuse, fresh direct decoding and zero new generations for the composition stage. These are not additional independent sources. The [complete request, decoding and mean-decomposition audit](../artifacts/research/openexempt_legal_scope_20261020/Run03_all9_actual_compositions1152_TRAIN_views_public_side_raw_reuse_fresh_decode_and_mean_identity_20261023.json) checks every such record.

The interface permits create, update, merge and delete. The completed main run actually committed seven creations and 14 updates, with no observed merge or deletion; proposals contained nine CREATE and 24 UPDATE operations. There were 15 teacher responses, nine accepted attempts, five rejected non-NOOP attempts and one explicit NOOP. Supported interface operations are not evidence that those operations were used. Neither a larger record count nor a successful TRAIN gate demonstrates transfer.

Capacity, structural, teacher or model failures remain recorded. There is no silent first-patch fallback, truncation to a fitting old bank, hidden solver, answer repair or score-selected resampling. The declared teacher capacity retry is a transport retry without a returned result, not another legal-answer sample. Failed and rejected work is included in actual cost reporting.

## D.5 Comparators, ablations and independent learning

The following is the declared final matrix, not a completed outcome table. All methods use the same 128 TRAIN sources and frozen 8B inference model. Per-answer inference settings are shared, but complete library limits and actual learning computation differ.

| Final condition | Declared banks / arms | Complete memory cap | Construction and status |
|---|---:|---:|---|
| Strong direct empty | 1 | No skill text | Common reference; final TEST pending |
| Blind static legal library | 1 | 4,096 tokens | Compiled without cases, trajectories or labels; TEST pending |
| Main evolving library | 3 | 4,096 tokens | Seed 45 complete; 145/245 unstarted |
| Each main learner's own B1 | 3 | 4,096 tokens | Its unique first final publication, not a separately selected or learned best bank |
| Native-role ACE task adaptation | 3 | 8,192 tokens | Seed 45 first forecasts complete; final update pending; 145/245 unstarted |
| Trace2Skill text-task adaptation | 3 | 8,192 tokens | Three complete construction profiles frozen, all unstarted |
| Whole-bank submission ablation | 1 | 4,096 tokens | One seed-45 full learning run, unstarted |
| First-commit feedback-policy ablation | 1 | 4,096 tokens | One seed-45 full learning run, unstarted |

The matrix has 16 arms but not 16 independent source sets. Main, ACE and the text adaptation each declare fresh learning seeds 45/145/245. Shared empty and static predictions are not copied into independent observations for each seed. Repeated structural labels, aliases and identical raw responses do not multiply the sample size.

ACE retains generator, reflector, per-bullet native counters and batch ADD curation, with up to three TRAIN reflection rounds. Every first-encounter batch is immutable before target release. Same-case reflection/regeneration is fitting, not a replacement first prediction. Repeated valid bullet IDs remain in saved metadata; reflection tags each distinct ID once. This task wrapper and its legal-feedback access are disclosed, not represented as an author-default reproduction. The complete 128-source first-forecast stream in Table 2 is separate from final-bank testing. Its four EC and nine EV invalid outputs retain their original zero scores; no favourable valid-only subset replaces the full denominator.

An earlier adapter incorrectly invalidated two legal answers because valid metadata contained repeated skill IDs. That run was stopped and preserved, not rescored into the formal comparison. The corrected run started afresh, preserving the original ID lists and legal answers and marking each distinct cited ID once in reflection. The affected later-case feedback had not reached a teacher or a batch-2 curator/publication; the restart was a conservative provenance choice, not evidence that the previous B1 library was corrupted.

The corrected seed-45 ACE learner uses an artifact-verified continuation after a failed-public-output feedback correction. Its unaffected B1/B2 publications and complete B3 first forecasts are retained exactly; no unfinished B3 teacher response or TRAIN regeneration is imported. Incomplete legal answers keep their original zero scores, while the unchanged public failure text becomes available to the TRAIN reflector. Restored origins, fresh continuation work and retired work are separately accounted for. This is one learning trajectory, not an extra independent repeat; seeds 145/245 start empty under the same corrected algorithm. The [continuation protocol](../docs/research/OPENEXEMPT_ACE_FAILED_PUBLIC_TRACE_V4_20261022.md) binds the original lineage and exact last completed prefix.

The current ACE seed-45 B1/B2 bullet text is predominantly Chinese with English legal terms and citations, whereas the observed main guidance is English. Content language was not constrained to be identical across methods. Original generated text is retained without post-hoc translation. The direction and magnitude of a language effect have not been measured; between-method results compare the declared end-to-end adaptations, not an unconfounded change of update rule alone. The [actual second publication and first B3 delivery audit](../artifacts/research/openexempt_legal_scope_20261020/ACEv3_Run02_B2_actual12_bullet_content_and_first_B3_full_native_delivery_no_partial_scores_20261022.json) preserves this limitation rather than attributing it to ACE in general.

The complementary text adaptation uses own source trajectories, a common initial empty scaffold, trajectory-wise edits, 64 ordered hierarchical merges and one planned translation, then lossless preload of all text files. Its full TRAIN replay is report-only, without score gating or best-seed choice. It is not the original ReAct tool-using error analyst. Differences, actual costs, failures and bounds are retained in the [construction protocol](../docs/research/OPENEXEMPT_TRACE2SKILL_TEXT_COMPLEMENT_20261022.md); a win against this variant cannot establish superiority over full native Trace2Skill or unimplemented SkillCommit.

A [23 October operational amendment](../docs/research/OPENEXEMPT_PROSPECTIVE_COMPARISON_PRIORITY_20261023.md) schedules one complete common-actor text construction after the current ACE and queued static TRAIN control, before the remaining independent repeats. The new [first text profile](../configs/openexempt_trace2skill_text_public_assets128_seed45_20261023_run01.json) retains the same analyst, merging, final translation, memory cap, feedback and final report-only replay. Only unrelated job dependencies and cumulative reservation ceilings change; the complete16-arm comparison remains unchanged. All nine prospective profiles have new immutable versions, with superseded never-started configurations preserved. No future profile has started at this revision.

Whole-bank submission changes the acceptance unit, not whether a proposal is checked: the entire proposal must pass the same retention gate. First-commit stops after the first accepted proposal, including a partial acceptance, and disables cross-batch failure carry. It still receives TRAIN labels and can make a second proposal following an initial rejection. Thus it is not a no-label/no-feedback condition, and its effect includes possible differences in actual computation. Both ablations independently learn from empty over all eight batches; neither is a hand-edited final bank.

## D.6 Paired final analysis and uncertainty

Before the first real TEST prediction, all required actual banks, final matrix, configurations, evaluator and current analysis implementation must be frozen. This gate has not yet been met. The preserved [original plan](../docs/research/OPENEXEMPT_FINAL_ANALYSIS_PLAN_20261021.md) and [text-method addendum](../docs/research/OPENEXEMPT_FINAL_ANALYSIS_TEXT_COMPLEMENT_ADDENDUM_20261022.md) were declared before TEST exposure, not before all development.

For a three-bank method contrast, each source contributes the difference between the two methods' mean F1 over their three actual learned banks. For the own-B1 contrast, banks correspond to the same learning seed. For common empty and static references, their one actual source score is subtracted from the main three-bank mean. The final estimate is the equally weighted mean over 128 sources, separately for EC and EV. This is conditional on the realized banks and common fixed evaluation decoding, not a population confidence interval over all possible training runs.

Source-paired cluster bootstrap uses 20,000 resamples and PCG64 seed 2026102192, retaining the paired conditions and two task views within each resampled source. Report ordinary 95% percentile intervals and family-adjusted intervals. The primary family has five comparator families times two endpoints, ten contrasts; adjusted tails are `0.025/10` and `1-0.025/10`. The two single-seed ablations have a separate four-contrast secondary family. Independent learning variability, harmful cases, invalid denominators and all planned/completed counts must also be reported. A favourable subset, an early checkpoint or a nonsignificant difference cannot replace the full denominator or establish equivalence.

## D.7 Actual costs, reproducibility and remaining gaps

The completed main seed-45 TRAIN implementation is `experiments/openexempt_online.py` and `legal_skill_guard/learning/task_scoped_skills.py`, source `6896246`, with `configs/openexempt_closed_feedback_public_assets128_20261021_run03.frozen.json` and contract `direct_statutory_claims` v14. Later ACE-only adapter revision `3dc28b5` leaves the main learner and its four shared actor/scoring files unchanged; it does not imply that every file in the current worktree equals the older manifest. Historical program-output experiments remain development records and are not spliced into the direct-answer stream. The complete confirmatory TEST matrix is not yet frozen.

The completed main seed-45 run contains 1,158 original 8B generations through 1,158 generation-endpoint HTTP requests, 7,655,443 input and 3,232,344 output tokens. Tokenizer and readiness queries are not included in this generation count. Its 15 fresh teacher responses use 3,232,522 input and 51,361 output tokens; the 35,912 reasoning-token subset is already included in output. Elapsed time is approximately 26 h 16 min, not a measured GPU-busy-time integral. Costs include rejected work and replay, not just admitted skills. Per-answer output-cap matching does not imply equal total training calls, teacher tokens, prompt lengths or wall time across methods.

The longest main batch was B6, approximately 5 h 55 min with 249 original calls. That batch-level total is not evidence of a monotonically increasing per-call slowdown. The [actual per-batch runtime decomposition](../artifacts/research/openexempt_legal_scope_20261020/Run03_actual_eight_batch_runtime_decomposition_and_primary_OpenExempt_comparison_boundaries_20261022.json) distinguishes physical calls, teacher response time and observed wall time.

The original requests, responses, source/configuration hashes, failed candidates, publications and existing dual-disk preservation receipts are retained. Exact request reuse is reported as reuse, not another physical generation. This appendix adds no model, test harness or learning-policy change. Current evidence bindings include the [complete main curve](../artifacts/research/openexempt_legal_scope_20261020/Run03_learning_curve_complete_first8_final8_publications_20261022.json), [actual cost](../artifacts/research/openexempt_legal_scope_20261020/Run03_complete_B1_B8_actual_terminal1158_15_cost_20261022.json) and [all teacher/library decisions](../artifacts/research/openexempt_legal_scope_20261020/Run03_all15_teacher14_candidate8_publication_actual_scope_composition_and_library_management_accounting_20261022.json).

The [complete same-source first-forecast comparison](../artifacts/research/openexempt_legal_scope_20261020/Run03_vs_ACEv4_complete_B1_B8_equal128_prequential_FIRSTS_ONLY_last_learning_cost_pending_NOT_TEST_20261023.json) binds all 16 original batch files and aggregates their unrounded score cells, including cold B1 and all failures. This is not a new HTTP or target-scoring re-audit; the original per-batch request/target audits remain its lower-level evidence. At this revision the last ACE TRAIN update and publication are still running, so live teacher or generation counters are not reported as final learning costs. The terminal all-cost summary remains queued independently.

[PENDING RESULT — complete mature comparators, remaining independent learning runs, both independently learned ablations and frozen TEST outcomes.]

[PENDING METADATA — target journal/template, author/contribution details, release location and checked code/data/model redistribution permissions.]

Known TRAIN ambiguities about ownership and personal/business use have not been adjudicated by legal experts. Targets and cases remain unchanged. Benchmark agreement is not expert-validated legal correctness, and this synthetic, supplied-law, limited-jurisdiction setup does not establish real-client advice or broad legal-domain transfer.

## 中文核对摘要

本附录明确EC/EV不是三分类，也不是旧依据抽取F1。原指标先算目标资产分，再算案均值；完整输出审计是在案内汇总主张后算F1，再跨案平均，两者不能混称。EV保留原代码的金额误差式及严格小于0.05，不擅改成精确数值匹配。全部128 TRAIN的目标自答检查只检验评分器：EC最大96.88%、EV100%，后六批EC仍有11.94个百分点空间，不能拿评分天花板解释掉进化弱。

同8B、同来源与单答设置不等于同提示、同容量、同总训练计算。已完成同128来源的八批首答对照，ACE末批学习、最终库及终态总成本仍待完成，不能用首答成绩代替最终测试。三次独立学习、16臂矩阵、十项主要及四项次要比较是已声明计划，未运行部分仍为空；学习器自己的B1库、EC/EV视图和复用响应都不能变成额外独立样本。原始八批指标不改，封存TEST继续不读。实验设计规范用于可复核细节与公平性，evidence-reporting用于区分已执行、计划和未支持主张，不据模板编造五次重复、跨骨干或理论保证。
