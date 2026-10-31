# Paired repair-outcome evidence: one TRAIN mechanism test

Status: planned, not deployed; no live frozen file is changed.

## Purpose

Test one concrete learning-interface failure: a rejected multi-edit proposal can
contain useful local repairs, but the next teacher receives only its regressions.
The test changes feedback evidence, not the actor, legal task, scorer, library
delivery, proposal capacity, admission policy or amount of actor exploration.
It does not assume that more teacher input or more skills improves performance.

## Fixed origin and arms

- Use the earliest fully verified omitted-repair episode: fourth-formal B5
  candidate 1 and the actual B5 candidate-2 teacher context.
- Parent: B4/B5 published bank `92c53de0370331ab725fc55cd94ce6e356834cfd181e7f7385e2386759fb25a8`.
- Prefix: original TRAIN sources 181--260, 80 cases; current cohort 245--260.
  Later TRAIN sources 261--308 are a subsequent-case check, not a new test set.
- Both arms use the same actual parent, rejected first proposal, public context,
  original targets, complete background cases, teacher model/settings, 4096-token
  bank cap, one fresh second-attempt teacher call, and unchanged admission gates.
  Do not compare a fresh teacher draw against only the old cached teacher answer.
- Control: the existing negative-first eight-witness feedback.
- Intervention: alternate genuine harms and safe improvements within the same
  eight-witness budget. Preserve distinct source/task identities. Order harms by
  the existing severity; order safe improvements by their minimum native/full
  gain, then mean gain and source/task for deterministic ties. If either direction
  is exhausted, fill from the other and then unresolved changed-request failures.
  No ratio sweep, extra candidates or hand-authored legal rules.
- For this isolation only, eligible witnesses must already have their facts,
  original target and actual parent answer in the fixed historical teacher body.
  This leaves four available positive task pairs from the same supplied context;
  it holds the entire background and original-label payload constant rather than
  confounding outcome evidence with extra cases or labels.

A safe improvement has no native-F1 or full-output-F1 decrease, no increase in
format/negative/unscored-asset failures, and a strict native or full improvement.
Correct empty EC answers need not have native F1 equal to one. Both witness
directions are real candidate-before/after contrasts, never invented successes.
The feedback preamble may be made outcome-neutral, identically in both arms;
the original teacher receives no extra instruction, label or tool advantage.

## Evaluation and decision

1. Freeze both teacher requests and source hashes before calls. Audit identical
   non-feedback bodies, maximum source 260, true parent references and actual
   candidate-after origins. Keep original reasoning-tail limits unchanged.
2. Generate one delta per arm. Replay all 80 prefix sources with the existing
   actor and original native/full/count gates. Record rejected proposals and
   actual admitted libraries separately; never force a candidate into a bank.
3. Freeze both actual resulting banks. Obtain every subsequent 48-case answer
   for both arms before reading their grading files. Exact raw-wire reuse is
   allowed only with matching actor payload/schema/generation provenance.
4. Report EC/EV native and full F1, paired gains/harms, emitted format failures,
   negative/unscored claims, proposed versus admitted edits, library contents,
   teacher and native tokens/calls and elapsed time. Report the parent alongside
   both arms. No best-case or best-checkpoint selection.
5. Adopt this feedback mechanism for a new empty-start formal Run ID only if an
   actual update is admitted, the later TRAIN EC/EV native/full families do not
   regress versus either the parent or the fresh control, counts do not worsen,
   and the intervention improves later mean native F1 over both. Otherwise preserve the result and
   diagnose that same mechanism before authorizing another long formal run.
   One diagnostic pair is not an independent replication or a significance claim.

## Execution boundary

Start only if needed after the current fourth-formal full-eight learning and its
already observed TEST version supplement are terminal and dual-disk preserved.
Execution-order update, fixed before any fourth-version TEST score was produced:
the complete third B8 bank is stronger on both native/full TRAIN families, so
first evaluate that already completed full bank after the fourth TEST. This is
a TRAIN-selected version reference, not selection among TEST checkpoints or a
new independent learning repeat. Run this unchanged paired TRAIN probe only if
the third reference does not show all eight numeric gains against the preserved
historical controls. Both version results are retained; a new source-disjoint
primary matrix is still required. This changes order, not the probe's inputs,
parent, witness selection, proposal budget or adoption checks.
Preserve their complete source snapshot before any scientific source edit. Do
not use old or new TEST labels to select witnesses or tune this test. Do not open
the prospective source-disjoint TEST packet here. All extra independent
main/ACE/Text repetitions remain user-deferred. No new model, solver, router,
fallback or generic framework is introduced.

## Evidence and attribution

The existing full native replays already contain the paired outcomes: B5-C1 has
10 safe gains, B6-C1 has 19, but subsequent bounded candidate feedback selected
zero of them. Original labels and actual parent predictions were present. These
observations identify an omitted signal, not proof that it is the sole cause.
ScienceClaw's verified failure--repair--success source instance motivates the
contrast; its workflow/operator framework is not imported. Primary source and
actual record hashes are retained in
`Primary_author_ScienceClaw_verified_repairs_vs_T8_negative_only_actual_TRAIN_witness_gap_20261028.json`.
