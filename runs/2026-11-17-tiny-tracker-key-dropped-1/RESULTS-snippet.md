Run 626d87b0f2 against http://127.0.0.1:47320/mcp (tool create_ticket), started 2026-11-17T02:13:28.647629Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | fail | external effect count for the logical operation is 2, not 1 |
| A2 | fail | mismatched retry executed as a new call: effect count rose from 1 to 2, response class success |
| A3 | unproven | contract pass condition is the K-only leg: no committed digest exists, so K-only recovery cannot be scored; run-id leg scored fail separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
