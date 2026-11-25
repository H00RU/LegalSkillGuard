# Project instructions for LegalSkillGuard

The server workspace is `/home/yndx/hhy/legal-skill-current`. Read
[the research handoff](docs/NEW_CHAT_HANDOFF.md) after a context compaction
or interruption. Verify actual jobs, ledger, bindings and terminal evidence
against the handoff before continuing in the current conversation.
Use ordinary conversation to implement and evaluate M3, judicial reason
correction skill learning, as the current primary method. M1 is closed and
M2 is on hold. The [current M3 plan](reports/judicial_reason_correction_skill_learning_20261126/PLAN.md)
defines the active research work. Reconcile the GitHub handoff with newer
server evidence while preserving local implementation changes and run records.

The original Goal, prior handoffs, and saved commands are historical evidence.
The convergence study's nested `SERVER_GOAL.md` is part of that run's archived
configuration. Use the root `SERVER_GOAL.md` to find the current handoff.
The convergence study's frozen [plan](reports/legal_skill_convergence_20261117/PLAN.md)
and [protocol](reports/legal_skill_convergence_20261117/protocol.json)
document the evaluation design. Follow the user's current request for task authority.

## Preserve assets and factual boundaries

- Keep the 177 source reviews, existing code, libraries, raw responses, failures,
  results, manifests, versions and uncommitted work. Do not run destructive cleanup to make the
  working tree look clean. Use the same project directory; do not create another
  sibling "latest" project.
- Before a major replacement, archive the necessary existing implementation,
  configuration and evidence with hashes. Avoid unrelated repository refactors
  and compatibility layers without a present need.
- Preserve the continuous ledger at
  `artifacts/rr_v2_preflight/research_ledger.sqlite3`; clearing a Goal never
  resets physical request counts or costs. Follow the new task and applicable
  resource authorization; do not restore superseded request/repair-round caps
  or treat saved pending tasks as permission to dispatch.
- TRAIN/DEV/TEST exposure is a fact, not a resettable instruction. The old
  fixed-study TEST was already exposed. Preserve its manifests and do not call
  reused exposed data a new blind test. Do not use held-out labels for repairs.
- Keep comparison conditions and scores accurate. Distinguish actual learned
  main-path execution from fallback, cached replay and offline checks; do not
  count those as independent mechanism evidence.

## Research and writing workflow

Use the user's brother's skills when relevant, reading each selected skill fully:

- `/home/yndx/.codex/skills/paper-ideation/SKILL.md` for research questions and contributions.
- `/home/yndx/.codex/skills/paper-experiments-appendix/SKILL.md` for claim/evidence design and reporting.
- `/home/yndx/.codex/skills/paper-figures-data/SKILL.md` for quantitative checks and figures.
- `/home/yndx/.codex/skills/anti-defensive-writing/SKILL.md` for Chinese argumentation;
  the `anti-defensive-writing-en` counterpart for English manuscript work.
- `nature-paper` may help with concise scientific prose when applicable.

Supervisor-Skills is also installed under `/home/yndx/.codex/skills/` from
`HKUSTDial/Supervisor-Skills`. See `docs/RESEARCH_SKILLS.md` for its 12 skills,
the pinned version, installation evidence and task-based selection. Read each
selected skill fully before using it; use it alongside the brother's skills
and the applicable anti-defensive-writing skill.

These are authoring workflows, not learned legal libraries. Do not modify lawyer
or teacher prompts just to activate a writing skill. Writing style never changes
numerical results, comparison conditions, uncertainty or negative evidence.

## Active experiment discipline

Before starting or resuming authorized work, check actual processes, requests and
bindings. While a run is live, leave every frozen-manifest file unchanged,
including source, tests, configuration, protocol and frozen README. Write live
observations only to unbound evidence files. Preserve at a safe boundary before
scientific changes. Do not duplicate a job from an old PID or progress file.

Exact historical reproduction uses its original manifests and source snapshots.
Preserve v0.23, utility v6 and unsuccessful studies. The five historical AST-lock
failures remain historical facts; do not alter frozen scientific hashes merely
to make historical checks pass. Use checks relevant to actual new changes.

Current development branch: `research/paired-interface-structural-transfer-20261116`;
preserved predecessor: `repair/lift-corev-activation-20261112`; public evidence
branch: `research/legal-skill-evolution-20261111`. Do not directly modify `main`.
