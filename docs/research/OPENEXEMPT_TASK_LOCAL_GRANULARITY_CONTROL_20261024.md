# Task-local granularity control, fixed before learning and TEST

24 October2026. The user authorized selecting the more appropriate second
ablation. Task-local replaces the genuinely unstarted first-commit control;
the original config/freeze and all historical plans remain available in Git
and recovery archives. No first-commit learning result is discarded or relabelled.

## One changed learning mechanism

The main45 learner uses legal_scope: within each EC/EV task, publicly co-visible
legal namespaces define dependent edit groups. The new control uses task_local:
all EC edits form one admission unit and all EV edits another. Whole-bank remains
the other independent control. The existing implementation already supports all
three policies; no actor, parser, scorer, teacher or skill-file format is changed.

All three start from empty and use the same128 TRAIN sources in the same order,
eight batches of16, generation seed45, original serial8B serving environment,
teacher settings, full seen-TRAIN replay,4096-token library cap, at most two
candidates per batch, carry_partial_and_refine feedback, original EC/EV scores,
complete-output EV/negative/format retention checks and own-B1 control.
Task-local keeps full-parent guidance for any unaccepted task; its composed
bank must still pass the original complete TRAIN gate and exact observed-wire
coverage. It is not arbitrary per-skill mixing or an answer-selection fallback.

The total actual candidate counts, native generations, teacher tokens and wall
time may differ. Common caps and per-answer settings are not equal actual total
compute. Whole-bank versus legal_scope tests the submission-granularity change;
task_local versus legal_scope tests legal-context detail beyond EC/EV splitting.
Neither contrast individually proves that replay or feedback itself is novel.

## Scope, provenance and budget

The unique new config is
`configs/openexempt_task_local_public_assets128_20261024_run01.json`.
Its comparison source is the actual completed main45 Run03 config, not a copied
bank. Its frozen manifest must be created under the unchanged serial sources
before it starts. It runs only after whole-bank45 naturally completes and both
terminal archives are verified; no simultaneous learner is launched.

The live teacher ceiling remains4023 during whole-bank. Only its actual complete
predecessor permits the single prospective32-attempt extension to4055, retaining
every historical reservation. This is the same second-control allowance, not
an extra third control. No145/245 main, ACE or Text repeat is authorized to start
by this protocol. No TEST outcome is read to select this policy or its settings.

## Paper evidence and later work

The first frozen TEST compares eight actual banks/conditions: main45, own-B1,
empty, blind static, ACE45, Text45, whole-bank45 and task-local45. All conditions
answer both EC and EV on the same128 unseen sources before any grading.
The six main-table rows and two component rows are not eight distinct methods.

The user has deferred independent repetitions until necessary experiments and
a teacher-facing draft are available. Any prospective repeat recipes are kept
only to preserve the same scientific algorithms before TEST exposure. They do
not grant execution authority or establish learning-run stability. Actual repeat
work and any final three-build table require a later user decision. Source-level
intervals from the single-build table remain conditional on these actual banks.

Brother 实验设计规范 informs the claim-to-control mapping and
cost/harms accounting. It does not require novel ablation names, three invented
contributions, five runs, extra models or a validation set.
