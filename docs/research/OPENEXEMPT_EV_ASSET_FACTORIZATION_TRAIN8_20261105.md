# Multi-asset output load: bounded TRAIN8 diagnostic

## Purpose

The preceding native EC-context condition improved coverage but introduced 15
new wrong amounts and did not retain the current cohort. This test asks whether
the same learned legal instructions become more executable when each generation
answers one asset, while every original fact and statute remains visible.

The intervention changes response scope, not legal knowledge or arithmetic.
All original asset mentions, including potentially non-debtor property, must be
answered. Each subcall decides eligibility and amounts itself. The host merely
merges disjoint public asset keys; it never filters citations, calculates/clamps
amounts, inserts answers, repairs output, or retries failures.

This follows the general task-decomposition rationale of
[Decomposed Prompting](https://arxiv.org/abs/2210.02406), not a claim of a new
decomposition algorithm. The question here is specific to the observed
skill-to-execution failure. No decomposer model, solver or new production layer
is introduced.

## Fixed sample and conditions

Use the existing B3 bank and original TRAIN32 pool. Select four current and four
prior cases using public allowable jurisdictions and source-key hashes only:
current first; prioritize uncovered namespace combinations, then lexical scope
order; within each group take the smallest SHA256(source_key). If fewer than
four groups exist, fill by remaining source-key hashes. No scores or answers
enter selection. Freeze the resulting IDs before any new generation.

The resulting current IDs are 229, 240, 243, 244; prior IDs 213, 201, 193, 192.
All five available jurisdiction combinations are represented. There are 19
literal asset mentions, so two arms require exactly 38 new EV generations.

The two new arms are empty-library and B3-library asset-wise answers. Compare
them with their actual previously generated whole-case answers on the same
eight cases, after verifying identical original requests and schemas. All
conditions receive the same legal facts, statutes, given jurisdictions, public
vocabularies and per-call model/sampling limits. Do not supply EC predictions.

For each asset-wise request, change only the output-scope sentences and root
schema keys to its focus asset ID; append that ID. All other message text and
the full original context remain unchanged. The legal result type is unchanged.
The final merged answer is evaluated against the entire original case target,
using the unmodified native and complete-output scorers. A malformed/incomplete
subcall invalidates the whole case rather than silently dropping that asset.

## Budget and decision

Zero teachers, no new EC, at most 64 EV calls and 30 minutes actor wall time.
The frozen sample actually requires 38 calls. Stop dispatch at 20 minutes to
drain the same 600-second transport timeout. Use the existing healthy 8B service
and four workers. Keep every raw response and failed attempt. All predictions
are saved before target grading. No early score-based stopping or case reselection.

Report full-case native/full F1, current/prior means, missing claims, wrong
amounts, extras, invalid cases, tokens and physical call count for all arms.
Also report the change in the skill-minus-empty gap, so a generic decomposition
gain is not described as a skill-learning gain. This is not equal per-case
compute: the new arms use one generation per mention, the historical arms one
generation per case. Preserve this distinction even if scores improve.

Further investigation is warranted only if the B3 factorized arm improves both
full-case F1 metrics by at least 2 percentage points over its whole-case parent,
does not reduce either current/prior mean, introduces no extra invalid case,
reduces wrong amounts, and has positive both-parseable gain. Otherwise close
this factorization screen without variants. This is a diagnostic screen, not a
replacement for the original training admission or evidence of later-batch
learning. Any formal adoption, changed training or paper column requires the
user's confirmation and a clear matched-comparison plan.
