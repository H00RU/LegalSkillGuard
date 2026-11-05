# Resource-bound continuation of the fixed B1/B8 TRAIN32 requests

Declared while the first phase is still running and before any new condition
is graded. This does not change a prompt, library, prediction, source selection,
sampling parameter, score or adoption criterion.

The fixed experiment has186 distinct logical requests, including17 usable
pre-existing responses, hence169 planned new EV generations. The first24 new
responses all finished normally; their B1/B8 mean output lengths were about2149
and1849 tokens, versus about1152 for the earlier screen's skill condition.
Thus the original45-minute phase may reach its dispatch limit before all fixed
requests are issued. No in-flight frozen file or original phase limit is edited.

## Only permitted continuation

1. Wait for the original service to terminate and confirm its real PID is gone.
   If it completes, no continuation is run. Otherwise verify that its failure is
   the declared dispatch-budget limit, not a transport/model/source-integrity
   failure. Preserve the entire first phase before doing anything else.
2. Check every recorded raw call and its exact request fingerprint. All requests
   actually issued must have retained terminal responses. Unknown or ambiguous
   execution is not treated as zero usage or as permission to retry.
3. Reuse every retained response, including incomplete or malformed responses,
   under identical messages/schema/generation. Do not regenerate a failed-quality
   answer. Generate only fixed requests proven never issued. The aggregate
   expected169 and hard176 new-call bounds across phases do not increase.
4. Use a fresh continuation Run ID and separately frozen source/protocol; retain
   aliases to true raw source paths and hashes. Same original service identity,
   model, libraries, cases, sampling and output limits must pass verification.
5. At most one additional30-minute actor phase, dispatch stopped at20 minutes
   with600 seconds for drain. Aggregate maximum actor time is75 minutes, with
   no new teacher or EC calls. This is resource completion of one fixed request
   set, not an extra hypothesis, seed, quality retry or independent replicate.
6. Grade only after the complete fixed prediction set has been saved. If this
   final resource phase remains incomplete, report incompleteness and stop;
   do not keep extending. Formal adoption and training still require confirmation.

All first-phase outcomes and actual costs remain in the record. Do not label a
multi-phase completion as having fit the original45-minute wall-time budget.
