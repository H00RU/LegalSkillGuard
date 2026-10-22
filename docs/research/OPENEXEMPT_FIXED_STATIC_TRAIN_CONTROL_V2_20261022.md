# Fixed static TRAIN control: corrected ACE predecessor

Prospective execution-metadata rebase, 22 October 2026. The original protocol
in OPENEXEMPT_FIXED_STATIC_TRAIN_CONTROL_20261022.md is retained. The control
algorithm, worker, full128 TRAIN, 256 forecasts before grading, seed45, direct
actor, native and complete-output scoring, 4096-token cap and zero new teacher
calls do not change.

The original run01 waiter was cancelled while still in its Bash waiting stage.
It made no model call and created no control run directory. Its declared ACE
predecessor Run02 was gracefully stopped to fix failed-public-output evidence
delivery; a failed learner must not qualify as a full predecessor.

New run02 waits for the corrected exact-prefix ACE continuation Run03 to finish
all eight batches and complete terminal preservation. The same Python guard
still requires both actual full main and ACE completion, source/model identity,
the canonical training lock, no failure and all original data bindings. A
natural ACE completion permits execution; any failed ACE blocks it before
model calls. This is sequencing, not a new scientific control or TEST arm.

The static bank remains the original zero-case seven-record, 2411-token direct
publication, SHA4809c3b2fe336a682ad36544f036206f158c0890adad4e87bde6eb4fa6502321.
It is not revised after seeing TRAIN or ACE outcomes. The complete TRAIN control
can inform subsequent method development, but no sealed TEST content or outcome
can be consulted for optimization. Future independent repeats and ablations
remain required and are not replaced by this diagnostic.
