# LegalSkillGuard: skill-evolution evidence and real TRAIN fit

[Current Goal](docs/CURRENT_GOAL.md) · [Current evidence](docs/METHOD_REDESIGN_CURRENT.md) · [Paper component gains and TRAIN suitability](reports/legal_skill_evolution_run_20261111/METHOD_EVIDENCE_AND_TRAIN_FIT.md) · [Actual compositional compiler comparison](reports/legal_skill_evolution_run_20261111/COMPOSITIONAL_COMPILER_RESULT.md)

The same Goal remains active and incomplete. The five fixed datasets, native scoring and 128 TRAIN parents / 280 views are preserved. Source/answer lineage and parent isolation are checked, with explicit dataset-specific mechanism boundaries.

The official NQG grammar baseline is integrated from its pinned Apache-2.0 implementation. An indexed equivalent candidate search replaces the original exhaustive interval materialization: 61 real acquired pairs roundtrip, 17 compositional rules, 5.699 seconds induction. On nine real original TRAIN contracts, results equal the literal baseline: 12/12 native core judgments on acquisition contracts; no new core coverage on two existing diagnostics; 24/36 fallback. Every record constructor misses required terminals on each diagnostic. This localizes the remaining bottleneck to transferable semantic acquisition and frame abstraction, without claiming a contribution from generic grammar induction.

This increment uses zero model calls. Cumulative 9287 executor / 172 teacher, pending zero; 143 regressions pass, all 206 original frozen entries and 9459 physical ledger rows are unchanged. Thinking OFF. No new full training, DEV/TEST matrix or paper. Main unchanged.
