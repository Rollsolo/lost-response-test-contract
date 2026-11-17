Run 409891e807 against http://127.0.0.1:47310/mcp (tool create_ticket), started 2026-11-17T02:13:28.514342Z.

| Assertion | Outcome | Evidence |
|---|---|---|
| A1 | pass | external effect count for the logical operation is exactly 1 |
| A2 | pass | mismatched retry produced no new effect and was explicitly refused |
| A3 | unproven | contract pass condition is the K-only leg: no committed digest exists, so K-only recovery cannot be scored; run-id leg scored fail separately in the evidence |
| A4 | pass | every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state |
| A5 | unproven | the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K |
