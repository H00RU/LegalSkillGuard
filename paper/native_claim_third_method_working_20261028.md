# Native-claim feedback for legal skill evolution

Third-build method and completed-stream working draft, 28 October 2026.
This file describes the actual third formal build, not the fourth build's
accepted-outcome feedback revision. It leaves the v0.23 manuscript unchanged.
The fixed final-library version supplement is complete; the source-disjoint
primary comparison and matched learning controls remain pending.

## 1. Legal task and learned state

We study whether a frozen executor can turn successive legal execution
experiences into procedures that improve its work on later source cases.
OpenExempt supplies exemption classification (EC) and exemption valuation (EV).
Given facts, public statutes and the allowable-law result, EC identifies every
applicable asset–provision alternative. EV additionally reports the protected
amount for each alternative. These independent-pair tasks do not ask the model
to jointly allocate an estate-wide exemption budget. EC and EV are two views
of each source, not two independent datasets.

The learning state is an external textual skill library. Each record declares
its public legal namespace, supported tasks, applicability conditions, procedure
and exclusions. The executor's model weights remain unchanged. Projection uses
the given allowable namespaces and task identity; it does not decide whether
an asset qualifies. The model performs classification and valuation directly.
Skills contain no executable numerical operators or hidden answer solver.

The common response interface uses public citation and literal asset references.
References identify strings, not ownership, applicability or correct amounts.
Decoding restores those strings without adding claims or correcting values.
EC skills precede the case material. EV skills follow the complete case
material, without the obsolete case-follows connector. The supplied facts and
statutes remain authoritative.

## 2. Claim-aligned learning and adaptive commitment

The learner starts with an empty library and processes 128 fixed TRAIN sources
in eight batches of 16. It saves every current-library forecast before releasing
that batch's original targets. The teacher receives selected original TRAIN
facts and complete targets, actual parent and empty-library answers, the public
statutes and the executor's actual system/schema contract. Claim-level feedback
distinguishes omissions, incorrect values and extra or duplicate claims using
the pinned native asset and claim matching. This is label-assisted skill
learning, not weight training or an unlabeled group-policy optimization run.

The teacher creates, revises, merges or removes textual records. A bounded
historical subset limits communication, not assessment: every proposal is
replayed on all encountered sources. The full library is capped at 4,096
executor-tokenizer tokens and each batch permits at most two proposals.
Lossless system/schema references remove duplicate prompt material. Saved
model-emitted process excerpts are bounded; full raw requests and responses
remain available in the run artifacts.

The third build uses `native_claim_aligned_compact_v1`. Rejected or partially
committed proposals can supply up to eight replay witnesses, ranked by their
actual-parent score difference and remaining failure. The pool can include
unchanged-request failures. A partial commitment becomes the next actual
parent; a later rejection does not erase it. A full commitment ends that
batch's refinement and does not carry the fourth build's explicit accepted-
regression packet. These details distinguish the two executed methods.

Commitment considers a complete proposal and a dependency-aware composition.
Public legal namespaces visible together in a request form connected edit
components; changed shared guidance and namespace-moving edits extend those
connections. The component count is data- and edit-dependent, not preset.
Current and prior TRAIN cohorts are checked separately. Native EC/EV F1 and
complete-output F1 must be retained, while format-error and negative/unscored-
asset claim counts must not increase. An admissible update must also improve
a declared current-cohort score or audited count.

Composed edits retain parent guidance outside accepted components. They are
eligible only when every complete rendered request, response schema and
generation profile matches an already measured response. Composition therefore
publishes one fixed library, not a case-specific selection of favorable answers.
It requires no additional generation for an unmeasured mixed request.

Among admissible complete and composed proposals, the controller ranks the
smaller of the two task-wise paired native-F1 gains first, then their mean gain;
an exact tie selects the complete proposal. Both gains use all encountered
sources and the same actual parent. If neither is admissible, the parent remains.
The gates concern cohort aggregates, not guaranteed non-regression on every case.

## 3. Completed chronological learning evidence

Continued evolution improves later-source forecasts relative to freezing the
learner's own first publication. Across all 128 sources, incoming-library native
EC/EV F1 is 82.38%/84.25%, compared with 79.19%/74.60% for own-B1, giving gains
of 3.19/9.65 percentage points. Of 256 paired task views, 83 improve, 24 worsen
and 149 tie. These are TRAIN first-encounter predictions, not post-label replay
or a final TEST result.

