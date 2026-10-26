# Adaptive study: fixed-benchmark supplement protocol

26 October 2026. Prospective protocol for the revised study's supplementary
evaluation. The adaptive learner is currently in B2; no revised TEST prediction
has been requested. This does not modify the live TRAIN bindings or the original
v0.23 study. It implements the user's preference to retain the original TEST
sources and reuse the completed comparators.

## Purpose and timing

Evaluate the unique terminal library from
`legal_openexempt_adaptive_legal_public_assets128_20261026_run01`, and that same
learner's own B1 snapshot, after all eight declared batches finish and the run is
preserved. The terminal bank is not selected from intermediate results. If the
learner fails or stops short of its declared complete stream, do not automatically
launch this evaluation as a completed-method result.

Keep the original 128 source cases, input packet, grading targets, native EC/EV
scoring and full-output audits from
`legal_openexempt_initial8_frozen_TEST_20261025_run01`. Its original completion
SHA256 is `9658e2ea236d6a83aa84d788e452cc563413c93190920d38674157cea50d7154`.
The cases are disjoint from TRAIN. Their previously inspected benchmark outcomes
informed development; this supplement is not described as untouched validation.
Original TEST text, targets and predictions remain excluded from teaching.

## Eight-condition matrix

| Condition | Prediction source | Role |
|---|---|---|
| empty | Original complete strong-empty predictions | Common task interface without skills |
| static | Original complete law-only predictions | Blind static legal prior |
| ACE45 | Original complete ACE task-adaptation predictions | External experience-learning comparator |
| text45 | Original complete Trace2Skill text-adaptation predictions | External experience-learning comparator |
| whole_bank | Original complete whole-bank control predictions | Historical fixed-policy comparator |
| task_local | Original complete EC/EV-local control predictions | Historical fixed-policy comparator |
| adaptive45 | New inference using the revised learner's final B8 bank | Revised main method |
| adaptive_own_B1_45 | New inference using the revised learner's exact B1 bank | Further learning beyond the initial library |

There are 128 sources × 2 task views × 8 conditions = 2048 logical predictions.
1536 predictions from the six common conditions are retained, not regenerated.
Only the 512 new-method/frozen-own-B1 requests may require fresh 8B generation;
exact duplicate native requests still share a single original response. Invalid
or incomplete returned outputs are retained. A different final bank is not given
an old bank's prediction merely because the method name is similar.

The original main and original own-B1 rows remain in the preserved v0.23 study;
neither is renamed as the revised method. The two historical policy comparators
remain visible but are not claimed to isolate the new adaptive selector under
identical teacher feedback. The new matched controls in the
[minimal-ablation plan](OPENEXEMPT_ADAPTIVE_PAPER_READINESS_AND_MINIMAL_ABLATIONS_20261026.md)
serve that separate purpose.

## Inference, source identity and cost

Use the unchanged single frozen bf16 Qwen3-8B revision and direct public
asset/citation interface, 32768 context, 8192 output, thinking enabled,
temperature0.6, top-p0.95, top-k20 and generation seed45. Use the captured common
four-worker/four-sequence environment. No teacher, skill update, answer repair,
model restart or learning repetition is part of this evaluation.

Bind the completed learner configuration, source manifest, initialization, exact
B1/B8 publications, completion, terminal preservation, bank digests and the
evaluation configuration before reading the evaluation packet. The revised own-B1
must equal `frozen_after_B1.json`, not the original study's B1 or a selected bank.
The actual generated requests must contain the corresponding task-visible skills.

Retained predictions must match the original input, schema, full generation
fingerprint and raw-response origin. Preserve the original pre-grading records
and record their origin; reuse is not a new draw or free omitted compute.
Report fresh calls/tokens, retained calls, exact within-evaluation reuse, errors
and wall time separately. Save both new conditions completely before grading.

## Endpoints and paired analysis

Primary endpoints remain native macro-F1 for EC and EV. Retain complete-output
F1, invalid format and negative/unscored asset claims as quality audits; do not
replace native endpoints with a newly favorable average. Report the two task
scores rather than presenting the two correlated task views as independent
datasets.

Five primary paired contrasts compare `adaptive45` against `empty`, `static`,
`ACE45`, `text45` and `adaptive_own_B1_45`, giving ten primary endpoints.
Two secondary paired contrasts compare against the historical `whole_bank` and
`task_local` conditions, giving four secondary endpoints. These are the new
supplement's fixed families, not a retrospective extension of the old study's
confidence claims.

Use source-paired differences across all128 sources, resampling each complete
EC/EV source pair with PCG64 seed2026102192 and20000 bootstrap samples. Report
ordinary95% intervals and Bonferroni intervals separately for ten primary and
four secondary endpoints, using the existing paired-source computation.
Record help/hurt/tie counts and every original denominator. These intervals are
conditional on the actual learned banks, not independent-learning variability.
Independent learning repeats remain user-deferred.

## Existing evaluator integration

The preserved evaluator's formal CLI currently accepts only the old initial8 and
final16 staged designs. Its runtime verifier also binds the original serial
seed45 and phase-dispatch source epochs. The adaptive run intentionally has a
new learning source and a four-native/one-teacher dispatch. Do not impersonate
one of those old recipes to make a check pass.

After live TRAIN finishes, add an explicit revised-study stage to the existing
evaluation path, with exact old and revised provenance and the retained-request
identity checks above. Keep the common actor/scorer unchanged. Do not hot-edit
the live-bound runtime verifier, discard its checks, monkeypatch a policy or
introduce a separate answer-selection layer. Freeze the resulting configuration
and exact final banks once, then run the supplement.

## Next paper step

Use this table to establish final utility and continued evolution. Use the
matched fixed-whole/fixed-dependency controls to establish the selector's
contribution. Keep all original study results intact and update the manuscript
only with actual, completed observations. This protocol launches no experiment.
