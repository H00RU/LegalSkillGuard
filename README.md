# LegalSkillGuard — source-bound discrimination follow-up

[Current implementation/evidence report](reports/method_redesign_20261109/source_binding_followup.md) · [Independent verification](reports/method_redesign_20261109/source_binding_publication_verified.json) · [Previous real TRAIN pilot](reports/method_redesign_20261109/M1M2_real_TRAIN_report.md)

Goal ACTIVE and incomplete. This follow-up adds ZERO model calls. A source-bound learner now derives role phrase/class dictionaries, lexical guards, precedence and typed discrimination-question/answer constraints from the original two TRAIN induction mothers. On the four previously observed excluded-case texts, offline pair accuracy and complete role candidate coverage are4/4. The same-information ordinary extraction learner is exactly equal, also4/4; no unique M1 effect or new blind/model-generated success is claimed. Seven targeted regression tests pass. Unissued questions remain unobserved.

A new joint label/span audit finds four real induction class errors, only two compatible with observable whole-role bundle copying (one merely unknown/null). The frozen four-label channel has not established source-binding misreading. All20 fixed source histories were inventoried without calls; the sole Airline7 teacher disagreement concerns storage fit versus the official first-carry-on convention and is not silently promoted to a new error label or acceptance gate.

Cumulative ledger1362 executor/51 teacher, pending0; executor thinking OFF, existing models/config/data preserved. No new full build, DEV matrix, TEST or paper. Both substantive contributions remain unestablished; do not repeat absorbed experiments or rename shared extraction machinery as novelty.

- [Source-bound learned program](reports/method_redesign_20261109/M1_source_bound_program.json) · [Offline real-text regression](reports/method_redesign_20261109/M1_source_bound_regression.json)
- [Whole-role channel audit](reports/method_redesign_20261109/M2_role_bundle_audit.json) · [Fixed-source reuse inventory](reports/method_redesign_20261109/M1M2_fixed_pool_reuse_audit.json)
- [Source implementation](legal_skill_guard/rr/source_discrimination.py) · [Regression tests](tests/test_rr_source_discrimination.py)
- [Calls and costs](reports/method_redesign_20261109/cost_snapshot.json) · [Manifest](reports/method_redesign_20261109/source_binding_publication_manifest.json)

Scientific update on research/legalskillguard-rr-v2. User main5368150 is preserved. Original studies, raw generations, ledgers and frozen pilot files remain intact. Private Git ancestry, credentials, environments/weights, adapter caches, SQLite metadata and TEST packets/labels are omitted. This is progress delivery, not Goal completion.
