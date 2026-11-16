Run 498c01b299 against https://zambo.dev/mcp (tool journal_log), started 2026-11-16T15:48:16.148119Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | fail | external effect count for the logical operation is 2, not 1: attempt 1 and the identical retry each produced a distinct public receipt for the operation |
| A2 | unproven | attempt 1 committed (effect count 1), and the mismatched retry was refused at the metering layer (payment_required) before it could execute, so the binding check was never exercised; no new effect occurred, and neither a binding rejection nor a silent execution was observed |
| A3 | fail | contract pass condition is the K-only leg: K-only recovery did not return the original committed outcome: the public record lookup by K returned 404 receipt_not_found (the /run/<K> page answers HTTP 200 with a Receipt not found title), and the K-keyed tool lookup returned no committed outcome or digest; run-id leg scored pass separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
