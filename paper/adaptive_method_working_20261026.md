# Evidence-adaptive commitment for legal skill evolution

Methods working draft, updated 27 October 2026. The second formal 128-source
learning stream and its fixed-benchmark supplement are complete. This file
describes that frozen implementation, training evidence and final-library
results; matched-policy evidence remains pending. The original v0.23 manuscript
remains unchanged. The running third formal study is a separate revision, not
an additional result or independent repeat of the method described here.

Implementation binding: scientific source `acf383255301aa15ea575b3172ad280d9777d2f4`,
[frozen run configuration](../configs/openexempt_adaptive_legal_public_assets128_20261026_run01.json)
and its 380-file source manifest. This working draft is outside those live bindings.

中文主线：让同一份法律技能修订的提交粒度服从已观察到的执行证据，在完整提案与依赖
分量组合之间选择，并把尚未解决的问题连同真实父库回答交回教师。研究的是法律规则
适用中的技能学习，不增加律师模型之外的数值求解器或新的客户路由任务。

## 1. Legal tasks and the external learning state

We study how a frozen language model accumulates reusable procedures for legal
rule application. Each source case supplies facts, statutory text and the
benchmark's already established allowable-law result. Exemption classification
(EC) asks for the applicable provisions for each asset. Exemption valuation (EV)
also asks for the amount protected by each applicable provision. The benchmark
scores alternative asset–provision claims independently; the task is not a
joint optimization of allocations across an estate.

A source has both EC and EV views. We denote the incoming source batch by
\(B_b\) and the previously encountered sources by \(H_{b-1}\). The frozen
executor \(f_\theta\) receives a library \(L\) as procedural text. Learning
changes \(L\), while \(\theta\) and the answer interface remain fixed.

The library stores procedures with an applicability condition, an action or
calculation rule, and an exclusion condition. Records identify their legal
namespace and supported task views. The public allowable-law result determines
which namespaces are visible, and task projection supplies the relevant guidance.
This projection does not infer jurisdiction, predict asset eligibility or choose
an answer. Every comparison condition receives the same public asset references,
readable citation vocabulary, legal facts and statutory text.

The executor directly returns asset-specific citations and, for EV, numerical
claims. The interface decodes reference identifiers through fixed public maps.
It does not execute a skill's numerical program, repair a returned answer or
replace a failed answer with another solver. The evaluated skill records contain
procedural text rather than executable operators.

## 2. Batchwise evidence and teacher revisions

**First-encounter predictions.** Before releasing a batch's targets, the learner
saves all predictions under its current library. The same sources also receive
an empty-library answer. From the second batch onward, they receive an
evaluation-only answer under the learner's own library frozen after the first
batch. Exact duplicate requests share their original response. This control never supplies an additional
answer for teacher feedback or candidate admission.

**Released training evidence.** Once every current prediction has been saved,
the native evaluator provides training feedback. The teacher receives current
facts, original targets, actual parent-library answers and their verifier scores.
For each selected source it also carries the saved strong-empty answer and
score; the own-B1 comparison remains evaluation-only. Its evidence packet also
includes a bounded selection of historical sources.
Historical selection prioritizes declared feedback witnesses, public legal
contexts, observed harms and parent failures. The teacher's communication subset
does not restrict the sources used for replay: candidate assessment covers every
source encountered so far.

**Witness-complete refinement.** A rejected or partially committed proposal
contributes bounded concrete witnesses to the next teacher request. Every source
named in those witnesses must appear in the evidence packet with its original
facts and targets. The historical budget expands when needed to retain that
mandatory union. Each witness preserves the proposed answer and its observed
score, while the parent-answer field reflects the library that is actually
active after any partial commitment. Thus refinement addresses the remaining
candidate–parent discrepancy rather than a hypothetical unpublished parent.

