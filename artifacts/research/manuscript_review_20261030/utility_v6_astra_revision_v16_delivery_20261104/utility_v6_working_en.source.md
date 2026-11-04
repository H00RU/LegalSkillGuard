# Evidence-guided skill evolution for statutory exemption reasoning

<!-- Implementation binding: configs/openexempt_complete_output_utility_public_assets128_20261030_run01.json, SHA256 5e0486a5352d2e534b50265e3b902ac3aaa0c7d2c5107dd2b904f20a3191e894; frozen manifest SHA256 182e6cbf98e6ee7da8801ad7874554da50a071a91a8a4297e20d87b4fbea30ef. Method sources: experiments/openexempt_online.py, legal_skill_guard/learning/task_scoped_skills.py and legal_skill_guard/learning/publication.py. Task and scoring: legal_skill_guard/openexempt.py and pinned OpenExempt revision ec6fa2547431096588ce2d3ef107b8adc33cd4fe. Source/test bindings remain unchanged during the current build. -->

## Abstract

We study whether reusable legal procedures continue to improve a frozen language model after initial skill acquisition. Statutory exemption classification and valuation require identifying independently applicable provisions and assigning their protected amounts. Evidence-guided skill evolution revises task-specific procedures from released training targets and observed executor errors. A library-level controller compares whole proposals with dependency-consistent edits, retaining revisions that improve complete-output utility while constraining current and historical mean performance. Qwen3-8B processes 128 training cases in eight batches; its first-batch library is then held fixed as a reference for continued evolution. On 128 source-disjoint cases, the final seven-record library reaches 95.46% classification F1 and 87.90% valuation F1. Classification improves by 11.95 percentage points over its own first-batch library, with a family-adjusted source-paired interval of [7.33, 16.60]. The valuation continuation estimate is 3.65 points, with interval [-2.82, 10.28]. Chronological first encounters, matched learning controls and recorded instruction changes explain the results for these completed builds. The findings establish further classification gains after initial skill acquisition through a compact, editable procedural memory.

## 1. Introduction

