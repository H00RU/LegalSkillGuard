# LegalSkillGuard — paid partial TRAIN observations are learned, saved and frozen

[Current report](../reports/method_redesign_20261109/observed_library_update_report.md) · [Independent verification](../reports/method_redesign_20261109/observed_update_publication_verified.json) · [Previous real probe](../reports/method_redesign_20261109/M2_discriminating_probe_report.md)

Goal ACTIVE and incomplete. This offline step adds zero model calls. The existing real cash probe acquired only the D group; R was never asked. The new finite learner uses the likelihood marginalized over unobserved R slots, keeping missing None distinct from the observed unknown class2. Structured M2, same-grammar factors, confusion matrices, joint empirical and same-feature softmax receive the same partial observations. Original grammar, context, priors and optimizer settings remain unchanged. Six necessary regressions pass, including full-observation equivalence and correct missing-answer handling.

The new frozen library uses five real TRAIN cases from the same two induction mothers,18 observed slots and2 unasked slots. Per-mother total weight remains1. The independently verified cash-to-false training phrase is actually added to the public source-role program: on this TRAIN case, the previous false/unknown changes to false/false. This is training replay, not transfer or M1 incremental success. A reweight-only attribution separates new observation evidence from per-mother balancing. No unseen R answer is filled in.

The library is saved and reloaded; all nine h-conditioned forecasts in the actual update context reproduce exactly, as does the source-role execution. Original frozen models, scores and responses are unchanged. All1418 cumulative call rows plus ledger metadata and oracle views have the same logical snapshot before and after; counts remain1365 executor/53 teacher, pending0. Executor thinking OFF and generation settings retained. No new source, full build, matrix, TEST or paper.

The old M1 query planner schedules zero actions over the nine existing texts. Its current three templates implement two ordinary role projections. Their candidate partitions match the corresponding ordinary PBE operator, conditional on the same answer; differing prompt accuracy is not assumed equivalent. Runtime question answers remain unobserved. Neither this offline update nor the query audit establishes the two substantive contributions.

- [Frozen library](../artifacts/rr_method_redesign_20261109/observed_library_update_v1_20261109/library.json) · [Input/source seal](../artifacts/rr_method_redesign_20261109/observed_library_update_v1_20261109/seal.json)
- [Execution/recovery receipt](../reports/method_redesign_20261109/observed_library_update_results.json) · [Protocol](../reports/method_redesign_20261109/observed_update_protocol.md)
- [Learner](../legal_skill_guard/rr/observed_reader_learning.py) · [Tests](../tests/test_rr_observed_reader_learning.py) · [Costs](../reports/method_redesign_20261109/cost_snapshot.json)
- [Manifest](../reports/method_redesign_20261109/observed_update_publication_manifest.json)

Scientific evidence on research/legalskillguard-rr-v2; main5368150 preserved. No private Git ancestry, credentials, environments/weights, SQLite metadata, adapter caches or TEST packets/labels are uploaded. This delivery is not Goal completion.
