# Evidence-adaptive commitment for legal skill evolution

Methods working draft, 26 October 2026. This file describes the frozen revised
implementation, not a completed revised-results manuscript. The original v0.23
manuscript remains unchanged. Quantitative claims require the complete learning
stream and the evaluations specified below.

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
Its evidence packet also includes a bounded selection of historical sources.
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
response and score; it neither substitutes a different answer nor generates a
new sample for a selected source. This makes component assessment possible
without additional executor generations for composition.

## 4. Evidence-adaptive commitment

The submission unit is selected from the admissible libraries produced by that
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

| Claim | State | Direct evidence / remaining requirement |
|---|---|---|
| Actor, scopes, dependency composition and selection describe the executed rule | VERIFIED | Frozen source/config and implementation map below |
| Actual proposal-to-parent feedback is connected | VERIFIED for the observed B2 refinement | Original64 parent answers/targets and8 witness records in the B2 feedback audit |
| Both submission modes have been used | VERIFIED for B1–B2 | B1 whole publication; B2 component publications |
| Continued learning improves subsequent-case performance | PENDING | Complete later-batch paired first forecasts versus own B1 |
| Revised final-bank fixed-benchmark performance | PLANNED | Unique B8 and own-B1 freeze, complete supplementary evaluation |
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
