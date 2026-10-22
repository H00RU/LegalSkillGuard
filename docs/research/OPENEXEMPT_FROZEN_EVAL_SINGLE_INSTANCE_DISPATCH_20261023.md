# Frozen evaluation: prospective single-instance request scheduling

23 October 2026. This amendment concerns inference scheduling only. It does not
change a learner, library, source selection, actor, schema, decoder, score,
endpoint, statistical contrast or per-answer generation setting. No actual TEST
content or outcome was consulted. No current training, queued TRAIN control,
model service or previously frozen training profile is changed by this document.

## Reason and scope

The declared16-arm,128-source EC/EV matrix contains4,096 logical predictions.
The completed main run's1,158 generations span93,209.27 seconds of recorded
input-file-to-raw-file intervals, about80.49 seconds per generation. Applying
that observed mean to4,096 unreused requests gives a91.58-hour serialization
scenario. This is not a TEST latency measurement, GPU-busy-time integral,
remaining-work ETA, or guarantee of a concurrency speedup. Libraries, lengths,
request reuse and serving throughput may differ.

The isolated formal evaluator therefore supports either the original single
request worker or four request workers against one frozen8B model instance.
Four workers require an explicit configuration declaration and captured
`--max-num-seqs 4` environment. The complete final matrix, this protocol, actual
libraries, evaluator and serving environment must be frozen before the first
real TEST prediction. The full-bank/provenance/16-arm/128-source gates remain.

## Required execution semantics

- Model revision, dtype, public inputs, direct/ACE actor implementations,
  thinking, temperature, top-p/top-k, fixed evaluation seed45,32,768-token
  context and8,192-token output cap remain common and unchanged.
- Each task retains the original deterministic rotating arm order. Independent
  task rows may be dispatched together, with at most four active workers.
  Completion order does not change saved per-arm source order.
- A lock keyed by complete messages, schema and generation guards the original
  actor's cache lookup, generation, insertion and alias recording. Identical
  requests retain one raw origin, including across concurrent source rows.
  They are not additional independent predictions or a resampling opportunity.
- Each original transport call owns its native client and immutable raw log.
  Progress-file updates are serialized. There is no new teacher, solver,
  response repair, truncation, answer-dependent retry or inference fallback.
- Any failure cancels queued work, prevents later calls, waits for in-flight
  requests to preserve their actual records, and retains a failure terminal.
  No partial matrix is graded. Every planned prediction must precede grading.
- Concurrent serving need not reproduce a serial GPU execution bit-for-bit.
  Results use the one prospectively frozen common schedule, not a choice of
  serial/concurrent outcomes, seeds, banks or successful responses.

## Deployment boundary

Current training and both queued TRAIN stages keep the original service and
source bindings. Do not restart that service to test this evaluator. Only after
all required training has actually completed and been preserved may a separate
final-evaluation environment be captured. Any serving transition first requires
complete on-disk recovery assets and preservation of the original deployment.
No extra model instance is authorized or added. A bounded TRAIN-only transport
check may verify the new execution environment without choosing the mode on
legal scores. Actual throughput and costs must be measured and reported; the
code's availability is not evidence that acceleration has been deployed or
that the full final matrix is ready.
