# Outcome-grounded legal skill evolution with adaptive commitment

Methods and evaluation working draft, 28 October 2026. This document describes
the fourth formal optimization build. It is separate from the preserved v0.23
manuscript and the second-build working draft. The complete eight-batch stream
has finished, as has its frozen final-library version supplement. The stream
and mechanism case below are TRAIN evidence; Section 6 reports the supplement.

## 1. Task and external learning state

A legal skill revision can correct one rule application while introducing an
error elsewhere. We select the part of a revision to publish from the frozen
executor's measured outcomes and return those outcomes to the skill teacher.
The learning state is a library of reusable procedures, not model weights.

We study OpenExempt exemption classification (EC) and exemption valuation (EV).
For each asset, EC identifies applicable statutory provisions; EV also determines
the amount protected under each provision. These are conditional legal tasks:
the allowable-exemption result supplies the available legal namespaces. The
benchmark evaluates alternative asset–provision claims, rather than a joint
allocation of exemptions across an estate. Each source supplies both task views.

The frozen executor receives facts, statutes, the allowable-law result and a
task-projected textual library. A skill records its legal namespace, supported
tasks, applicability condition, procedure and exclusions. Projection uses the
given legal namespaces and task identity; it does not predict asset eligibility.
Semantic applicability and numerical reasoning remain the executor's work.
The executor directly returns citations and numerical values. The evaluated
library contains no executable claim operators.

All comparison arms use the same public reference interface. Citation references
spell the headers of the supplied laws. Asset references identify maximal literal
mentions from the benchmark's description-only asset lexicon; they do not identify
ownership or eligibility. Fixed decoding restores these strings without filling
claims, correcting amounts or invoking another solver. Learned guidance remains
subordinate to the supplied facts and statutory text.

## 2. Outcome-grounded revisions

Before releasing a batch's training targets, the learner saves every current-library
prediction. Training feedback then combines the original targets, actual answers,
native scores and claim-level errors. The teacher also receives saved same-case
empty-library answers, the public statutes and the actual executor interface.

The evidence packet contains all current sources and a bounded historical
selection. Historical selection includes every source named by the bounded
revision witnesses, then prioritizes public legal contexts, observed harms and
parent failures. It carries the original facts and targets for those sources.
The communication subset does not restrict assessment: each proposal is replayed
on every source encountered so far.

Revision feedback links the proposed outcome to the answer under the library
that is actually active. It prioritizes observed regressions, then unresolved
intended repairs and other changed-request failures. Unchanged background failures
do not fill the witness budget. Accepted revisions also retain observed
pre-/post-commit regressions, so full acceptance does not erase their remaining
errors. A subsequent teacher request may therefore receive evidence about both
unpublished guidance and harm remaining after a published update.

The teacher edits the actual parent through creation, replacement or deletion of
skill records. When a component is accepted, it becomes the next proposal's
parent. A later rejection leaves that accepted state intact. Refinement ends
after full commitment, an explicit no-op or the declared proposal budget. One
final publication fixes the library used on the next batch. Neither library size
nor the number of accepted updates is constrained to increase.

## 3. Dependency-aware commitment

The commitment unit follows which legal guidance can appear together in an
executor request. For each task, co-visible legal namespaces are connected.
Changed shared guidance and namespace-moving edits extend those connections.
The resulting components define jointly assessed edit coordinates; their number
depends on the public inputs and edits, not a preset number of skill categories.

Let \(L\) be the active parent, \(J\) the complete teacher proposal and \(C\) a
composition that retains proposed guidance in accepted components and parent
guidance elsewhere. Current and earlier TRAIN cohorts are checked separately.
For each task, native F1 and complete-output F1 must be retained, and invalid-format
and negative/unscored-asset claim counts must not increase. At least one current
native score, complete-output score or audited count must improve. Component
edits pass local checks and the composed library passes the complete-library
checks. Retention concerns cohort aggregates; individual help, harm and ties are
recorded separately.

A composition is assessed only when every rendered request matches a response
already measured in the learner's cache. Identity includes the complete messages,
response schema and generation profile. Otherwise that composition is rejected.
This produces a single published library, not case-specific selection among
candidate answers, and needs no extra generation for composition.