**Bounded updates.** The teacher proposes edits to the active library. Each
proposal is assessed before it changes the active state. An accepted subset
becomes the next refinement's actual parent; a later rejected proposal cannot
undo it. Refinement stops when the proposal is fully represented in the accepted
task projections, when the teacher makes no change, or when the declared attempt
budget is exhausted. A fully admitted proposal does not require another teacher
call. Each new batch imports unresolved proposals from the immediately preceding
publication, rather than an unbounded rejection history. One final batch
publication records the resulting bank before subsequent sources are answered.

## 3. Legal dependency components and admissible libraries

**Public dependency structure.** Edits can alter guidance that appears together
in an executor request. For each task view, we construct a graph over legal
namespaces visible in the encountered sources. Co-visible namespaces are
connected. A changed record that moves between namespaces connects its old and
new locations, and changed shared guidance connects all affected namespaces.
Connected components define the units that can be admitted together. Their
number depends on the public cases and proposed edits, rather than a predefined
number of skill types.

**Candidate construction.** Starting from the same active parent \(L\), a teacher
proposal produces a complete proposed library \(J\). Component admission retains
proposed guidance in accepted dependency components and parent guidance elsewhere,
forming a single library \(C\). The composition is a library update, not a
case-specific choice between answers. Skill identities are checked when records
move or their task-specific guidance is joined.

**Complete replay and retention.** The frozen executor replays \(J\) on all
\(H_b=H_{b-1}\cup B_b\) sources. Complete-library retention checks compare current
and historical cohorts separately. Neither task's native F1 or complete-output
F1 may decrease beyond floating-point round-off, and invalid-format and negative/unscored-asset claim counts may
not increase. At least one current-task metric or audited count must improve.
These checks concern cohort aggregates; per-source help, harm and ties are also
retained. The component proposal must pass its local checks and the same
complete-library retention checks after composition.

**Exact-request reuse.** A composed library is assessed through its complete
rendered requests. Each request must match a complete request already observed
in this learner's cache, including the messages, response schema and generation configuration.
Otherwise that composition is rejected. The verified match reuses the original
response, decoded and scored under the same interface and native grader; it
neither substitutes a different answer nor generates a new sample for a selected
source. This makes component assessment possible without additional executor
generations for composition.

## 4. Evidence-adaptive commitment

The commitment unit is selected from the admissible libraries produced by that
revision. Let \(\mathcal F(L,J,C)\) contain the complete proposal and the composed
proposal that pass their respective checks. For an admissible \(A\), define its
paired native-F1 gain on task \(t\) using all encountered sources:

\[
\Delta_t(A;L)=
\frac{1}{|H_b|}\sum_{i\in H_b}
\bigl[s_t(f_\theta(x_{i,t};A),y_{i,t})
-s_t(f_\theta(x_{i,t};L),y_{i,t})\bigr].
\tag{1}
\]

Here \(x_{i,t}\) and \(y_{i,t}\) are the task input and released training target
for source \(i\), and \(s_t\) is its native F1 score. Each source has equal weight
within a task. Both task gains are measured against the same actual parent.

The controller chooses the admissible library with the largest weaker-task gain,
using the mean gain to break ties:

\[
Q(A;L)=\left(
\min_{t\in\{EC,EV\}}\Delta_t(A;L),\quad
\frac{\Delta_{EC}(A;L)+\Delta_{EV}(A;L)}{2}
\right),\qquad
A^*\in\underset{A\in\mathcal F(L,J,C)}{\arg\max}_{\rm lex}Q(A;L).
\tag{2}
\]

An exact tie selects the complete proposal. When neither proposal is admissible,
the parent remains active. Equation (2) permits a useful single-task improvement
when the other task is unchanged; it does not force both scores to rise on every
update. All retention checks remain authoritative, including checks not used in
the ranking objective.

The selection reuses the existing replay outcomes. It adds no executor generation
beyond the proposal assessment and verified composition. Within that evaluated
feasible set, its weaker-task gain is at least that of either feasible fixed
choice, with mean gain resolving equal weaker-task gains. This is a finite-choice
training property; downstream utility is evaluated using subsequent sources and
the frozen-library comparisons.

