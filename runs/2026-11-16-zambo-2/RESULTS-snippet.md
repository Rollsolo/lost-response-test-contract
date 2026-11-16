Run f63fe15895 against https://zambo.dev/mcp (tool journal_log), started 2026-11-16T20:32:58.193547Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | fail | external effect count for the logical operation is 2, not 1 |
| A2 | fail | mismatched retry executed as a new call: effect count rose from 1 to 2, response class success |
| A3 | fail | contract pass condition is the K-only leg: K-only recovery did not return the original committed outcome; the direct record lookup by K returned not found and no K-keyed lookup returned the committed digest; run-id leg scored pass separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