The controller ranks the admissible complete and composed proposals by paired
native-F1 gains. For encountered sources \(H_b\), task \(t\), and admissible
library \(A\), define

\[
\Delta_t(A;L)=|H_b|^{-1}\sum_{i\in H_b}
\left[s_t(f_\theta(x_{i,t};A),y_{i,t})-
s_t(f_\theta(x_{i,t};L),y_{i,t})\right].
\]

Here \(x_{i,t}\) and \(y_{i,t}\) are the task input and released training target,
and \(s_t\) is the pinned native score. Both gains use the same actual parent.
For feasible \(A\in\{J,C\}\), the ranking is lexicographic:

\[
Q(A;L)=\left(\min_t\Delta_t(A;L),\;
\tfrac12\sum_{t\in\{EC,EV\}}\Delta_t(A;L)\right).
\]

The higher weaker-task gain wins, followed by the mean gain; an exact tie selects
the complete proposal. If neither is admissible, the parent remains active.
This finite-choice rule selects among already measured TRAIN outcomes while
retaining every quality check. Subsequent-source and frozen-library evaluations
measure the utility of the published procedures.

## 4. Evaluation and implementation details

The formal stream contains 128 sources in eight batches of 16, with two task
views per source. Qwen3-8B remains frozen; the authorized gpt-5.6-sol teacher uses
released TRAIN evidence. There is no validation split. The proposal cap is two
per batch and the complete-library budget is 4,096 executor-tokenizer tokens.
The original passive skill-delivery contract and native scoring are unchanged.

The fixed native evaluator supplies benchmark-comparable per-source scores,
which are averaged equally within each task. Its EC convention assigns zero F1
to a correctly empty target/prediction asset, and its target-based aggregation
does not fully measure additional claims. We therefore also report complete-output
claim F1 per source, including claims on negative and otherwise unscored assets,
alongside format and overproduction counts. The native scores remain unchanged.

First-encounter predictions measure usefulness before that batch's target release;
post-update replay measures fit on encountered TRAIN. An evaluation-only own-B1
control isolates continued evolution beyond the first publication. Its B1 entry
is the saved cold forecast; B2 onward uses the first published bank. That bank is
fixed by the immutable B1 publication, while its inference is deferred until after
the main checkpoint. It never supplies teacher or admission feedback.

To remove repeated control inference from the critical path, this build imports
256 uniformly precomputed, exact empty-library raw response origins from the
preceding run. Incomplete outputs are retained too. The knowledge bank starts
empty; no learned library, skill-conditioned response, parsed answer, stored score,
target or teacher response is imported. Only encountered batch records enter
teaching. These shared controls are not new independent draws. New physical calls,
original reference costs and deferred measurements are accounted separately.

The fixed harm stop checks two successive post-B1 batches. It stops learning when
each shows more than two percentage points of mean native-F1 loss relative to a
fixed empty-reference condition, or more than two points of EV complete-output
loss relative to that reference. A cold B1 alone cannot trigger this stop. Parsing
failures and length-ended outputs remain in their declared scoring denominator;
there is no answer-quality retry or alternate solver.

The immediate checkpoint evaluates only the actual completed B8 library on the
original, previously inspected 128-source TEST packet. It is a frozen version
supplement against preserved historical whole-bank and task-local conditions.
EC and EV native/complete-output F1 yield eight directional contrasts. The bound
analysis uses 20,000 source-paired bootstrap resamples with an eight-endpoint
Bonferroni family; numeric wins and adjusted-interval support are reported
separately. This supplement does not select a checkpoint or establish newly
matched learning ablations. If a complete new B8 is unavailable, the sole
prespecified third-build reference is labeled as that earlier version.

A separate source-disjoint prospective evaluation remains the primary evidence
required for the optimized method. Matched learning controls and the retained
empty, static and experience-learning conditions complete that comparison.
Additional independent main/ACE/Text learning repeats remain deferred. Bootstrap
uncertainty over source cases is conditional on the learned artifacts.

## 5. Complete TRAIN stream

The learned library improves the frozen executor's first encounters with new
sources. Across all 128 sources, including cold B1, native EC/EV F1 is
78.91%/80.24%, compared with 63.58%/59.85% for the same-case shared empty control.
Of the 256 paired task views, 130 improve, 15 worsen and 111 tie. These predictions
precede each batch's target release; they are distinct from post-update replay.