## 5. Execution and empirical questions

The revised stream starts from an empty library and contains 128 sources in eight
batches of 16, each with EC and EV views. Qwen3-8B remains frozen throughout.
The authorized gpt-5.6-sol teacher uses released TRAIN evidence with high reasoning effort. There are at most
two proposals per batch and a 4096-token complete-library limit. No validation
split is introduced; replay and teacher feedback use encountered TRAIN sources. The captured
single-model service handles four independent native requests; teacher requests
remain sequential. The full configuration fixes model revision, prompts,
context/output limits, decoding and the input packet.

The experiments separate three questions. First-encounter predictions measure
whether accumulated procedures help the next sources. Comparing with the same
learner's fixed first-batch library measures continued learning beyond the
initial prior. Frozen final-library evaluation compares the revised method
with the retained empty, static and external experience-learning conditions.
Matched fixed-whole and fixed-dependency learning controls isolate the value of
adaptive commitment under the same revised feedback and execution conditions.

The two task views share source cases, so source-paired analysis keeps them
together. The revised fixed-benchmark supplement retains the original128 TEST
sources and six completed comparison conditions, adding the revised final bank
and its own first-batch snapshot. It is a development-informed supplement; the
original benchmark outcomes had been inspected, while its questions, targets and
predictions remain outside teaching. Independent learning repeats are deferred
and are not represented by source bootstrap intervals.

## Research notes and claim ledger — not manuscript prose

The central candidate contribution is selection of the **commitment unit within
a legal-library revision** using observed multi-task utility. The public
dependency structure defines composable choices; the complete replay and
witness-complete teacher packet support a coherent update loop. Frozen models,
textual skills, labeled training feedback and replay individually are established
tools, not separate novelty claims.

