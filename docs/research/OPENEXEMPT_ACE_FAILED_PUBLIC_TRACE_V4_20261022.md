# ACE v4: preserve failed public output for TRAIN reflection

Prospective correction, 22 October 2026. The completed main Run03, its eight
first-forecast batches, labels, scoring and seven-record final bank are unchanged.
This correction concerns the external ACE task adaptation, not a new legal task.

## Verified defect and boundary

Pinned upstream `ace/ace_batch.py` at
`82709de050e1db6e6ef2f07bcb0393560b94992a` passes the generator's unchanged public
response to the reflector as its reasoning-trace input. The local v3 adapter
serialized an observation instead. That retained the complete public wrapper
for valid output, but a length/parse failure left only null parsed fields and a
disk path. The tool-free teacher could not read the original public failure.

Actual v3 Run02 B3 first forecasts 224 EV and 228 EV repeated final-answer claims
until the unchanged 8,192-token cap. Both original zero scores remain. No failed
224/228 reflection had been invoked at the operator stop. B1/B2's 348 saved
answer records were parse-valid. This omission cannot explain the already
observed B3 first-forecast deficit, which preceded any B3 feedback.

The exact ACE process was gracefully stopped at 23:04:02 CST after saving the
current call. It retained 294 native generations, 114 teacher responses and
both actual-terminal archives. The original 8B model was not stopped. The
not-yet-started static-control waiter was cancelled to prevent a failed
predecessor from triggering a misleading stage. The failed attempt is not
hidden or counted as a completed independent learning run.

## Minimal correction

Only a failed native observation gains `unparsed_public_output`, containing the
unchanged public response, and its actual finish reason. The reflector refuses
a failed observation without that evidence. Valid observations and all actor
prompts, schemas, generation settings, legal answers, zero-score rules and
native counters are unchanged. No JSON repair, partial-answer recovery, guessed
bullet ID, deduplication, longer cap, inference retry or fallback is introduced.
The original public failure is evidence for TRAIN diagnosis, not a legal answer.

## Exact last-prefix continuation, not best-checkpoint selection

Seed 45 continues the same learner from the unique last completed publication,
B2: 12 bullets, 1,214 tokens, SHA
`701ee9b2b2edaa8c48de2d13b187cd47cf0fb557c9fc6595c7a2b365bb095e52`.
The complete hash-bound receipt identifies all 1,301 original artifacts and
the prior source/configuration/freeze. This is not an additional independent
repeat, and initialization discloses the inherited prefix rather than claiming
an empty fresh start.

The 220 B1/B2 native origins and 102 original teacher responses are retained.
The complete 64 native B3 first forecasts may be reused only by identical full
request fingerprint. Their original aggregate scores must remain exact. No B3
TRAIN regeneration or teacher response is restored: the retired ten native
calls and twelve teacher responses remain charged to the stopped attempt.
B3 learning is rerun with fresh teachers after all continued batch forecasts
are saved. No future/TEST label is used. All previously observed data are TRAIN;
the continuation freeze explicitly marks prior performance exposure.

The correction's conditional branch was never visited in the completed B1/B2
prefix. Source and receipt checks enforce that fact. Independent seeds 145/245
start from empty under the same corrected algorithm; only seed 45 has this
explicit operational lineage. Final reporting must separate restored origins,
fresh continuation calls and retired work, and preserve the original failed run.

## Remaining study

Keep eight batches of the same 128 TRAIN sources, one frozen local 8B, three
maximum native TRAIN reflection rounds, one batch ADD curator and the existing
8,192-token memory cap. Continue full fair ACE learning, then the unchanged
zero-case static TRAIN control, declared learning repeats and ablations.
Replace unstarted frozen profiles prospectively when their source bindings are
stale; never edit an existing frozen manifest in place. The original static
waiter is stopped and must not be mistaken for a still-active future stage.
All actual banks and the full analysis matrix must still be frozen before any
real TEST prediction. No validation set, new model or paid service is added.