| Batch | Empty EC / EV (%) | Incoming-library EC / EV (%) | Accepted proposals | Published skills | Published tokens |
|---|---|---|---|---|---|
| B1 | 62.90 / 67.97 | 62.90 / 67.97 | 1 | 6 | 1,399 |
| B2 | 62.70 / 51.70 | 82.07 / 67.77 | 1 | 6 | 1,613 |
| B3 | 64.85 / 71.30 | 82.56 / 85.17 | 1 | 6 | 2,147 |
| B4 | 60.38 / 67.18 | 77.87 / 87.88 | 1 | 6 | 2,308 |
| B5 | 59.41 / 57.29 | 80.40 / 90.90 | 0 | 6 | 2,308 |
| B6 | 69.35 / 64.93 | 79.58 / 83.25 | 0 | 6 | 2,308 |
| B7 | 59.10 / 51.04 | 82.16 / 74.01 | 1 | 6 | 2,432 |
| B8 | 69.92 / 47.37 | 83.77 / 84.99 | 0 | 6 | 2,432 |

Each row covers 16 new sources and both task views. Scores use the incoming
library; the final columns describe the publication after those targets are
released. Different rows contain different cases. The five admitted proposals
produce five distinct published banks, without requiring skill-count growth.
B7 admits the Arizona EV component: current-source EV rises from 74.01% to
81.23%, and prior-source EV from 85.49% to 86.88%. EC retains its actual parent
answers. Both B8 proposals are rejected, leaving the actual B7 bank as B8.

The completed build uses 801 new native calls, all ending normally, plus the
256 declared shared empty origins; the two incomplete shared origins retain
their original zero scores. Native usage is 5,408,245 input and 2,133,304 output
tokens. Fourteen fresh teacher calls use 2,521,273 input and 48,633 output tokens;
reasoning is included in that output total. The build window is 6.08 hours on
the single A40 service, including teacher and admission time. Deferred own-B1
inference and the completed frozen TEST are not included in these build totals.
The shared empty origins themselves cost 1,621,981 input and 696,201 output
tokens. Counting these necessary learning references gives 1,057 native origins,
7,030,226 input tokens and 2,829,505 output tokens. Reuse shortens this run's
critical path; it is not credited as a reduction in the method's reference-query
requirement.

The [completed-stream audit](../artifacts/research/openexempt_legal_scope_20261020/Fourth_formal_B8_complete512_wires_both_rejected_all8_801native14teachers_actual_bank_TEST_started_20261028.json)
links the complete first-encounter curve, actual publications, original wire and
score checks, native costs and two-disk terminal preservation. The B8 publication
fixes bank `2041200a449eb2b9a6a6700ed52e5018b1d090e29540053e656a76c467a54acb`.

## 6. Completed frozen-library version supplement

The fourth build's fixed final library gives 80.76% native EC F1 and 84.23%
native EV F1 on the previously inspected 128-source packet. Its EV point
estimates exceed both historical controls, whereas the EC estimates are lower.
The supplement therefore does not establish the proposed method-wide advantage.

| Frozen condition | EC native F1 (%) | EV native F1 (%) | EC complete-output F1 (%) | EV complete-output F1 (%) |
|---|---|---|---|---|
| Fourth formal build | 80.76 | 84.23 | 81.86 | 83.82 |
| Historical whole-bank control | 93.03 | 81.32 | 93.47 | 81.57 |
| Historical task-local control | 93.25 | 83.35 | 93.82 | 83.34 |

Four of eight directional point differences are positive, all for EV; none has
a positive eight-endpoint-adjusted bootstrap lower bound. Native EV differences
are +2.92 points against whole-bank (adjusted interval -1.65 to +7.80) and +0.88
against task-local (-3.43 to +5.16). Native EC differences are -12.28 points
(-16.56 to -8.23) and -12.49 (-16.63 to -8.51), respectively. These comparisons
concern preserved historical conditions, not new matched learning ablations.

