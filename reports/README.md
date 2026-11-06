# LegalSkillGuard RR-v2 — fixed shared training build

The original 128 TRAIN sources and eight batches are complete, starting from an empty
library. B1/B8 and ordinary-control frozen states are preserved. Formal evaluation,
frozen tests and paper writing have not been started. Stop for review before evaluation.

- [Build report](../reports/legalskillguard_rr_v2_formal_build_20261106.md) · [128-source status](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/source_status.csv)
- [Final audit](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/final_audit.json) · [actual cached recovery](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/cached_recovery.json)
- [B1](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/B1.frozen.json) · [B8](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/B8.frozen.json) · [all checkpoints](../artifacts/rr_v2_formal_build_20261106/run_citation_fix/batches)
- [Coverage](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/mechanism_coverage.json) · [failure classes](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/failure_classification.json) · [costs](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/cost_summary.json)
- [Source](../legal_skill_guard/rr) · [formal controller](../experiments/rr_v2_formal_build.py) · [reproduce/recover](../docs/rr_v2/FORMAL_BUILD_REPRODUCE.md)
- [Previous method repair](../reports/legalskillguard_rr_v2_method_gap_repair_20261106.md) · [prior study](../paper/README.md)
- [Publication manifest](../reports/rr_v2_evidence/formal_build_20261106_citation_fix/publication_manifest.json)

Executor thinking is OFF. Teacher is gpt-5.6-sol with reasoning_effort=high through the
existing Codex CLI; no explicit temperature. Cumulative physical counts are
424/6000 executor and 14/20 teacher.
Failures remain charged; fallback correctness is not core mechanism success. Training
reference matching is not formal evaluation. Old preflight and aborted-build completions/summaries are
historical and were not reused as this fresh build's completion records.

The aborted citation-contract version is retained separately with65 executor and2
teacher attempts and34 completed source records. Its canonical Illinois citation
closure defect and offline repair evidence are linked in the current report. The
corrected run starts from the unchanged cumulative192/6 ledger and an empty library;
it does not present the old partial build as current completions.

This development-branch content mirror preserves raw TRAIN scientific evidence and the
previous public tree, without private local Git ancestry. Private SQLite metadata,
credentials, machine-operation history, model weights/environments, bound host binaries,
and DEV/TEST packets or labels are omitted. Public navigation is an explicit variant of
the locally frozen README/handoff. See the manifest for exported bytes and omissions;
the clone alone does not provision the bound host runtime. Main is unchanged.