| Batch | Incoming EC / EV F1 (%) | Own-B1 EC / EV F1 (%) | Published records |
|---|---|---|---|
| B1 | 62.90 / 67.97 | 62.90 / 67.97 | 4 |
| B2 | 81.05 / 64.17 | 81.05 / 64.17 | 7 |
| B3 | 87.23 / 89.43 | 83.07 / 82.45 | 7 |
| B4 | 81.24 / 93.77 | 80.95 / 79.73 | 7 |
| B5 | 83.80 / 89.01 | 81.87 / 77.44 | 7 |
| B6 | 86.42 / 91.64 | 84.29 / 79.92 | 8 |
| B7 | 85.24 / 85.52 | 73.74 / 74.53 | 8 |
| B8 | 91.12 / 92.48 | 85.62 / 70.59 | 8 |

Each row contains 16 different new sources. Incoming forecasts precede target
release; the record count describes the publication after learning from that
batch. Both B1 forecasts are cold, and B2 uses the same actual B1 bank in both
conditions. Own-B1 is fixed by the immutable first publication and never enters
teacher or admission feedback. From B3 through B8, both task-wise paired point
differences are positive in each cohort. This does not assert a monotonic
same-case curve or statistical superiority over another learning method.

The controller accepts nine of fourteen proposals: four complete proposals and
five dependency compositions; five proposals publish no update. B7 makes no
accepted update. Record count increases from four to eight but is not the
learning objective. The unique actual B8 bank contains eight records and 2,910
tokens, with SHA256
`3c63a71f1ecd7d1b9d071c4ab39750ac8f0c483c5f3ad8d25c7ee6adca813cf2`.

The [complete-stream own-B1 reconstruction](../artifacts/research/openexempt_legal_scope_20261020/Third_complete8_incoming_vs_ownB1_actual256wires_both_task_gains_B3_B8_not_new_inference_20261028.json)
reproduces all eight rows and aggregate metrics and verifies the 256 actual
own-B1 request renderings. It adds no model or teacher calls. Actual B8 replay
on encountered TRAIN gives native EC/EV F1 of 91.15%/91.28% and complete-output
F1 of 94.33%/90.63%; this fit is distinct from the incoming curve above.

## 4. Evaluation and accounting

All conditions use the frozen Qwen3-8B revision, supplied facts/laws, original
scorer and declared decoding profile. The teacher is the authorized
`gpt-5.6-sol` with high reasoning effort. There is no validation split, external
legal solver, fallback or answer-quality retry. Malformed and length-ended
responses remain in the scoring denominator. The native EC empty-asset
convention is unchanged. Complete-output claim F1 and format/overproduction
counts provide complementary measurement without replacing native F1.

The completed run uses 1,329 physical native calls, with 8,938,274 input and
3,651,780 output tokens. These totals include the declared empty and own-B1
measurement calls as well as learning; they are not a pure training-only
query count. Fourteen fresh teacher responses require fourteen actual attempts,
2,439,708 input tokens and 57,154 output tokens. Reasoning accounts for 38,670
of those output tokens, not an additional output charge; cached input is zero.
No teacher tool events occur. Exact-wire aliases are not independent draws.

Actual consumption separates learning references from exclusive measurement:

| Native-call use | Unique origins | Input tokens | Output tokens |
|---|---|---|---|
| Consumed by learning | 1,179 | 7,954,074 | 3,202,712 |
| Exclusive own-B1 measurement | 150 | 984,200 | 449,068 |
| Actual complete run | 1,329 | 8,938,274 | 3,651,780 |

Learning includes first forecasts, required empty references, candidate assessment
and teacher evidence. Of the 256 own-B1 response origins, 106 are also consumed
by learning; shared origins are charged once, not subtracted as exclusive
measurement. The [origin-level accounting](../artifacts/research/openexempt_legal_scope_20261020/Third_actual1329_native_cost_partition1179_learning150_ownB1_only_exact_origin_closure_20261028.json)
reconciles every call and token with the complete-run totals. This describes
actual consumption, not a counterfactual claim about outputs or scheduling
without measurement.