All 256 new responses were saved before grading. There were no teacher calls,
updates, checkpoint changes or quality retries; all responses ended normally.
Inference used 1,732,089 input and 700,508 output tokens. The
[independent completed-supplement audit](../artifacts/research/openexempt_legal_scope_20261020/Fourth_observed_TEST_complete256_raw_wires_and_eight_bootstrap_verified_not_superior_third_preselected_20261028.json)
reproduces original scoring, all eight contrasts and their intervals from the
actual requests and responses. A separate third-build B8 evaluation, selected
from full TRAIN evidence before these fourth-build TEST scores existed, is not
part of this fourth-build result.

## Reproducibility record — working notes, not Results prose

| Field | Frozen value or artifact |
|---|---|
| Formal build | `legal_openexempt_revision_outcomes_shared_controls_public_assets128_20261028_run02` |
| Executed configuration | [Run02 configuration](../configs/openexempt_revision_outcomes_shared_controls_public_assets128_20261028_run02.json) |
| Source manifest | [900-file binding](../configs/openexempt_revision_outcomes_shared_controls_public_assets128_20261028_run02.frozen.json), SHA256 `4308b6bf21d9ca38db1a53229b2806fb16f0c683de0f46b3d1de99cca05ab793` |
| Online implementation | SHA256 `2e033daf59de7f4f83b07547b138c724edf63dc8303242eed3ee4b6dbbfaa06d` |
| Executor revision | Qwen3-8B `b968826d9c46dd6066d109eabc6255188de91218` |
| Decoding | Seed 45; temperature 0.6; top-p 0.95; top-k 20; thinking enabled; context 32,768; maximum output 8,192 |
| Execution | One BF16 A40 model service; four independent native requests, sequential teacher calls |
| Teacher | `gpt-5.6-sol`, high reasoning effort; actual calls/attempts/tokens recorded |
| Control inference | 256 uniform exact empty raw origins; [bound index](../artifacts/launches/legal_openexempt_deadline12h_learning_and_version_TEST_20261028_run01/shared_empty_control_index.json) |
| Execution protocol | [Full learning/shared measurement](../docs/research/OPENEXEMPT_REVISION_OUTCOMES_SHARED_CONTROLS_FORMAL_20261028.md) |
| Writing structure | Existing [ten-peer writing study](../peer-papers/同行写法研究-v1-20261023.md); no new literature or novelty claim added here |

### Completed mechanism case

In the completed chronological TRAIN diagnostic, the same first proposal failed
both the whole-bank and task-level checks. Its EC dependency component passed
and was published; the second proposal was rejected. On the following 16 TRAIN
sources, the fixed published update changed native EC F1 from 91.12% to 95.81%,
with EV unchanged at 92.48%; complete-output EC changed from 92.33% to 95.96%.
This is a fixed-proposal admission example with actual subsequent predictions,
not a complete newly learned counterfactual control or final TEST result.
The [mechanism artifact](../artifacts/research/openexempt_legal_scope_20261020/Fixed_actual_C1_policy_gate_component_and_forwardTRAIN_mechanism_no_new_experiment_20261028.json)
binds the proposal, gates, actual publication and paired outcomes.

### Claim and result ledger

| Item | State | Authoritative evidence / remaining result |
|---|---|---|
| Frozen executor, textual updates and original task interface | VERIFIED | Frozen configuration and implementation |
| Accepted-revision harm feedback and actual-parent references | VERIFIED | Actual diagnostic teacher requests and completed replay |
| One fixed-proposal component-admission case | VERIFIED | Bound mechanism artifact above |
| Fourth formal complete eight-batch stream | COMPLETE | Eight actual publications; Section 5 and the completed-stream audit |
| Fourth final-library version supplement | COMPLETE | Section 6; 256 new responses, four of eight numeric wins and zero positive adjusted lower bounds |
| Optimized-method prospective primary matrix | PLANNED | `[PENDING ANALYSIS — final binding, matched conditions and source-disjoint frozen-library predictions]` |
| Method-wide superiority and continued-evolution effect | PENDING | Full stream, own-B1 measurement, matched controls and prospective primary matrix |
| Independent main/ACE/Text learning repeats | USER-DEFERRED | Do not replace them with decoding repeats or source bootstrap counts |

The complete TRAIN stream and observed-packet supplement do not replace the
pending source-disjoint primary comparison.
