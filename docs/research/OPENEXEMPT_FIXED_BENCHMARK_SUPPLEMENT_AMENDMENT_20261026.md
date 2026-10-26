# Fixed-benchmark supplement plan, 26 October 2026

The user asked to retain the original128 TEST cases and reuse completed comparator
predictions. Prioritize this fixed-benchmark supplement once the revised method
and its unique terminal bank are frozen. No evaluation is started by this note.

- Keep the original task packet, native scorer, direct interfaces, model revision,
  per-answer generation settings and common serving profile.
- Retain the immutable old predictions, failures and scores for empty, static,
  ACE, Text and the original learning controls. Their construction is not repeated.
- Evaluate the revised final bank once on the same sources and join results by
  exact source/task keys, preserving all denominators and failures.
- The revised learner's B1 is its own new snapshot. If final-test evolution beyond
  B1 is claimed, evaluate that snapshot too; do not relabel the old method's B1.
- Report the supplementary row as development-informed fixed-benchmark evidence.
  The underlying source cases remain disjoint from TRAIN and their targets remain
  excluded from skill training. Do not describe the new method as selected before
  all inspection of benchmark outcomes.
- Keep the original v0.23 study and all evaluated revisions identifiable.
  Do not select a favourable checkpoint using these cases or mix new-source
  method scores with old-source comparator scores.
- A fresh-source confirmation remains an optional later strengthening step,
  rather than a prerequisite for completing the current optimization run.
  Independent learning repetitions remain user-deferred.

This amends the future-evaluation priority, not the frozen training algorithm.
The bound training protocol is left unchanged so the live run remains consistent.