Legal rule application requires more than recalling a relevant provision: the answer must connect factual conditions to every applicable alternative and compute its consequence. [LegalBench](https://arxiv.org/abs/2308.11462v1) distinguishes rule recall from rule application in its legal-reasoning typology. [OpenExempt](https://arxiv.org/abs/2601.13183) makes these requirements measurable through generated statutory-reasoning problems with symbolic reference solutions.

External experience offers an editable learning interface for a model whose parameters remain fixed. Natural-language lessons can summarize recurring errors, and evolving playbooks can carry procedures across tasks, as studied by [ExpeL](https://ojs.aaai.org/index.php/AAAI/article/view/29936) and [ACE](https://arxiv.org/abs/2510.04618v3). In a legal application, such a procedure must specify when a provision applies, which alternatives coexist, and how a statutory ceiling becomes an asset-specific amount. These are instructions that the executor must carry out, rather than additional statutory text to recall.

The distinction between a plausible abstraction and a useful procedure matters for experience consolidation. [Trace2Skill](https://arxiv.org/abs/2603.25158v5) induces portable procedures from trajectory-local lessons, while [ReasoningBank](https://arxiv.org/abs/2509.25140v2) organizes strategies from successful and failed experiences. [SkillCommit](https://arxiv.org/abs/2608.15165v2) further evaluates behavioral compatibility before broadening skill scope. Our question concerns the execution of legal alternatives by a small frozen model: can observed claim errors produce procedures that remain useful as new cases arrive? This requires distinguishing the value of acquiring an initial library from the value of continuing to revise it.

We study this question through evidence-guided skill evolution for exemption classification and valuation. After saving a batch's blind forecasts, a teacher receives the released reference outputs, actual parent answers and claim-level errors. It revises one task's instructions while preserving the other task's projection. Edits can change applicability conditions and procedural wording, or add a deidentified execution illustration to an otherwise preserved rule. A shared, bounded textual library is the learned state; the executor continues to generate the legal answers directly.

Publication is tied to the quality of those generated answers. The controller evaluates both the complete proposal and dependency-consistent edit components on all encountered training sources. Admission preserves current-cohort and all-seen native and complete-output F1, while bounding historical mean loss. Complete-output scoring accounts for false claims as well as omissions and incorrect amounts. Retained historical failure witnesses inform later teaching. Together, task-focused revision and utility-based admission connect the content of a legal procedure to its measured execution by the intended model.

Evaluation follows a chronological stream and a subsequent frozen-library comparison on source-isolated cases. A library fixed after the first batch tests the incremental value of later evolution. Same-version controls examine teacher-visible execution evidence and the admission/selection policy, while empty, static and experience-learning libraries provide complementary references. The resulting evidence separates initial knowledge acquisition, subsequent-case learning and final-library utility under a common legal task interface.

The completed comparison gives the frozen executor 95.46% EC F1 and 87.90% EV F1 on 128 new source cases. Relative to its own first-batch library, the final library adds 11.95 EC points; this continuation gain remains positive under the prespecified family adjustment. Our contribution couples task-protected procedure revision with library-level utility checks and separates their observed continuation benefit from initial skill acquisition. Complete algorithm definitions, the learned B1/B8 libraries and same-candidate policy readouts make this learning process inspectable.

## 2. Related work

**Experience-based context adaptation.** External learning methods differ in how they represent and consolidate experience. [ExpeL](https://ojs.aaai.org/index.php/AAAI/article/view/29936) extracts natural-language insights from training experiences, and [ReasoningBank](https://arxiv.org/abs/2509.25140v2) distills strategies from self-judged successes and failures for later retrieval. [ACE](https://arxiv.org/abs/2510.04618v3) maintains an incrementally revised playbook through generation, reflection and curation, whereas [Trace2Skill](https://arxiv.org/abs/2603.25158v5) consolidates parallel trajectory-local lessons into a portable skill directory. Our study focuses on procedures for a fixed statutory answer interface, learned from released training labels and observed execution errors, with final-library inference separated from the learning stream.

**Behavioral validation and statutory reasoning.** [Factoring Statutory Reasoning](https://aclanthology.org/2021.acl-long.213/) decomposes rule application into language-understanding subtasks, while [JustifIT-QA](https://aclanthology.org/2026.emnlp-main.593/) combines statutory retrieval with judge-guided answer refinement. For reusable experience, [GSE](https://arxiv.org/abs/2608.06153v1) validates candidate banks through a skill-relation graph, consolidation and historical replay. [SkillCommit](https://arxiv.org/abs/2608.15165v2) tests cross-instance transfer and mechanism compatibility before consolidating instance patches, including on OpenExempt. Our controller instead evaluates a fixed library under task-protected edits, current/all-seen native and complete-output utility, and one dependency-consistent composition. The difference concerns the revision and decision unit, not the general idea of learning from errors or replaying experience. [OpenExempt](https://arxiv.org/abs/2601.13183) supplies computable classification and valuation targets for testing these procedures. A fixed first-batch library makes the incremental value of continued revision measurable on later cases.

## 3. Task and learning problem

We study whether a frozen language model can improve statutory reasoning by accumulating and revising reusable legal procedures. Each source case supplies facts, statutes and the allowable-jurisdiction result. Exemption classification (EC) identifies every applicable asset–provision alternative. Exemption valuation (EV) additionally assigns the protected amount to each alternative. The two tasks share source facts but are answered separately. EV determines eligibility from its own input; the supplied prerequisites identify allowable jurisdictions rather than a solved EC answer.

The target is the benchmark's set of independently applicable alternatives. A specific exemption and a general-property exemption may both be relevant to an asset. Their protected amounts are alternative claims, not an instruction to combine them into an estate-wide allocation. All reference outputs follow the pinned benchmark construction and its supplied statutory text.

Let $B$ denote a textual skill library and $F_\theta$ the executor with fixed model parameters. A skill specifies a public legal namespace, supported tasks, an applicability condition, a procedure and exclusions. A shared record can contain separate EC and EV instruction blocks. Given source $c$ and task $h$, the public namespace and task projection $P_h(B;c)$ select the instructions delivered to the executor:

$$
\widehat y_{c,h}(B)=F_\theta\bigl(x_{c,h},P_h(B;c)\bigr).
$$

Here $x_{c,h}$ contains the case facts, supplied prerequisites and statutes. Projection selects relevant instruction text. The executor decides asset eligibility, applicable provisions and claim values. Library tokens, rather than model weights, are the learned state.

A **record** is a storage unit; its **task projection** is the EC or EV instruction block delivered for that task, containing an applicability condition, procedure and exclusions. For example, the B1 Federal record contains the EC instruction “Apply 11 U.S.C. § 522(d)(5) independently to any property, and retain it alongside every applicable specific paragraph.” Its separate EV block governs amounts. Public task and jurisdiction select the block; a condition in its text is an instruction for the executor, not a learned semantic router. The complete B1 and B8 records are supplied in Supplementary Data 1.

The executor uses shared public citation labels and case-local literal asset references. These identify strings in the supplied text. The decoder restores the corresponding strings by lookup. The same interface serves the empty-library and learned-library conditions. EC instructions precede the case; EV instructions follow it. Public asset references carry neither eligibility decisions nor reference amounts.

## 4. Evidence-guided skill evolution

The learning loop turns observed claim errors into procedures and tests each revision before publication. It has two connected stages: task-focused execution teaching and complete-output utility admission.

![Evidence-guided skill evolution with a frozen legal executor](figures/utility_method_overview_20261030/method_overview.svg)

Figure 1. Execution errors guide task-protected procedure revision. Columns 2–3 repeat for EC and then EV: teach EC, assess/select, teach EV using that selected library, and assess/select again. The final batch check precedes publication. All new-case first answers are saved before target release; the fixed B1 library is evaluation-only. Whole and dependency-consistent edits are assessed on encountered training cases. The published library serves the next batch, and B8 is frozen for the subsequent evaluation.

### 4.1. Task-focused execution teaching

**Chronological evidence.** The learner starts with an empty library and processes successive source batches. It saves all current-batch forecasts before releasing that batch's original reference outputs. Each batch then receives one EC-focused and one EV-focused teaching opportunity. An accepted first-step revision becomes the actual parent of the second step.

The teacher sees the current cases and a bounded historical set. Its evidence includes public facts and statutes, original training targets, actual parent and empty-library answers, and the executor's real response interface. Claim-level feedback distinguishes omitted alternatives, incorrect amounts and extra predictions using the pinned benchmark matcher. Selected model-emitted excerpts supplement these observed outcomes. Original raw outputs remain the evidential source.

**Procedures and execution illustrations.** The teacher can create, update, merge or remove skill text within the active task projection. It distinguishes an inadequate instruction from an execution lapse. The former can change applicability conditions, procedural wording or exclusions. For the latter, the existing legal prefix is preserved and a compact, deidentified execution illustration is added or replaced. For example, an illustration can show that a general-property alternative must coexist with a qualifying specific alternative, without recording an instance's asset names or values.

Each changed skill–task projection has exactly one diagnosis and references supplied training sources. An execution-lapse diagnosis preserves the applicability, exclusions and legal prefix byte for byte, changing the execution illustration after that prefix. Its anchor quotes at least 20 characters from the existing rule. A skill-defect diagnosis permits a rule edit; any nonempty anchor must occur in that same parent projection, while a new projection uses an empty anchor. These are structural provenance checks, not an independent legal correctness judge. Source identifiers and diagnoses stay outside executor memory.

**Task protection.** An EC teaching step preserves the EV projection, and conversely. This permits a teacher to improve one procedure without silently rewriting the other task's instructions. Shared records remain possible; their task-specific blocks are checked separately. The complete serialized library, including metadata and both task views, obeys one token budget.

**Retained failure evidence.** For each teaching task, the next request can retain its latest unsuccessful or partially committed historical proposal, with at most eight actual replay witnesses. A no-op or an unrelated successful edit does not erase that record. Historical candidate outputs retain their original proposed-bank identity. Current-parent reference answers are supplied separately, so an old output is not presented as a fresh execution under the current library.

### 4.2. Complete-output utility admission

**Assessment cohorts.** A proposal is assessed on every encountered training source. Let $D_t$ be the current batch, $H_t$ the preceding sources and $A_t=D_t\cup H_t$. For each task, the controller compares a candidate with the actual parent of that teaching step. Bounded teacher communication therefore does not reduce the assessment cohort.

Let $g_{S,h}(B)$ be the mean score of library $B$ on source set $S$ and task $h$. We use both the original native F1 and complete-output F1 in the admission constraints:

$$
g_{D_t,h}(B')\geq g_{D_t,h}(B),\qquad
g_{A_t,h}(B')\geq g_{A_t,h}(B),
$$

$$
g_{H_t,h}(B')\geq g_{H_t,h}(B)-\varepsilon.
$$

The historical constraint applies when $H_t$ is nonempty. Every inequality is checked separately for EC and EV, and for both score definitions. An admissible change must also strictly improve a current-cohort native or complete-output score, or reduce a current-cohort format-failure or negative/unscored-asset claim count. Invalid responses retain zero scores. False claims remain penalized by complete-output F1. Format and false-claim counts are reported as diagnostics rather than additional zero-increase vetoes.

These constraints preserve current and all-seen aggregate quality while allowing bounded historical trade-offs. They evaluate the realized training executions; individual cases can improve or worsen. The token budget and task-protection constraints apply to the same delivered candidate.

**Dependency components.** For each task, form an undirected graph of public legal namespaces appearing in encountered cases or either library. Join namespaces that are jointly allowable in a case, and join the old and new namespaces of a moved record ID. Changing shared `ALL` guidance joins every namespace; unchanged shared guidance adds no such edge. Connected components define inseparable edit coordinates. Each coordinate is assessed on every current and prior case whose allowable namespaces intersect it, and needs at least one current case. This construction uses public preconditions and library differences, not answer correctness.

**One composed candidate.** The controller admits every component passing the task-level utility checks and takes their unique union. Within each admitted component it uses proposed records; elsewhere it retains parent records. It considers only this composition and the whole proposal, rather than enumerating arbitrary subsets. An incompatible record move, invalid schema or over-budget composition is discarded. Table A2 gives both policy variants.

Every composed request must match a previously measured parent or proposed request in its complete messages, schema and generation profile. The existing raw response is then interpreted under the actual composed library. This yields library-level selection without constructing a case-specific mixture of favorable answers.

**Selection and publication.** Among admissible whole and composed revisions, selection maximizes the changed task's all-seen complete-output gain:

$$
G_h(B',B)=g^{\mathrm{full}}_{A_t,h}(B')-g^{\mathrm{full}}_{A_t,h}(B).
$$

An exact tie retains the whole proposal. The implementation uses the minimum and then mean task-wise gains; under task protection the unchanged task contributes zero, making this ordering equivalent to $G_h$. If neither revision is admissible, the step parent remains. After both teaching steps, the resulting library is checked against the original batch parent with the same contract. Failure of that final check aborts the build rather than substituting an earlier checkpoint. Algorithm 1 specifies the complete selection loop.

The loop freezes its actual last-batch library for evaluation. The model generates direct EC answers and numeric EV claims throughout; numerical operators are excluded from skill records. Exact-request reuse shares identical responses and charges their generation once. It does not turn aliases into independent samples.

## 5. Experimental design

We address four research questions. **RQ1:** How useful is the final frozen library relative to empty, static and experience-learning libraries on new sources? **RQ2:** Do later revisions improve subsequent-case predictions beyond the library acquired after B1? **RQ3:** What does teacher-visible execution evidence add when training labels and replay-based admission remain available? **RQ4:** How does complete-output utility admission compare with the strict admission/selection policy? The frozen comparison addresses RQ1, the chronological and final-library B1 comparisons address RQ2, and the two same-version learning controls address RQ3 and RQ4.

### 5.1. Data and chronological learning

The training stream contains 128 source cases generated with the pinned OpenExempt procedure, with one EC and one EV view per source. We retain the original facts, reference outputs, order and statutory material. Eight batches contain 16 sources each. Current-batch targets are released after all forecast conditions have been saved. There is no validation split.

The generator samples two to four assets per source, uses a configured married-debtor ratio of 0.5 and draws from Arizona, Illinois, Oregon, Pennsylvania and Wisconsin. Optional irrelevant facts and subjective opinions are disabled. These settings are shared by training and source-isolated IID evaluation.

The source-isolated IID confirmation contains 128 additional source cases produced by the same generator and construction settings. Its construction excludes source keys from the training and previously used packets. Confirmation inputs were opened after the method, required controls, actual final-bank hashes, common inference conditions and statistical family had been bound. Previously inspected evaluations remain separate from this confirmation.

### 5.2. Comparators and mechanism controls

The comparison includes a strong empty-library executor, a static law-only library, retained experience-learning libraries and the learned final library. The same ACE library is evaluated through its native interface and a lossless common-interface wrapper. These are two interfaces to one learned bank. Trace2Skill–Text supplies an offline, text-only trajectory-learning comparison, while the SkillCommit paper adaptation supplies task-online repair and behaviorally validated consolidation. All three adaptations use the released training references and the same requested teacher model and reasoning effort; Appendix C specifies their method-specific formation conditions.

Two same-version controls address the current mechanisms. The strict-policy condition retains the teacher, anchors and bounded history while restoring the original zero-regression, count-veto and native-gain selection policy. This tests the admission/selection policy bundle. The teacher-evidence condition retains the utility policy, labels, facts, statutes, current parent and public executor interface while withholding explicit actor outcomes and outcome-labelled feedback from the teacher. Its controller still performs actual replay and admission, so the condition measures the incremental value of teacher-visible execution evidence.

A completed predecessor library is retained as a historical method-version reference, separate from matched component controls. Extra independent learning builds remain deferred. Both control builds completed all eight batches. The original ten-condition comparison binds its actual libraries before prediction. The subsequent SkillCommit supplement freezes its actual eighth-batch terminal bank before evaluating the existing 128-source TEST packet; its two-endpoint comparison is reported separately (Appendix B.5).

### 5.3. Metrics and learning curves

Primary endpoints are the original native per-case EC and EV F1, averaged separately across sources. The pinned evaluator's asset matching and amount tolerance remain unchanged. Complete-output F1 pools true positives, false positives and false negatives within each source and then averages across sources. It includes claims on unmatched or negative-target assets. Consequently, native and complete-output F1 use different within-case aggregation and need not have a fixed numerical ordering.

The chronological curve reports first answers on each new batch before its targets are released. We compare the incoming library with the same-case empty library and a snapshot fixed after exactly the first batch. This snapshot is an evaluation condition, not a teacher or admission input. B2 starts from that same library; subsequent batches measure the effect of further evolution. Post-label assessment replays are reported separately.

Within each evaluation experiment, predictions are saved before its unified scoring. Source-paired resampling keeps each case's EC and EV views together and quantifies uncertainty conditional on the actual frozen libraries. The original contrast family is fixed before confirmation inputs are opened; the later SkillCommit supplement retains its separate declared two-endpoint analysis. Reports include invalid outputs, omissions, incorrect amounts, extra claims, actual skill edits and delivered task blocks. Physical native origins, exact-request reuse, teacher responses and attempts, token totals and elapsed time provide cost accounting.

### 5.4. Implementation settings

**Table S1. Fixed executor, teacher and learning settings.** The source and model revisions, rather than a sampling seed alone, identify the experiment.

| Setting | Value |
|---|---|
| Executor | [Qwen3-8B](https://arxiv.org/abs/2505.09388), fixed weights, BF16 |
| Runtime | One A40 model instance; four native workers; one teacher worker |
| Inference software | vLLM 0.10.2; PyTorch 2.8.0 |
| Teacher request model | `gpt-5.6-sol`, high reasoning effort |
| Training sources / batches | 128 / 8 |
| Sources per batch | 16 |
| Teaching opportunities | One EC step and one EV step per batch; at most 16 successful responses |
| Complete-library budget | 4,096 executor-tokenizer tokens |
| Historical mean-loss allowance $\varepsilon$ | F1 allowance of 0.01, or one percentage point |
| Executor context / maximum output | 32,768 / 8,192 tokens |
| Decoding | Seed 45; temperature 0.6; top-p 0.95; top-k 20; thinking enabled |
| Teacher historical proposal memory | At most one per task; eight witnesses per proposal |
| Upstream generator/evaluator revision | `ec6fa2547431096588ce2d3ef107b8adc33cd4fe` |

## 6. Results

### 6.1. Final-library utility on new sources (RQ1)

The final library improves classification beyond an already useful first-batch library (Table 1). EC F1 rises from 64.48% with no skills to 83.51% after B1 and 95.46% after B8. The paired B8-minus-B1 gain is 11.95 percentage points, with family-adjusted interval [7.33, 16.60]. EV F1 rises from 55.88% to 84.25% and then 87.90%; its continuation gain of 3.65 points has interval [-2.82, 10.28]. Thus, the separate-source comparison supports continued classification learning, while the corresponding valuation effect remains uncertain.

The final library also exceeds the empty, static and retained experience-learning libraries. Relative to the strong empty executor, EC/EV gains are 30.98/32.02 points; relative to ACE with the common interface, they are 28.87/20.98 points. These four adjusted intervals are positive (Appendix B.4). The common-interface comparison shows that ACE's alternative delivery interface alone does not close the gap. The later SkillCommit paper adaptation gives 67.98/64.82%, with positive main-minus-adaptation intervals in its separate existing-TEST supplement (Appendix B.5). These comparisons standardize final executor inference, not library-formation compute or the original authors' systems.

**Table 1. Frozen-library performance on 128 source-isolated IID cases (%).** EC and EV are the original source-mean native F1 endpoints; Avg. is their descriptive mean. Bold denotes the highest point estimate in each column. The SkillCommit row is a later supplement on the existing, previously observed TEST packet, outside the original comparison family. All conditions retain invalid and unfavorable outputs; formation conditions and costs are reported separately.

| Frozen library | EC F1 | EV F1 | Avg. |
|---|---:|---:|---:|
| Strong empty | 64.48 | 55.88 | 60.18 |
| Law-only static | 60.40 | 55.34 | 57.87 |
| ACE native interface | 65.00 | 58.68 | 61.84 |
| ACE common interface | 66.59 | 66.92 | 66.75 |
| Trace2Skill–Text | 55.08 | 53.31 | 54.19 |
| SkillCommit adaptation (supplement) | 67.98 | 64.82 | 66.40 |
| Own frozen B1 | 83.51 | 84.25 | 83.88 |
| Strict-policy control | 80.29 | **89.01** | 84.65 |
| Execution-evidence-withheld control | 86.98 | 80.38 | 83.68 |
| Predecessor library | 87.63 | 83.91 | 85.77 |
| **Evidence-guided evolution** | **95.46** | 87.90 | **91.68** |

The original ten-condition experiment contains 2,560 predictions saved before its unified scoring. The separate SkillCommit experiment adds 256 fresh predictions, saved before its own scoring, giving 2,816 predictions on the same source matrix. ACE's two rows use one learned playbook through two interfaces. The predecessor is a method-version reference, while the strict-policy and teacher-evidence conditions are matched learning controls. Table B3 additionally reports complete-output quality, strict object matching and format failures.

<!-- Actual frozen comparison: legal_openexempt_v6_frozen_source_isolated_IID128_20261031_run01; original completion SHA256 2db223a4205748fda9bb8203b7e5eb07a5b492a210c35dea9def3e6816d2f66d. All2560 actual bank/task-projection requests and original18 endpoints verified by7933c50c62a22fb2eed693b77069e39751f827aefe1d3d8ad99138c916ebfd3c. Table source: paper/tables/utility_frozen_results_20261101.json, SHA2563879cee0d1f5765f3a00637b2c3252640c570d2eed7da4cc1f05031ecd4fb732. -->

### 6.2. Chronological evolution (RQ2)

Continued evolution improves new-case answers beyond the first learned library. Across all 112 sources in B2–B8, the evolving library raises native EC F1 by 10.96 percentage points and EV F1 by 3.42 points over its own fixed B1 library (Table 2). Complete-output gains are 10.27 and 3.44 points. The two libraries coincide at B2, so their separation from B3 onward measures further learning after initial library construction rather than the benefit of receiving any skills.

**Table 2. First-answer performance on the 112 new training-stream sources after B1 (%).** Each source contributes one EC and one EV answer. All B2–B8 forecasts are included; the last row is the paired evolving-minus-fixed-B1 mean in percentage points.

| Library at first encounter | EC native F1 | EV native F1 | EC complete-output F1 | EV complete-output F1 |
|---|---:|---:|---:|---:|
| Empty | 63.21 | 61.43 | 66.56 | 61.29 |
| Fixed after B1 | 80.87 | 84.74 | 84.15 | 83.97 |
| Evolving | 91.83 | 88.16 | 94.42 | 87.41 |
| Evolving − fixed B1, pp | +10.96 | +3.42 | +10.27 | +3.44 |

Actual requests establish where later revisions reach the executor. Of the 112 subsequent EC tasks, 86 receive guidance different from fixed B1; native F1 improves on 52 and decreases on three. For EV, 96 tasks receive changed guidance, with 36 improvements and 14 decreases. The remaining 26 EC and 16 EV tasks have identical inputs and reuse the same recorded responses. Same-case references separate library utility from changes across batches. For example, all three EV conditions decrease at B7, while the evolving library remains 2.25 points above fixed B1; B8's paired advantage is 6.44 points. Figure 2 retains these observed fluctuations and reports both scoring views of every batch.

<!-- Actual exposure: Utility_v6_main8_all112_actual_postB1_skill_exposure_both_HTTPs_224pairs_scope_and_revision_timing_not_TEST_20261030.json, SHA256 ebe91485b25176ac8a169225ecae32829ec9da6bafe306efee16746b468dcca6. All 112-source primary means remain unchanged; exposure groups are not randomized causal controls. -->

The library evolves mainly by revising existing procedures. Nine of the 16 teaching steps commit an update: five EC steps and four EV steps. After B1, the accepted edits make 16 revisions to existing task projections and add one EV projection while retaining seven records. The final library occupies 3,993 tokens, and each subsequent first-answer task receives two or three projected instruction blocks (Appendix D). These records distinguish content evolution from growth in the number of entries.

Recorded edits expose what this continuation changes. The Federal EC record already requires the general-property alternative at B1. B2 expands category-specific guidance and puts the wildcard check last; B3 turns the same listed provisions into two mandatory passes and a per-asset audit. A later illustration revision preserves that legal prefix exactly. Appendix E shows the original instruction excerpts and a new-source answer, separating procedural refinement from added provision coverage.

![Figure 2. All eight batches of chronological first-answer performance.](figures/utility_learning_curves_20261030/learning_curves_preview.png)

**Figure 2.** Continued evolution improves subsequent-case performance beyond the first learned library. Each point is the mean over 16 new source cases, whose EC and EV first answers are saved before the current targets are released. Panels show native and complete-output F1 for the evolving, empty and fixed first-batch libraries. The fixed B1 library becomes available at B2; B1 starts empty. All eight observed batches are shown without smoothing. Post-label replay scores are excluded.

### 6.3. Execution evidence and publication policy (RQ3, RQ4)

**Teacher-visible execution evidence (RQ3).** Hiding explicit executor outcomes from the teacher while retaining facts, statutes, released targets and replay-based admission yields final EC/EV F1 of 86.98/80.38%. The complete method improves these endpoints by 8.48 points [3.91, 13.59] and 7.53 points [2.38, 12.67], respectively, where brackets give family-adjusted source-paired intervals. This supports grounding revisions in observed execution errors rather than reference solutions alone under the retained learning protocol. The control still receives labels and public solved material, and its controller supplies indirect feedback through replay and admission.

Chronological evidence distinguishes this effect from initial acquisition. On the same 112 post-B1 sources, the evidence-withheld library records native EC/EV F1 of 84.54/81.27%, compared with 84.54/81.91% for its own B1 snapshot. Its continuation changes are 0.00/-0.64 points, whereas the main method changes by +10.96/+3.42 points (Table 2). Appendix D.5 reports both complete controls and their learning-path boundaries.

**Admission and selection policy (RQ4).** Complete-output utility admission gives a 15.17-point EC advantage over the strict-policy control, with adjusted interval [10.53, 20.35]. The strict control instead has the highest EV point estimate, 89.01% versus 87.90%; the paired utility-minus-strict EV difference is -1.11 points [-6.20, 3.65]. The supported policy advantage is classification quality, not superiority on every endpoint. The control changes admission, selection and their teacher-facing objective together. Same-candidate policy readouts locate two disagreements in its recorded proposals, including rejection of a B1 valuation gain because negative/unscored-asset claims rise from one to two. Conversely, both policies choose the same result from every main-run candidate pool (Appendix D.6). The final-bank contrast therefore concerns the policy-conditioned learning path, not an isolated veto mechanism.

**Complete-answer quality.** The main library attains 96.67% complete-output EC F1 and 87.51% complete-output EV F1. Between own B1 and B8, omitted EC targets decrease from 248 to 40 and extra EC predictions from 44 to 26. EV improves less: incorrect-amount targets decrease from 69 to 57, leaving a substantial valuation error source (Table B6). Its two invalid EV outputs retain zero scores. Strict decoded-object matching is 57.81/41.41%; this representation-sensitive diagnostic is not whole-case legal accuracy (Appendix B.3).

## 7. Discussion

**Execution-grounded legal procedures.** The completed source-isolated evaluation shows that an editable library can substantially improve a small frozen model's statutory answers. The teacher-evidence control connects this utility to information about the model's actual omissions, incorrect amounts and extra predictions. The teacher acts during learning; the frozen executor still selects provisions and amounts itself at test time. The learned state therefore consists of reusable instructions rather than a second answer-generating model or a privileged numerical solver.

**Improvement after initial acquisition.** A useful initial library and a useful evolution process answer different questions. The own-B1 reference holds initial knowledge fixed while later procedures are revised. Its paired comparison supports further classification improvement both on subsequent learning-stream sources and on the separate frozen evaluation. The positive EV continuation estimate remains uncertain under family adjustment. Distinguishing these effects makes continued learning testable without assuming monotonic improvements across changing batches.

**Evolution within bounded memory.** The stream retains seven records while revising 16 existing task projections after B1 and adding one EV projection. Actual delivery traces and the own-B1 contrast connect these changes to the instructions used on later cases. Task protection permits targeted revision inside shared records, while complete-output assessment charges both omissions and false claims. The resulting memory objective concerns the utility of applicable procedure text, not growth in the number of entries.

**Interpretation boundary.** The evidence concerns statutory alternatives under supplied facts, statutes and jurisdiction prerequisites in one generator, not end-to-end legal advice or unseen legal domains. The complete controls evaluate teacher-evidence and policy bundles under one completed learning build per condition. Source-paired intervals quantify case variation for those banks; independent learning replication remains necessary to estimate build-to-build variation. The observed classification continuation gain and bounded valuation result are the conclusions supported by this experiment.

## 8. Conclusion

Task-focused execution teaching and complete-output utility admission turn observed legal errors into reusable skills for a frozen 8B model. Across 128 new OpenExempt sources, the final library attains 95.46% EC and 87.90% EV F1 and adds 11.95 EC points beyond its first-batch library.

## Appendix A. Learning algorithm and evidence routing

### A.1. Chronological library updates

The executor parameters, task interface, decoding profile and source order remain fixed throughout a build. The initial library is empty. The following sequence implements one batch; its output library becomes the next batch's incoming library.

1. **Forecast.** Generate and save both task views of every current source under the incoming library, the empty library and the fixed first-batch library. The first-batch reference is empty during B1 and is set immediately after B1 publication. Two retained reference aliases, the frozen initial library and direct-numeric empty condition, also pass through the same request path. In this build the initial library is empty and every condition uses direct numeric claims. Identical requests share one physical response.
2. **Release.** Read current-source targets after all forecast conditions have been saved. Save original forecast scores separately from the subsequent teaching and replay records.
3. **Teach EC.** Assemble the actual parent library, current-source evidence, selected historical evidence and retained EC proposal feedback. Request one diagnosed edit. Check the edit against its released evidence, legal anchors, protected EV projection and complete-library token budget.
4. **Assess and select.** A changed, valid proposal is executed on all encountered sources. Check the whole proposal and dependency-consistent components under Section 4.2. If a composed library is admissible, verify the complete request identity for its reused executions. Compare admissible whole and composed libraries, publish the selected change as the next step's parent, or retain the existing parent.
5. **Teach EV.** Repeat the same process for EV using the actual result of the EC step. Protect EC instructions. The two opportunities concern different tasks, rather than repeated attempts on whichever task is easier to improve.
6. **Publish the batch.** Check the resulting library against the original batch parent. Save the actual library, both teaching decisions, assessment records and parent-to-publication lineage. After exactly B1, copy the actual publication into the fixed first-batch reference; never replace that reference using later performance.

A no-op, an invalid edit or an over-budget proposal consumes its scheduled teaching opportunity without an extra same-task retry. The completed stream returns its actual B8 publication. A predeclared forward-harm stop examines two consecutive batches from B2 onward: mean native EC/EV loss greater than two percentage points against a retained empty/initial/direct reference, or EV complete-output loss greater than two points against the initial reference. Such a stop terminates the build rather than selecting a favorable earlier checkpoint. The first-batch frozen reference supplies evaluation evidence and is not used in teaching or admission.

### A.2. Decision contracts and component composition

**Algorithm 1. Task-protected library selection.** Inputs are the step parent, one proposed task edit, measured parent/proposal outputs on encountered sources, public allowable namespaces and the fixed policy in Table A2. EC is processed before EV; each selected result becomes the next step's parent.

1. Validate the delta, evidence references, diagnoses, anchors, unchanged other-task projection and 4,096-token complete-library cap. An invalid or unchanged proposal retains the parent and consumes the opportunity.
2. Build the task-specific namespace graph defined in Section 4.2. Assess each connected component on all intersecting current and prior sources; a component without current support is ineligible.
3. Form exactly one composition from all admitted components, retaining the parent elsewhere. Reject an invalid or over-budget composition. For every encountered task, require its complete request to equal a measured parent or proposal request before reusing that response.
4. Apply the library-level policy separately to the whole proposal and this composition. The policy checks both tasks and both score definitions. Its candidate set contains at most these two libraries, not every component subset.
5. Rank admissible candidates by the minimum, then mean all-seen task gain under the policy's selection score. Exact ties prefer the whole proposal. If none passes, retain the parent.
6. After the EV step, check the resulting bank against the original batch parent. A failed final check aborts the build. Otherwise save the actual bank, scores and decision lineage; freeze B1 for evaluation only and return B8 after eight batches.

**Table A2. Complete decision contracts.** All score constraints are task-wise. Native and complete-output F1 are checked separately, with numerical comparison tolerance $10^{-12}$. Prior constraints are omitted at B1. A component uses its intersecting cohort; whole/composed libraries use all encountered sources.

| Decision element | Complete-output utility | Strict-policy control |
|---|---|---|
| Current native and complete-output means | No loss | No loss |
| Prior native and complete-output means | Loss at most 0.01 | No loss |
| All-seen native and complete-output means | No loss | Implied by current/prior checks |
| Format failures and negative/unscored-asset claims | Diagnostic counts, not separate vetoes | Neither count may rise on current or prior cohorts |
| Strict current improvement | Higher native/full F1 or lower diagnostic count | Same requirement |
| Selection score | All-seen complete-output F1 gain | All-seen native F1 gain |
| Candidate ordering | Minimum task gain, then mean; whole wins ties | Same ordering |
| Teacher-facing contract | States utility constraints and objective | States strict constraints and objective |
| Shared structural checks | Task protection, diagnoses, public components, token cap, exact-request composition | Same checks |

**Table A3. One actual composed selection: B2 EC.** Scores are means over the 32 encountered sources (%), before the subsequent EV step. Both proposed libraries pass utility admission. The component union retains the parent in Arizona and adopts the other two proposed components; it is selected for its larger complete-output gain.

| EC-step library | Native F1 | Complete-output F1 | Serialized tokens |
|---|---:|---:|---:|
| Step parent (B1) | 85.07 | 88.12 | 2,461 |
| Whole EC proposal | 90.05 | 92.24 | 2,699 |
| Admitted-component union | 91.62 | 94.29 | 2,664 |

The Arizona component has four current and three prior sources and fails current nonregression. The admitted components are Federal–Oregon–Pennsylvania–Wisconsin and Illinois. Co-allowability joins the Federal-connected namespaces; it is not a manually fixed partition. The selected union's complete-output EC gain is 6.17 points versus 4.11 for the whole proposal. EV requests remain unchanged. Every composed request is identical to a saved parent/proposal request; no extra generation or favorable per-case answer choice is introduced.

### A.3. Communication and execution evidence

Each task-focused request includes every current source and selects up to 16 historical background sources. Mandatory retained failure witnesses are included first, followed by public-context witnesses, observed regressions and low-scoring parent cases, with source identifiers breaking ties. If mandatory witnesses exceed the background limit, the limit expands to include them. This is communication selection within already encountered training data. Proposal assessment still covers every encountered source.

The supplied public law corpus is deduplicated within a request. Current-parent answers contain the actual parsed output, native and complete-output scores, and claim-level errors. For each selected parent execution, the teacher can also see the final native submission and up to the last 1,024 characters of model-emitted reasoning. A malformed final submission contributes bounded head and tail excerpts. These excerpts are identified as unverified model emissions; they do not replace the original output or reference target.

Retained proposal feedback identifies the historical candidate and its original parent, while references to current-parent answers point to separately supplied observations. Each task retains at most one unsuccessful or partially committed proposal with at most eight replay witnesses. The controller distinguishes a fully committed proposal, a partially committed proposal and a rejected proposal. The executor receives the resulting procedures, not the source identifiers, diagnostic labels or historical answer records.

### A.4. Exact-request accounting

A request identity contains the full messages, response schema and generation profile. A library hash alone is insufficient: different libraries can deliver the same task projection, while changed applicable text produces a different request. Every reused response retains its original raw-call identity and is decoded for the actual requesting condition. A dependency composition is valid only when each composed request matches a measured parent or proposal request. Consequently, composition selects a fixed library without an additional generation round or per-case score-based answer choice.

A fixed sampling seed specifies a decoding condition, not guaranteed bitwise repeatability of fresh online calls ([version-pinned serving documentation](https://docs.vllm.ai/en/v0.10.2/usage/reproducibility.html)). Exact-request reuse shares the original recorded response rather than issuing a fresh repetition.

Cost reporting counts each physical native origin once and lists logical forecasts, assessment views and reuse separately. Teacher responses and transport attempts are distinct quantities. Provider-reported cached input is a subset of input tokens, and reasoning tokens are a subset of output tokens; neither is added a second time. Actual total tokens and elapsed times, rather than assumed equal compute, describe each learning method.

## Appendix B. Prespecified frozen comparison and uncertainty

### B.1. Source and library boundaries

The confirmation recipe fixes 128 source cases with seed 2026103001. It excludes the source keys of 564 cases across 15 earlier packets. Each source contributes one EC and one EV question. This is source-isolated IID evaluation within the pinned generator, rather than a claim of unseen-jurisdiction or official Advanced-benchmark evaluation.

**Table B1. Source distributions and public legal context.** Counts refer to source cases, not the doubled EC/EV questions. Both packets draw from the same legal and asset vocabulary.

| Property | TRAIN (128) | TEST (128) |
|---|---:|---:|
| Cases with 2 / 3 / 4 assets | 43 / 48 / 37 | 42 / 45 / 41 |
| Target claims per case, min / median / max | 1 / 6 / 16 | 2 / 6 / 16 |
| Arizona | 24 | 20 |
| Illinois | 28 | 28 |
| Federal + Oregon | 22 | 24 |
| Federal + Pennsylvania | 27 | 26 |
| Federal + Wisconsin | 27 | 30 |
| Distinct target-citation sets | 55 | 62 |
| Distinct literal asset descriptions | 378 | 383 |

The packets share 287 literal asset-description strings and 26 target-citation sets, but no source keys. These overlaps characterize the controlled IID setting: source isolation does not imply new statutory vocabulary or new asset templates.

The prespecified matrix contains ten conditions: empty, static, ACE native, ACE common-interface, Text, the evolved B8 library, its own fixed B1 library, the strict-policy control, the teacher-execution-evidence-withheld control and the completed predecessor library. It therefore contains 2,560 logical predictions. The two ACE conditions share one learned bank; the predecessor is a version reference, not a matched component ablation.

Before opening confirmation questions, the evaluation binds each real learned bank to its configuration, frozen source manifest, completion, publication and terminal preservation. The B1 reference additionally binds its actual first-batch snapshot. Learning-source snapshots establish the executor and grader shared across teaching versions. All condition forecasts are saved before confirmation targets are read for unified scoring. Evaluation performs no teacher update or skill revision.

### B.2. Scores and paired contrasts

For case $i$ with reference assets $a=1,\ldots,m_i$, let $T_{ia}$, $P_{ia}$ and $N_{ia}$ denote matched, false-positive and false-negative claim counts. With zero-denominator F1 defined as zero, the native and complete-output case scores are

$$
F^{\mathrm{native}}_i=\frac{1}{m_i}\sum_{a=1}^{m_i}\frac{2T_{ia}}{2T_{ia}+P_{ia}+N_{ia}},\qquad
F^{\mathrm{full}}_i=\frac{2T_i}{2T_i+P_i+N_i}.
$$

The primary endpoint is the arithmetic mean of the 128 native case scores. Complete-output F1 instead pools counts within each case, including claims on unmatched or negative-target assets, before averaging cases. Different aggregation weights mean it need not be lower than native F1. Native precision and recall are also asset means, not a new F1 computed from their across-source averages.

The pinned evaluator strips whitespace and lowercases asset descriptions, first matching exact descriptions and otherwise taking the best RapidFuzz partial-ratio match strictly above 90. EC strips/lowercases citation strings and uses sets, so duplicate normalized citations are removed. EV greedily matches each predicted citation to a remaining reference claim at most once. An exact amount match is accepted; otherwise its error is $\operatorname{abs}(\widehat{v}/(v+1)-1)$, and a match requires error strictly below 0.05. A wrong amount contributes one false positive while leaving its reference as a false negative; a duplicate or unmatched claim contributes a false positive. Invalid whole outputs score zero.

An empty-reference asset contributes zero to native asset-mean F1 even when correctly empty. Reference answers therefore score 98.50%, not 100%, under native EC on this packet; reference-self EV is 100%. This convention is preserved, not renormalized. As a worked EC example, reference $A=\{p,q\}, B=\varnothing$ and prediction $A=\{p\},B=\varnothing,X=\{r\}$ give native $(2/3+0)/2=1/3$ and complete-output $2/(2+1+1)=1/2$. The unmatched $X$ claim is charged only by the latter. For EV, reference $A=(p,100), B=(q,200)$ and prediction $A=(p,150),B=(q,200),X=(r,50)$ give native $1/2$ and complete-output $2/(2+2+1)=0.4$.

For a fixed comparator, source $i$ supplies the paired difference between the evolved library and that comparator. The reported effect is the mean of these 128 differences, with EC and EV reported separately. Source-paired bootstrap draws resample whole source indices, preserving both tasks and all conditions together. The procedure uses 20,000 draws from NumPy PCG64 with seed 2026103092 and linear quantiles.

The evolved library is compared with the other nine conditions on both native endpoints. These 18 contrasts form one primary family. Reports provide ordinary 95% intervals and Bonferroni-adjusted intervals with quantiles $0.025/18$ and $1-0.025/18$. Complete-output quality, strict object matching, error categories and cost are descriptive accompanying evidence. A 200,000-draw numerical sensitivity check with the same seed preserves all 18 adjusted-interval sign conclusions; reported intervals remain the original 20,000-draw estimates. The bootstrap characterizes source variation conditional on the actual learned libraries; it is not a substitute for independent learning builds.

### B.3. Complete-output quality and invalid responses

**Table B3. Accompanying quality endpoints on all 128 cases per task (%).** Paired values are EC / EV. Strict object match compares the decoded full answer with the reference using object equality; format-failure counts use the original parser. Complete-output F1 is the per-case pooled-claim score averaged across sources, not a global ratio over all claims.

| Frozen library | Complete-output F1 EC / EV | Strict object match EC / EV | Invalid EC / EV |
|---|---:|---:|---:|
| Strong empty | 66.65 / 56.51 | 11.72 / 8.59 | 0 / 1 |
| Law-only static | 63.64 / 56.37 | 9.38 / 8.59 | 0 / 3 |
| ACE native interface | 66.86 / 59.51 | 14.06 / 10.94 | 6 / 4 |
| ACE common interface | 69.73 / 66.41 | 17.19 / 14.84 | 1 / 1 |
| Trace2Skill–Text | 58.88 / 54.78 | 11.72 / 7.81 | 5 / 1 |
| SkillCommit paper adaptation | 69.79 / 64.47 | 20.31 / 18.75 | 3 / 4 |
| Own frozen B1 | 85.25 / 83.75 | 27.34 / 35.16 | 0 / 2 |
| Strict-policy control | 81.60 / 88.28 | 26.56 / 44.53 | 2 / 1 |
| Execution-evidence-withheld control | 88.51 / 79.84 | 44.53 / 26.56 | 0 / 0 |
| Predecessor library | 88.86 / 83.33 | 32.81 / 30.47 | 0 / 1 |
| Evidence-guided evolution | 96.67 / 87.51 | 57.81 / 41.41 | 0 / 2 |

Across the original ten conditions and the SkillCommit supplement, all 37 invalid outputs correspond to output-length terminations and retain zero scores. The main library has two such EV outcomes; SkillCommit has three EC and four EV outcomes. The original grader does not emit complete pooled counts for those malformed outputs, so no global micro-average is reconstructed from a favorable subset or repaired answer.

Strict object matching ignores dictionary-key order but preserves list order, duplicate entries, raw amounts and explicit empty-asset entries. It does not apply the native scorer's citation normalization or amount tolerance. For B8, 74 EC and 53 EV answers match strictly; another 19 EC and seven EV answers differ only in list ordering. Five EV references omit zero-claim assets for which the common response interface requests an explicit empty list. Three B8 EV answers satisfy every scored claim but fail strict equality for that representation difference. Accordingly, the main library's 93 EC and 63 EV cases with complete-output F1 equal to one should not be confused with its stricter object-match counts, or with externally adjudicated legal correctness.

### B.4. Prespecified paired effects

**Table B4. Evolved-library minus comparator native F1 (percentage points).** Each cell gives the paired effect and its family-adjusted interval. All 18 EC/EV endpoints share the prespecified Bonferroni family; 15 adjusted lower bounds are positive. Ordinary 95% intervals, case-level differences and source keys remain in the machine-readable results.

| Comparator | EC difference [adjusted interval] | EV difference [adjusted interval] |
|---|---:|---:|
| Strong empty | +30.98 [24.80, 37.51] | +32.02 [23.79, 40.39] |
| Law-only static | +35.06 [28.48, 41.91] | +32.57 [24.69, 40.87] |
| ACE native interface | +30.46 [24.05, 37.49] | +29.22 [21.67, 37.30] |
| ACE common interface | +28.87 [22.97, 34.79] | +20.98 [14.63, 27.43] |
| Trace2Skill–Text | +40.39 [32.92, 48.30] | +34.59 [26.96, 42.55] |
| Own frozen B1 | +11.95 [7.33, 16.60] | +3.65 [-2.82, 10.28] |
| Strict-policy control | +15.17 [10.53, 20.35] | -1.11 [-6.20, 3.65] |
| Execution-evidence-withheld control | +8.48 [3.91, 13.59] | +7.53 [2.38, 12.67] |
| Predecessor library | +7.83 [4.57, 11.16] | +3.99 [-1.66, 9.86] |

The EV contrasts with own B1, strict policy and the predecessor have adjusted intervals spanning zero. No equivalence or non-inferiority conclusion is inferred from these intervals. Table B4 retains the original family in `paper/tables/utility_frozen_results_20261101.json`. Tables 1 and B3 extend its unchanged ten-condition rows with the SkillCommit supplement in `paper/tables/utility_frozen_results_with_skillcommit_20261104.json`.

### B.5. Existing-TEST SkillCommit supplement

This supplementary comparison uses the actual terminal SkillCommit bank on the existing, previously observed 128-source TEST packet. All 256 new predictions are saved before their own unified scoring. Source-paired resampling uses 20,000 draws, seed 2026110101 and the same source-index draws for EC and EV. The declared two-endpoint family uses quantiles 0.0125 and 0.9875 for simultaneous 95% intervals, separately from the unchanged original 18-endpoint family. Intervals condition on these actual frozen banks rather than independent learning-build variation.

**Table B5. Main method minus SkillCommit paper adaptation native F1 (percentage points).**

| Task | Paired difference | Ordinary 95% interval | Two-endpoint adjusted interval |
|---|---:|---:|---:|
| EC | +27.49 | [23.46, 31.70] | [22.92, 32.30] |
| EV | +23.08 | [18.23, 27.94] | [17.55, 28.68] |

### B.6. Claim-level error decomposition

**Table B6. Observed claim counts in parseable outputs on the fixed 128-source comparison.** TP denotes correct claims; omissions have no corresponding predicted citation; wrong amounts have a matched citation but fail EV tolerance. Extra counts include duplicate EV claims. Invalid outputs remain separate zero-score cases, not reconstructed claim counts. A wrong amount contributes both FP and FN to F1; columns are diagnostic categories, not independent endpoints.

| Task / library | TP | Omitted targets | Wrong amounts | Extra predictions | Invalid |
|---|---:|---:|---:|---:|---:|
| EC / Empty | 483 | 461 | 0 | 45 | 0 |
| EC / B1 | 696 | 248 | 0 | 44 | 0 |
| EC / B8 | 904 | 40 | 0 | 26 | 0 |
| EV / Empty | 433 | 430 | 69 | 82 | 1 |
| EV / B1 | 778 | 85 | 69 | 49 | 2 |
| EV / B8 | 811 | 58 | 57 | 31 | 2 |

## Appendix C. Experience-library formation conditions

The retained ACE, Trace2Skill–Text and SkillCommit adaptations use the same 128 training sources and original EC/EV references. Their configurations match the main method's Qwen3-8B decoding profile and request `gpt-5.6-sol` with high reasoning effort. ACE receives the reference and actual prediction at every used reflection; Trace2Skill–Text analyzes each of the 256 empty-library trajectories with its reference, score and actual output. These are task-interface adaptations, rather than reproductions of the authors' agentic environments.

**Table C1. Retained experience-library formation.** Counts describe the actual task adaptations, with their distinct formation budgets.

| Learning condition | Library formation | Executor memory-token cap | Teacher responses |
|---|---|---:|---|
| Execution-evidence evolution | Online, task-focused revision and utility admission | 4,096 | 16 used |
| ACE adaptation | Online reflection, regeneration and incremental curation | 8,192 | 423 used in the retained stream |
| Trace2Skill–Text | Offline trajectory analysis, hierarchical merge and text translation | 8,192 | 321 used |
| SkillCommit paper adaptation | Task-online repair and behaviorally validated consolidation | 8,192 (top 4 memories) | 930 used |

ACE's retained stream contains 415 reflections and eight batch curations. Its continuation records separately preserve 19 successful but uncommitted teacher responses; failed-request usage is unknown rather than zero. Trace2Skill–Text uses 256 trajectory analyses, 64 merges and one translation, followed by a training replay that does not select its final bank. Historical formation schedules and budgets remain distinct from the main method's four-worker learning schedule. The final comparison standardizes executor inference over these frozen libraries; formation costs are reported separately.

SkillCommit repairs failed first answers using a separate training-target-assisted teacher reference, verified by the native scorer before up to three local patch attempts. EC and EV have separate pools. Consolidation uses up to four retrieved candidates, a two-thirds behavioral threshold, two reverse witnesses per active candidate and up to three abstraction versions. Full-scope replay precedes commitment; a supported subset of at least two sources can instead be narrowed and revalidated once, retaining the parent and uncovered local patches. Local BGE embeddings replace the paper's embedding service. At inference, the original public task prompt, including facts and supplied law, retrieves up to four complete memories from the union of same-task patterns and residual patches, within an 8,192-token delivery cap rather than a whole-pool cap. Memory keys combine applicability, repair and exclusions. The local encoder embeds all prompt windows rather than truncating long inputs, using normalized, length-weighted window representations and cosine ranking; ID order resolves ties. This encoder and the direct numeric answer interface are explicit adaptations, not the authors' released executor setup.

The completed build contains 21 higher-level patterns and 23 residual patches. All 256 TEST tasks receive four complete patterns, occupying 1,351–1,615 recorded tokens. Actual deployment uses six distinct EC patterns and four EV patterns; every EV task receives the same four, and residual patches remain unselected. All four EV applicability fields explicitly concern Illinois, although only 28 of 128 TEST sources allow Illinois; the remaining 100 receive the same Illinois-focused instructions. One delivered repair begins, “Assess every asset against each statutory alternative independently,” before specifying Illinois subsection (b). Saved public-query rankings and complete delivery texts are included in Supplementary Data 1. This scope-concentration diagnostic limits interpretation of the local retrieval adaptation; it is not evidence that the original SkillCommit system has the same behavior or that retrieval alone causes the score gap. The retained implementation was fixed for paper-aligned training/consolidation behavior before its own TEST inference; retired implementation attempts, with separate costs in Appendix D.3, did not supply memories to this build. No post-TEST retrieval retuning or extra answer selection is used here.

## Appendix D. Observed skill evolution and compute

### D.1. Published library changes

**Table D1. Actual committed task projections, not proposed operations.** A shared record can hold separate EC and EV blocks, so a new task projection need not add a record. Each batch has one teaching opportunity per task.

| Batch | Records | EC / EV blocks | Serialized tokens | Committed EC projection edits | Committed EV projection edits |
|---|---:|---:|---:|---|---|
| B1 | 7 | 7 / 6 | 2,461 | 7 new | 6 new |
| B2 | 7 | 7 / 6 | 3,257 | 4 revised | 5 revised |
| B3 | 7 | 7 / 6 | 3,413 | 3 revised | 0 |
| B4 | 7 | 7 / 6 | 3,413 | 0 | 0 |
| B5 | 7 | 7 / 6 | 3,594 | 1 revised | 0 |
| B6 | 7 | 7 / 6 | 3,654 | 2 revised | 0 |
| B7 | 7 | 7 / 7 | 3,975 | 0 | 1 new |
| B8 | 7 | 7 / 7 | 3,993 | 0 | 1 revised |

Each post-B1 first-answer task receives two or three blocks selected by its public task and supplied legal namespaces. Delivery records establish which instructions the executor received; answer scores measure whether those instructions helped. Forecasts use the incoming published library, so edits made after B8's first answers contribute to the final-library comparison rather than retrospectively to B8's curve.

The evidence-withheld control finishes with 12 records occupying 3,965 tokens. It retains two revisions after B6 and one after B8. The B6 revisions reach the B7–B8 forecasts; the B8 revision first reaches new cases in the frozen-library comparison.

### D.2. Actual build cost

The totals cover this complete learning build, including its forecast reference conditions and training-assessment replays. Each physical native origin is counted once; exact-request reuse retains that recorded response.

**Table D2. Observed cost of the main learning build.**

| Quantity | Recorded value |
|---|---:|
| Physical native generations | 1,207 |
| Exact-request reuses | 3,497 |
| Native input / output tokens | 8,293,891 / 3,196,466 |
| Successful teacher responses / recorded attempts | 16 / 16 |
| Teacher input / output tokens | 1,778,335 / 66,439 |
| Cached input / reasoning output subsets | 115,968 / 38,939 |
| Service wall time | 9.00 h |

Cached input is included in teacher input, and reasoning output is included in teacher output. Service wall time is measured from the manager's monotonic start and success events; it includes teacher waits, CPU work and terminal preservation, and is not a measurement of active GPU hours. Frozen-test inference and other learning builds are outside these totals.

### D.3. Teacher and executor work across retained builds

The main build uses fewer teacher tokens than each of the three retained experience adaptations (Table D3). Compared with the retained SkillCommit adaptation, it uses 90.97% fewer teacher input tokens and 40.10% fewer physical executor generations under the recorded formation schedules. Local counts include each build's first answers, forecast reference conditions and training-assessment replays. Teacher and executor tokens are reported separately because the two roles use different models; method-specific formation budgets do not imply a common GPU-time or monetary cost.

**Table D3. Recorded response generation in the actual retained learning streams.** Teacher input includes cached input, and teacher output includes reasoning output. Formation schedules and memory budgets are specified in Appendix C.

| Learning condition | Role | Responses | Input tokens | Output tokens |
|---|---|---:|---:|---:|
| Execution-evidence evolution | Teacher | 16 | 1,778,335 | 66,439 |
| Execution-evidence evolution | 8B executor | 1,207 | 8,293,891 | 3,196,466 |
| Strict-policy control | Teacher | 16 | 1,776,813 | 67,501 |
| Strict-policy control | 8B executor | 1,206 | 8,172,956 | 3,466,541 |
| Teacher-execution-withheld control | Teacher | 16 | 904,633 | 46,046 |
| Teacher-execution-withheld control | 8B executor | 974 | 6,587,209 | 2,416,560 |
| ACE adaptation | Teacher | 423 | 11,526,040 | 405,699 |
| ACE adaptation | 8B executor | 896 | 7,122,372 | 2,258,447 |
| Trace2Skill–Text | Teacher | 321 | 6,429,967 | 503,252 |
| Trace2Skill–Text | 8B executor | 512 | 4,061,370 | 1,463,066 |
| SkillCommit paper adaptation | Teacher | 930 | 19,696,279 | 548,224 |
| SkillCommit paper adaptation | 8B executor | 2,015 | 13,663,563 | 5,542,122 |

ACE's operational continuations additionally retired 19 successful teacher responses, containing 458,657 input and 21,354 output tokens, and 15 executor generations, containing 135,867 input and 45,681 output tokens. These are preserved separately from the retained-stream totals. Failed-request usage that was not reported remains unknown rather than zero.

Four SkillCommit implementation attempts retired before TEST separately account for 368 successful teacher responses (7,640,289 input and 234,308 output tokens) and 584 executor generations (3,893,280 input and 1,620,559 output tokens). Their outputs and memories were not imported into the retained build. Its 930 successful teacher responses came from 931 recorded attempts, with unreported failed-request usage remaining unknown. Its 345 exact-request reuses do not add physical generations. Frozen-test inference is outside the learning totals in Table D3.

<!-- SkillCommit build-cost evidence: runs/legal_openexempt_skillcommit_paper_public_assets128_seed45_20261102_run05/publications/final.json, SHA256 090af0de02fd5ba84bd053683411ea930b7fa8c9906613ccb8f5aac518b9cc89; completed-build audit run05_eighth_complete_batch_and_build_evidence_20261104.json. Retired-attempt costs are retained in the frozen run05 configuration; these are implementation attempts, not independent learning repeats. -->

<!-- Formation-cost evidence: Utility_v6_main_ACE_Text_exact_used_and_ACE_retired_success_teacher_native_tokens_not_total_cost_20261030.json, SHA256 f971c116e070104b229879d40316325e57d33996ab904bcae34b7709e4e40a34. Counts do not claim equal formation budgets, independent learning repeats or total historical project cost. -->

<!-- Control costs: original completed strict and teacher-evidence runs, with all 16 actual response usage records summed for each; complete-eight proofs 6f562a601cd0d150b010605563f9e3bb34a103af0a0a10d28b37a22b46e97496 and 6714d193055a8b8b6c43c9338db1fbe1d04e96420ff338c30c87694a12a8b266. Cached input and reasoning output remain subsets. -->

### D.4. Completed frozen-evaluation cost

The ten-condition frozen comparison uses 2,560 physical generations and no prior-stage answers or exact-request aliases. Total executor input/output is 19,242,658/6,841,407 tokens; teacher calls are zero. The original completion occurs after 19 h 50 min 03 s of wall time. This covers all conditions jointly and is not an estimate of active GPU hours or a main-method-only inference cost. The original 2,530 stop and 30 length outcomes are retained. All forecasts precede unified target access and scoring.

The separate SkillCommit frozen evaluation uses 256 fresh physical generations, 2,001,690 input tokens and 712,116 output tokens, with zero teacher calls. Its 249 stop and seven length outcomes are all included. These inference totals are separate from its completed learning cost in Table D3.

**Table D4. Actual executor token use in frozen evaluation.** Each condition contains the same 256 EC/EV tasks. Token counts include length-limited outputs.

| Condition | Input tokens | Output tokens | Length-limited outputs |
|---|---:|---:|---:|
| Empty library | 1,622,317 | 711,638 | 1 |
| Law-only static | 1,838,793 | 627,485 | 3 |
| ACE, native interface | 2,267,693 | 694,380 | 10 |
| ACE, common interface | 2,200,621 | 653,265 | 2 |
| Trace2Skill–Text | 2,438,957 | 661,951 | 6 |
| SkillCommit paper adaptation | 2,001,690 | 712,116 | 7 |
| Evidence-guided evolution | 1,809,329 | 627,240 | 2 |
| Own frozen B1 | 1,752,541 | 785,144 | 2 |
| Strict-policy control | 1,767,439 | 723,505 | 3 |
| Execution evidence withheld | 1,766,569 | 621,900 | 0 |
| Predecessor library | 1,778,399 | 734,899 | 1 |

Across these same tasks, the evolved library uses 17.78% fewer input tokens and 3.98% fewer output tokens than ACE under the common interface, and 9.61% fewer input tokens and 11.92% fewer output tokens than the SkillCommit adaptation. Relative to the empty library, its input use increases by 11.53% and output use decreases by 11.86%. Input and output counts describe distinct executor resources; library construction is accounted for separately.

<!-- Frozen-inference cost evidence: paper/tables/utility_frozen_inference_cost_20261102.json; all 2560 unchanged raw response envelopes included. Source scored_records SHA256 ff72aa2ba7c27d1d2725c938729a278c4a68e28068871d5da09aa827ddaa9cf6. No new predictions or scoring calls. -->

### D.5. Learning-path evidence for the mechanism controls

**Table D5. Chronological first answers on the same 112 post-B1 sources (%).** These are learning-stream forecasts, not confirmation scores or post-label replay.

| Learning condition | EC native F1 | EV native F1 | EC complete-output F1 | EV complete-output F1 |
|---|---:|---:|---:|---:|
| Evidence-guided evolution | 91.83 | 88.16 | 94.42 | 87.41 |
| Strict policy | 76.31 | 83.49 | 78.70 | 83.04 |
| Execution evidence withheld | 84.54 | 81.27 | 87.15 | 80.36 |

The strict-policy B1 library has no EV projection, so its later EV gain relative to that snapshot also includes first acquisition; it is not a matched post-acquisition effect. The following fixed-candidate readout explains where the decision contracts differ without pretending to regenerate an alternative learning path.

The evidence-withheld condition keeps released targets and public solved material. Its fixed-B1 native EC/EV F1 is 84.54/81.91%, and its complete-output continuation changes are 0.00/-0.72 points, compared with +10.27/+3.44 for the main method. Hiding explicit teacher-visible execution evidence does not remove controller feedback or establish that labels alone cannot produce useful skills.

<!-- Original full controls and strict fixed-output gate audit:6f562a601cd0d150b010605563f9e3bb34a103af0a0a10d28b37a22b46e97496;6714d193055a8b8b6c43c9338db1fbe1d04e96420ff338c30c87694a12a8b266;68f9517211db9cf6bef124437bb7a33afaddc56c30f1673fcb6a51dc684590a9. Original v0.23 and inspected earlier TEST remain separate and unchanged. -->

### D.6. Applying both policies to recorded candidate pools

We apply both frozen decision functions to each of the 16 saved parent/proposal pools from the main and strict builds, constructing only the corresponding unique component union and verifying request identity before response reuse. The actual-policy readout reproduces all 32 recorded selections. It introduces no model, teacher or embedding call and changes no original output. For the main build, both policies select the same bank at every step: eight whole commits, one component-union commit and seven retained parents. Thus, its nine commits cannot themselves be credited to relaxing strict vetoes.

Two strict-build pools produce different decisions (Table D6). The first is its B1 EV proposal: improved native and complete-output means coexist with one additional negative/unscored-asset claim, so the strict count veto rejects a proposal admitted by utility. At B6 EC, historical losses fall within the utility bound and all-seen quality improves, while the strict prior-nonregression condition rejects it. The teacher-facing policy instructions also differ from the first request; the completed banks already diverge after B1 EC. These records establish specific contract differences, not the downstream performance of hypothetical builds that accepted the rejected proposals.

**Table D6. Same-parent, same-proposal policy disagreements in the strict build.** Values are percentages; arrows denote parent to whole proposal. Utility selects the whole proposal in both pools; strict retains the parent. All sources are encountered TRAIN cases.

| Recorded proposal | Current native F1 | Current complete-output F1 | Binding strict veto |
|---|---:|---:|---|
| B1 EV, 16 current sources | 62.06 → 77.39 | 63.37 → 75.34 | Negative/unscored-asset claims 1 → 2 |
| B6 EC, 16 current + 80 prior | 73.98 → 79.85 | 79.25 → 83.60 | Prior native −0.85 pp; prior complete-output −0.42 pp |

At B6, all-seen complete-output EC F1 improves by 0.38 points; both prior losses are smaller than the utility policy's one-point allowance. The fixed-output readout is descriptive policy evidence, distinct from the final-library control comparison in Table 1.

## Appendix E. Recovering an independent legal alternative

We illustrate procedure evolution on source-isolated frozen-evaluation case 3000055. The supplied prerequisites allow Federal and Wisconsin exemptions. The assets are a necklace worth $890, bath towels worth $175 and a physician-authorized prosthetic arm worth $8,300. For the arm, the benchmark references contain three independent alternatives: 11 U.S.C. § 522(d)(9), 11 U.S.C. § 522(d)(5) and Wis. Stat. § 815.18(3)(d). Each EV alternative protects $8,300 under the supplied task materials; these are alternative claims rather than additive payments.

**Recorded skill evolution.** The B1 Federal EC instruction already states that the wildcard applies independently alongside specific provisions. B2 adds a separate final wildcard check, and B3 expresses the procedure as two mandatory passes with a per-asset completeness audit. The Wisconsin EV block is first published at B7 and revised at B8. The saved final-library EV request contains the Federal, cross-jurisdiction scan and Wisconsin EV projections; the B1 request contains the first two but no Wisconsin EV projection. These revisions were published before the frozen evaluation.

The following are verbatim excerpts from the same Federal EC record, `EC:federal-wildcard-and-category-eligibility`:

**B1, existing legal requirement:** “Apply 11 U.S.C. § 522(d)(5) independently to any property, and retain it alongside every applicable specific paragraph.”

**B2, explicit sequencing:** “Then perform a separate final check for § 522(d)(5) on every asset: it applies to any property, including real property and property already matching a specific paragraph.” B2 also expands the preceding category list, so this transition combines coverage and procedural refinement.

**B3, same listed provisions with an audit:** “Use two mandatory passes for each asset.” The closing instruction becomes: “Second add § 522(d)(5) to every asset without exception, including property already matching a specific paragraph. Before emitting, verify that each asset has (d)(5) and every factually matching specific paragraph.”

**B6, illustration-only refinement retained at B8:** “Hypothetically, personal wearing apparel receives both (d)(3) and (d)(5) even when its value exceeds the (d)(3) ceiling; do not drop (d)(3).” This replaces the earlier animal illustration while preserving the preceding legal procedure byte for byte. The full before/after records and diagnosed edits are in Supplementary Data 1.

**Table E1. Native F1 for the complete illustrative case (%).** All entries are original saved predictions under the common executor profile.

| Frozen condition | EC F1 | EV F1 |
|---|---:|---:|
| Empty library | 80.00 | 44.44 |
| Own frozen B1 | 93.33 | 83.33 |
| Execution evidence withheld | 80.00 | 93.33 |
| Final evolved library | 100.00 | 100.00 |

**Key observations.** The B1 EC answer omits the wildcard for the prosthetic arm despite the general instruction already being present. Its EV answer reports the prescribed-health-aid provision alone, omitting both the wildcard and Wisconsin alternative. The final library's recorded outputs recover all three alternatives and their amounts. The empty-library EV answer additionally assigns unrelated account, business-property and vehicle provisions to the arm, illustrating why recall alone is insufficient. Across the three assets, the final EC and EV outputs each recover all nine reference claims without extras. The EC example demonstrates recovery of an already stated alternative; the added Wisconsin EV projection changes available coverage. The case links actual delivery to outputs, not an isolated edit's causal effect; all-source comparisons quantify aggregate library utility.

## Supplementary data and reproducibility

Supplementary Data 1 provides the complete B1/B8 banks and edit lineage, executor/teacher request definitions, frozen configurations and source manifests, the pinned scorer, original scored predictions, case-level analysis tables and scripts for reproducing scores and paired intervals. The original result files remain unchanged; the added policy, error and bootstrap-sensitivity readouts are separate derived analyses. The package requires no new model or teacher calls for its offline checks. Model inference and independent relearning are separate procedures with their recorded budgets.

<!-- Illustrative case evidence: paper/tables/utility_frozen_case_study_20261102.json. Source key 585875d80b135e3feaf5504a5af7e9acd4891d4e6bdaafc79097e0848a5da949 is absent from TRAIN. Posthoc illustration selected by the documented smallest-ID criterion, not a new endpoint or a per-edit causal intervention. No regenerated predictions or rescoring. -->