The completed fixed-version supplement evaluates the actual B8 bank on the
previously inspected 128-source TEST packet. All 256 responses were saved before
grading them, with no teacher calls, updates or checkpoint selection.
Selection of this complete version was bound from full TRAIN evidence before
the fourth version's TEST scores existed. Section 5 reports its eight historical-
control contrasts and source-paired adjusted intervals.

The prospective primary uses the separately sealed, source-disjoint IID128
packet. Necessary same-version whole-bank and dependency-commitment learning
controls, own-B1, strong empty, static and retained experience-learning libraries
follow the [bound study design](../docs/research/OPENEXEMPT_THIRD_FORMAL_MATCHED_POLICIES_AND_IID_EVAL_20261027.md).
The primary matrix and those matched learning results are **PENDING**; the
historical-control supplement does not replace them. Extra independent main,
ACE and text-library learning repeats remain USER-DEFERRED. Source bootstrap
uncertainty is conditional on the actual learned libraries, not a substitute
for repeated learning runs.

## 5. Completed frozen-library version supplement

The third build improves native EV F1 over both historical controls: 87.07%
versus 81.32% and 83.35%. Its native EC point estimate is 92.91%, compared with
93.03% and 93.25%. The result supports a valuation gain against the historical
whole-bank condition, not an advantage on every endpoint or a causal claim
about the commitment policy alone.

| Frozen condition | EC native F1 (%) | EV native F1 (%) | EC complete-output F1 (%) | EV complete-output F1 (%) |
|---|---|---|---|---|
| Third formal build | 92.91 | 87.07 | 93.49 | 87.04 |
| Historical whole-bank control | 93.03 | 81.32 | 93.47 | 81.57 |
| Historical task-local control | 93.25 | 83.35 | 93.82 | 83.34 |

Five of eight directional point differences are positive. Two have positive
eight-endpoint-adjusted bootstrap lower bounds, both for EV against whole-bank.
The native EV difference is +5.75 points (adjusted interval +0.92 to +10.62)
against whole-bank and +3.72 (-1.10 to +8.30) against task-local. Native EC
differences are -0.13 (-3.25 to +3.00) and -0.34 (-3.63 to +3.03), respectively.
Complete-output EV gains are +5.47 (+0.88 to +10.17) and +3.70 (-1.01 to +8.25).
The EC intervals cross zero; they do not establish equivalence or non-inferiority.
The controls retain their historical learning and rendering epochs, so this
supplement does not replace the planned same-version learning controls.

All 256 new responses ended normally. EC and EV each have zero invalid-format
responses; EC has zero negative/unscored-asset claims and EV has one. Inference
used 1,755,740 input and 646,876 output tokens, with zero teacher calls. The
[independent completed-supplement audit](../artifacts/research/openexempt_legal_scope_20261020/Third_observed_TEST_complete256_raw_wires_grade_eight_bootstrap_actual_final_B8_20261028.json)
reconstructs the 256 method and 512 historical request/response decodings and
original scores, all eight seeded-bootstrap contrasts and terminal archive hashes.
The unique final bank remains the eight-record B8 fixed in Section 3; no
intermediate checkpoint or repaired answer replaces it.

## Reproducibility anchors — working record

| Field | Executed artifact |
|---|---|
| Formal build | `legal_openexempt_native_claim_feedback_public_assets128_20261027_run01` |
| Original configuration | [Third formal recipe](../configs/openexempt_native_claim_feedback_public_assets128_20261027_run01.json) |
| Frozen implementation epoch | Original Online SHA256 `3213e92d8e3a3c2c3b4e565dd3553a17ba9b2e425e68e607232749363e8c1985` |
| Teacher evidence | `native_claim_aligned_compact_v1`; not fourth-build v2 |
| Execution | One BF16 A40 Qwen3-8B instance; four native workers and one teacher worker |
| Decoding | Seed45; temperature0.6; top-p0.95; top-k20; thinking on; context32,768; maximum output8,192 |
| Own-B1 | Bank `02c5f64f331afdba709cb037a759c04e9b71c12b9513b720a26d5ffaccb20df6`; fixed after exactly B1 |
| Completed version TEST | `legal_openexempt_third_TRAIN_selected_observed_TEST128_20261028_run01`; frozen388-file renderer binding; 773 terminal archive members |

This working record does not claim method-wide superiority from the completed
historical-control supplement. The source-disjoint primary and same-version
controls remain pending. It neither replaces the preserved v0.23 study nor
relabels a fixed-policy control as the adaptive method.