Closest verified references for the eventual related-work revision are
[Agentic Context Engineering: Evolving Contexts for Self-Improving Language Models](https://arxiv.org/abs/2510.04618v3),
[Trace2Skill: Distill Trajectory-Local Lessons into Transferable Agent Skills](https://arxiv.org/abs/2603.25158v5),
and [SkillCommit: Evolving Agent Skills through Behaviorally Validated Scope Expansion](https://arxiv.org/html/2608.15165v2).
Their verified mechanisms are summarized in the
[contribution assessment](../docs/research/OPENEXEMPT_ADAPTIVE_PAPER_READINESS_AND_MINIMAL_ABLATIONS_20261026.md).
This draft uses those existing nearest-neighbour materials rather than opening
another broad literature survey. It introduces no new bibliography metadata.

### Completed training evidence

The completed run contains all 128 sources and eight final batch publications.
Of 15 teacher proposals, one was committed as a complete proposal and five as
dependency-component compositions; seven were rejected and two were explicit
no-ops. These counts describe actual decisions, not the number of available
branches in the controller. The final library contains nine records and costs
2,426 executor-tokenizer tokens. It is the unique B8 terminal state, identical
to B7 after both B8 proposals were rejected.

The following native-F1 values are first-encounter predictions on each batch's
16 sources, before targets or that batch's revisions are supplied. The last
column instead records the library published **after** the batch. All values
are percentages; EC/EV share the same sources.

| Batch | Evolving library EC/EV | Own B1 control EC/EV | Empty EC/EV | Published records/tokens |
|---|---|---|---|---|
| B1 | 59.31/63.86 | 59.31/63.86 | 59.31/63.86 | 5/1,551 |
| B2 | 86.75/75.22 | 86.75/75.22 | 63.53/61.67 | 7/2,020 |
| B3 | 91.40/86.98 | 91.29/80.44 | 65.01/67.01 | 8/2,224 |
| B4 | 86.68/70.60 | 82.38/78.69 | 60.54/53.56 | 8/2,224 |
| B5 | 90.22/72.82 | 86.02/75.24 | 66.67/53.54 | 8/2,231 |
| B6 | 90.16/90.04 | 89.24/73.75 | 68.82/65.03 | 8/2,231 |
| B7 | 87.49/75.00 | 90.28/71.41 | 61.49/49.51 | 9/2,426 |
| B8 | 93.26/83.63 | 89.39/77.36 | 65.47/52.44 | 9/2,426 |
| All 128 sources | 85.66/77.27 | 84.33/74.50 | 63.86/58.33 | — |

At B1 no learned library exists: the control column uses the same empty
prediction, not a retrospective answer with the completed B1 library. Thereafter
the own-B1 control is explicitly `frozen_after_B1`, snapshot
`509fcf9408a5c92719df6a799693487db3bd8ff00fb3178e79a88b9665b87860`.
B2 uses this same library in both conditions. Over B3–B8, the 96 sources that
can reflect post-B1 revisions, evolving-library EC/EV averages are 89.87/79.85%
against 88.10/76.15% for own B1: paired mean gains of 1.77/3.70 percentage
points. The complete eight-batch table retains the task-specific regressions;
these observed means are not frozen-TEST results or independent-learning
stability estimates.

The stream includes content revision at unchanged library size: B5 revises the
Illinois wildcard procedure. No published transition removes a record, so this
run is not evidence for successful skill deletion or merging. Final learned
library SHA-256 is
`6bab10640bdea4c7728ea25f4866f12f558d2b44156442fe981fd8160b6e0b99`.

Measured TRAIN cost is 1,501 real executor generations and 15 successful teacher
responses in 15 transport attempts. Executor usage is 10,065,456 input plus
4,173,988 output tokens, totaling 14,239,444. Exact-request reuse is not counted
as an additional generation. These totals exclude historical studies, the
completed frozen supplement and the unexecuted matched controls. Source evidence:
[terminal completion](../runs/legal_openexempt_adaptive_legal_public_assets128_20261026_run01/completion.json),
[all-eight first-forecast comparison](../artifacts/research/openexempt_legal_scope_20261020/Adaptive45_complete8_firsts_same128_old_new_EC8203_8566_EV7916_7727_not_final_TEST_20261027.json),
and the eight immutable batch publications in the same run.

### Completed fixed-benchmark supplement — second formal run

The unique final library achieves 92.47% EC and 80.59% EV native F1 on the
retained 128-source benchmark. Relative to its own B1 snapshot, continued
learning adds 2.86 EC and 5.18 EV points. Under the predeclared ten-primary-
comparison adjustment, the paired-source intervals are [-0.25, 5.78] and
[0.93, 9.64], respectively: this realized bank provides positive valuation
evidence beyond B1, while the classification contrast remains unresolved.

The supplement completed at 00:24:45 UTC on 27 October. All conditions use
the same 128 sources per task; values below are equal-source native F1, not
classification accuracy or independent-learning averages. The original
benchmark had already been inspected before this revision, so this is a
development-informed fixed-benchmark comparison, not an untouched confirmation
test. No benchmark questions, targets or predictions entered teaching or
TRAIN admission.

| Frozen condition | EC F1 (%) | EV F1 (%) | Invalid EC / EV |
|---|---:|---:|---:|
| Strong direct empty | 64.08 | 61.88 | 0 / 0 |
| Blind static legal library | 64.20 | 60.81 | 2 / 0 |
| Second-run adaptive final library | 92.47 | 80.59 | 0 / 0 |
| Second-run own B1 snapshot | 89.61 | 75.41 | 0 / 0 |
| ACE task adaptation | 67.66 | 57.97 | 4 / 8 |
| Trace2Skill text-only adaptation | 57.92 | 52.03 | 5 / 11 |
| Historical whole-bank control | 93.03 | 81.32 | 0 / 1 |
| Historical task-local control | 93.25 | 83.35 | 0 / 0 |

The six retained comparison conditions preserve their original predictions and
scores exactly. Whole-bank and task-local are historical controls, not
single-factor ablations of the revised teacher-evidence contract. Their four
adjusted paired intervals contain zero; these data establish neither adaptive
superiority nor equivalence. Matched-policy evidence is still required for the
commitment-unit contribution.

As a separate historical reference, the first formal method retained in v0.23
achieves 87.43% EC and 86.18% EV on the same benchmark. The second run changes
these point estimates by +5.04 and -5.59 points. The equal-task descriptive
mean is 86.80% for the first and 86.53% for the second; it is not a newly
selected primary endpoint. This trade-off does not establish an overall
improvement over the first method, and is not a single-factor estimate of the
adaptive selector.

The second library's complete-output EC/EV F1 is 92.99/80.54%, with no invalid
final-library outputs. Source-paired resampling uses 20,000 draws and seed
2026102192, conditional on the actual frozen banks and decoding. Independent
main/ACE/Text learning repeats remain user-deferred; these intervals do not
estimate between-learning-run variation.

Evaluation required 440 new executor generations, 1,608 exact-request reuse
events and no teacher calls, yielding all 2,048 logical task predictions.
Fresh evaluation usage is 2,950,405 input plus 1,240,823 output tokens,
totaling 4,191,228. Reuses are not independent generations or learning repeats.
The executed comparison and all adverse outcomes are retained in the
[supplement completion](../runs/legal_openexempt_adaptive_supplement_TEST128_20261027_run01/completion.json)
and its
[complete result audit](../artifacts/research/openexempt_legal_scope_20261020/Adaptive45_complete_frozen_TEST128_EC9247_EV8059_ownB18961_7541_not_above_historical_controls_20261027.json).
The original v0.23 main table and PDF have not been overwritten.

### Claim ledger

| Claim | State | Direct evidence / remaining requirement |
|---|---|---|
| Actor, scopes, dependency composition and selection describe the executed rule | VERIFIED | Frozen source/config and implementation map below |
| Actual proposal-to-parent feedback is connected | VERIFIED for the observed B2 refinement | Original64 parent answers/targets and8 witness records in the B2 feedback audit |
| Both commitment modes have been used | VERIFIED for the complete stream | One joint and five component commitments among 15 teacher proposals |
| Observed subsequent-source mean gain over own B1 | VERIFIED as a within-stream observation | B3–B8, 96 sources: EC +1.77pp and EV +3.70pp; individual batches retain regressions |
| Revised final-bank fixed-benchmark performance | COMPLETED | Unique B8: EC92.47%/EV80.59%; own-B1 gains2.86/5.18pp with adjusted intervals[-0.25,5.78]/[0.93,9.64] |
| Adaptive selection improves the end-to-end fixed-policy alternatives | PENDING | Matched fixed-whole/fixed-dependency learning and evaluation |
| Uniform dominance, new untouched-test validation or independent-run stability | UNSUPPORTED by current evidence | Not stated as a result in this draft |

### Implementation map

| Methods object | Frozen implementation |
|---|---|
| Public allowable namespaces and reference decoding | `legal_skill_guard/learning/legal_namespace.py`: `allowable_namespaces`, `public_catalog`, `public_asset_catalog` |
| Task-local text and dependency components | `legal_skill_guard/learning/task_scoped_skills.py`: `task_view`, `legal_edit_coordinates`, `compose_legal_edits` |
| Shared direct actor | `experiments/openexempt_online.py`: `actor_payload`, `Online.answer` |
| Current/prior retention | `acceptance`, `_head_admission`, `legal_scope_admission` |
| Balanced finite-choice criterion | `balanced_replay_gain`, `Online.update` |
| Actual-parent and mandatory-witness feedback | `candidate_feedback`, `teacher_evidence_rows`, `Online.teacher_body`, `Online.update` |
| Prediction-before-label release and own-B1 control | `Online.execute` |

Authoring sources: the brother's methods skill supplies purpose-to-mechanism
organization; Anti-Defensive supplies the single contribution thread; Nature
guidance keeps implementation claims distinct from incomplete results. The
learner and its prompts do not load these authoring skills.
