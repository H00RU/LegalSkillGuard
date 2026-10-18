# Prior202 training-only source-reading policy calibration

2026-10-19. Run `legal_contractnli_training202_read_pool_calibration_20261019_run01`.
Entry: `python -m experiments.decision_evidence_transfer calibrate_reading <config>`.
This is ordinary CPU tool training, NOT native lawyer evaluation, a qualification
suite, skill gain, a new GPU model, or a dedicated validation set.

## Evidence motivating the correction

The completed witnessed forward16 study used72 native/2 new teacher/1 new fit,
plus its inherited failed initialization0/1/1. All16 forward full-source answers
are preserved. Combined82.35/73.16/61.76% accuracy/Gold-NN original hard F1/joint,
empty79.41/73.99/57.72%. Non-neutral exact79->80, correct NM78->88: the11 joint
gains are mostly NM, not evidence-acquisition improvement. Do not upscale that
configuration or call its first-batch positive classification a breakthrough.
Its382-member terminal archive is personally dual hash-verified, SHA256
9e674fb22447ac40289f84fd6db50d4deaa4ecd2463d99e9f4c18340140059e9.

On its COMPLETE first8, actual same242 model candidates covered106/169 Gold
members, native combined107/169. Of62 combined false negatives,58 were outside
the explicit candidates, even though all original source was always present.
The binary p>0.5 decision has been used as the reading-access interface. The
original audited scorer returns raw rankings; a binary positive decision is
not automatically a suitable retrieval pool. The already-scored8 diagnostic
grid showed recall/precision tradeoffs; it is NOT a chosen threshold, native
performance, proof of a general fix, or evidence that the source was hidden.

## Training data and no test/validation drift

Use EXACTLY the original prior202 TRAIN cases that trained the common initial
ordinary model. Texts/offsets are verified against the original author TRAIN
ZIP and annotations are copied only for these202. No current16, later128,
official DEV/TEST labels enter calibration. Global TRAIN URL/normalized-text
connectivity is source-only metadata; all members of a connected source identity
stay in one OUTER fold. Here202 prior components happen to be202 singletons.

Five fixed source-group outer folds, seed2026101903. Each fits the UNCHANGED
existing no-program ordinary scorer on the other groups, including feature
fitting and both model stages. Its existing inner document folds stay intact.
Every prior training case is scored once outside its component, with all17
hypotheses and every original SPAN. Original NM pairs supply all-negative
membership targets. No special cases, relabels, semantic judge or hard-source
removal. All202 remain training data; no24/144 detection or validation set.

Fit one shared reading threshold on these out-of-source training predictions
by F-beta with beta2, a prospective recall-favouring retrieval objective.
Ties prefer fewer reading proposals; equal-score blocks are indivisible.
Also report the F1-fitted and original0.5 COMPONENT references, not separate
selected/deployed methods. Threshold fitting uses these training labels, so
its apparent calibrated OOF component values are parameter fit, NOT independent
validation, held-out paper performance, or native lawyer metrics.

The original native output/scoring remains untouched. The scorer still exposes
its ordinary binary p>0.5 diagnostic separately. A reading threshold ONLY changes
fallible source proposals before a future native answer; it never selects,
completes, filters, repairs or reinterprets the lawyer's final evidence/label.
No active run is hot-modified. Any future use is frozen under a NEW Run ID and
shared identically by empty/skill/mature-method controls. If both improve equally,
that is ordinary-tool improvement, NOT skill contribution. Classifications,
original Gold-NN hard F1, strict joint, uncertainty and all adverse cases remain.

## Finite implementation, resources and next decision

Two small no-model tests pass0.42s: threshold objective/tie/read-pool semantics,
and whole-source exclusion for both stages using a synthetic training fixture.
No GPU/teacher qualification calls. Real planned work0 native/0 teacher/5 CPU
fits with the SAME existing scorer/settings, sequentially,2 threads, no extra
LLM, embeddings, model service, paid API or model download. Fold score records,
original targets, source partitions, code/input hashes, timings and partial
failures persist. Do not save five redundant deployed model checkpoints.

The preceding development family is217 native/9 teacher/7 fits; after this
ordinary calibration completes,217/9/12. No teacher ledger reservation is needed.
Freeze code/data/config, preserve source/Git and use the existing independent
terminal preserver. The helper and command live in existing modules; no new
test framework or runtime middleware. A fitted reading policy is just the next
foundation for actual chronological skill learning, not the paper objective.
