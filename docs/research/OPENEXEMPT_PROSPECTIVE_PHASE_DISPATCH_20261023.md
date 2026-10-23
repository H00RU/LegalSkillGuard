# Prospective independent-phase scheduling — NOT DEPLOYED

23 October 2026. Preparation in an isolated worktree based on canonical
`bc7c2036704048a0d00011a1786e934036a8c0c5`. No running learner, queue, service,
frozen profile, paper result, source packet, score or TEST artifact is changed.
This is an execution change, not another skill-learning method or contribution.
The brother's experiment skill is used for matched conditions, costs and claim
boundaries; its example numbers and prescribed contribution count are not adopted.

## Observed cost, not a hypothetical speedup

ACE seed45 spans 22 October 16:14:05 to 23 October 15:48:37 CST: 23.5756 wall
hours including interruptions. Its 911 original 8B generations have 18.7174 hours
of input-file-to-response-file intervals, including request processing rather
than a measured GPU-busy integral. Its 442 successful teacher calls record
3.6193 hours; there were 443 attempts and one timeout with unknown usage.
The remaining 1.2389 hours are not assigned entirely to any one cause.

At 22:05 CST Text45 had completed54 source requests in3964.14 seconds. The
same-mean512-logical-answer scenario is10.44 hours, excluding teachers; this is
neither a remaining ETA nor a measurement of final-library inference. The A40
utilization snapshot was98%. Removing CPU inspection does not remove the main
serial generation cost. Current service arguments explicitly set
`--max-num-seqs 1`, so HTTP threads alone do not establish GPU batching speedup.

## Matched boundary: retain seed45, accelerate only future repeated learning

1. Keep current Text45 unchanged through actual completion and preservation.
2. Keep both already declared seed45 learning ablations on the original runtime
   and original model process. This matches the actual seed45 main reference;
   do not introduce a scheduler change into a nominally policy-only ablation.
3. Only after those original stages naturally complete and are preserved may
   the remaining six seed145/245 builds receive a new frozen execution version:
   main145, ACE145, main245, ACE245, Text145 and Text245, in the existing order.
4. Keep all three real learning seeds and all16 final arms, ten primary and four
   secondary contrasts. Do not add a fresh main45 reference, discard the actual
   main45 curve, select a better old bank, or use TEST to choose this schedule.
5. Main/ACE/Text are matched within each learning-seed stratum. Seed45 uses the
   original one-sequence runtime;145/245 prospectively use the same new runtime
   across methods. Report this execution difference: between-bank variation is
   not purely a seed-only variance estimate under one identical schedule.

All frozen-library TEST arms will use one common prospectively frozen final
schedule. The estimator remains conditional on the realized banks and common
decode. This amendment does not authorize opening TEST before all actual banks,
the final matrix, analysis, source provenance and environment are ready.

## Implemented in isolation

`PhaseDispatch` is one bounded ordered execution helper, not a planner, router,
fallback, model client or solver. It is explicit opt-in; an absent declaration
retains serial execution. The actor functions, prompts, answer decoding,
transport, source matching and admission criteria remain unchanged.

| Phase | Allowed overlap | Barrier retained |
|---|---|---|
| Main first forecasts | Independent task rows; original arm rotation within each row | All batch predictions before any current grading |
| Main candidate replay | Independent rows under one fixed candidate | Whole replay before admission; candidate attempts stay sequential |
| ACE first forecasts | Independent rows; original within-row rotation | All arms before labels |
| ACE TRAIN update | Independent case trajectories, at most four; each case's reflection/regeneration rounds remain sequential | Original row/round tag ordering before one curator |
| Text source/final inference | Independent rows under one fixed entering bank | All256 source forecasts before label release; final bank before replay |
| Text analysts/merges | At most two teachers; independent analyses or groups at the same level | All children before their next merge level and translation |

Complete messages, schema and generation key a lock around the unchanged
actor's full cache path. Identical wires retain one physical origin; no answer
is selected by score. Results are reassembled in original input order. In
particular ACE's last-tag-per-ID rule must not follow completion order. Text
preserves the existing author's small-tail placement; its flattened traversal
is not necessarily numerically sorted, although every original patch remains.

Progress writes and teacher-attempt updates are serialized. The existing ledger
already holds an exclusive file lock for each reservation; its model and exact
ceiling checks remain. Different runs are not overlapped or given inconsistent
shared ceilings. Any failure cancels not-yet-started work, stops later phases,
drains in-flight responses and records actual costs before terminal preservation.
There is no failed-answer retry, format repair, clipping or fallback. The
existing narrow capacity-without-result policy remains unchanged.

Proposed explicit settings are four request workers, two teacher slots and a
captured four-sequence single-instance service. A declared one-sequence overlap
mode is distinct and must not be described as demonstrated GPU batching.
No second model or instance is introduced. Per-answer context32768/output8192,
thinking, temperature/top-p/top-k, seeds, revision, dtype, legal task, public
inputs, teacher model/reasoning, labels, memory caps, update limits and full
source denominators remain unchanged.

## Still required before any deployment

- Complete functional and source-provenance integration, not only executor unit
  checks. Preserve exact v1 source artifacts, approve exact v2 byte hashes, and
  require unchanged actor/grader/transport/gate ASTs; do not waive arbitrary
  differences in old manifests. The formal evaluator must accept both actual
  declared execution versions without narrowing its16-arm or complete-bank gates.
- Publish new immutable profiles for the six unstarted repeats after actual new
  environment capture. Rebase only operational fields and declared scheduling;
  retain the complete old configs and budget history. Same attempt ceilings and
  planned teacher/native budgets, no quota reset.
- Prepare an exact finite handoff before retiring any waiting controller. Never
  stop a controller that currently owns an active learner, and do not hot-edit
  its script or replace a model while any old-profile learning remains active.
- Verify and double-preserve the original on-disk deployment/recovery assets,
  source and all completed stages before a single-instance serving transition.
  File presence alone is not sufficient model-asset verification.
- Use at most eight fixed public TRAIN transport/timing requests: EC/EV for
  source181/182, once serial and once with four workers on the newly captured
  service. Do not load labels, score, select answers or import them into a learner.
  Save all calls and costs separately. This is not full qualification or TEST.
- Measure actual throughput and memory, and report rather than promise a speedup.
  A failed integration stops for diagnosis; it does not silently select serial
  answers, an older library or an alternative model.

At this revision36 focused CPU checks pass in0.42 seconds, with no model, teacher
or TEST calls. They cover cancellation/drain, duplicate-wire origin, teacher
limit, real atomic progress/ledger concurrency, protected functions and mocked
main/ACE/Text phase ordering. The original Text grouping rule initially exposed
a wrong test expectation of globally sorted traversal; the expectation was
corrected against the pinned original rule, not by changing the rule. Real GPU
integration, measured speedup, new profiles and promotion remain uncompleted.
