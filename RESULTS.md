# Results

Recorded runs of the contract in CONTRACT.md. One row per assertion, per
system, per run. Outcome is one of: pass, fail, unproven. Raw outputs are
linked, not summarized. Failures are reported as observed.

Run of 2026-11-16: Zambo production (https://zambo.dev/mcp), target tool
journal_log, harness in fixtures/harness/, raw outputs in
runs/2026-11-16-zambo-1/ (summary.json is the scored record; the run was
rescored from its own raw outputs with the corrected counter, see
runs/2026-11-16-zambo-1/RESCORE-NOTE.md). Operation identity K and the
run-scoped session identity for each assertion are recorded in the raw
outputs.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | fail | External effect count 2, not 1: attempt 1 (response dropped) produced public receipt b49c66f5-5386-4bda-8bd6-2726bdfee7d1 and the identical retry produced a second distinct public receipt 2b8cefc9-72c0-415c-9525-71f6000679f9, each counted from the job's workflow snapshot and attributed through its public record. Raw: runs/2026-11-16-zambo-1/count_a1_final.json, runs/2026-11-16-zambo-1/a1_retry_identical.json | 2026-11-16 |
| A2 | Zambo | unproven | Attempt 1 committed (effect count 1, receipt e8f9f9b8-af48-45cb-8df0-5ce944346e05). The mismatched retry (one parameter changed: action) was refused at the metering layer with response class payment_required before it could execute, so the binding check was never exercised: no new effect occurred, and neither a binding rejection nor a silent execution was observed. Raw: runs/2026-11-16-zambo-1/a2_retry_mismatched.json, runs/2026-11-16-zambo-1/count_a2_final.json | 2026-11-16 |
| A3 | Zambo | fail | K-only leg failed: recovery holding only K (lr-op-498c01b299-a1) returned no committed outcome; the public record lookup by K returned 404 receipt_not_found and the K-keyed tool lookup returned no outcome or digest. Run-id leg passed separately: holding receipt id b49c66f5-5386-4bda-8bd6-2726bdfee7d1, resolution returned the unaltered record and recomputation matched (SHA-256 of the decoded canonical bytes equals the served output_hash sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970). Raw: runs/2026-11-16-zambo-1/a3_summary.json, runs/2026-11-16-zambo-1/a3_runid_leg_receipt.json, runs/2026-11-16-zambo-1/a3_konly_run_lookup.json | 2026-11-16 |
| A4 | Zambo | pass | Recorded retry response classes: A1 retry success, corresponding to a committed record (the retry's own second receipt, counted in A1), not a generic success with no record; A2 retry payment_required, an explicit non-success state naming the situation. Raw: runs/2026-11-16-zambo-1/summary.json | 2026-11-16 |
| A5 | Zambo | unproven | The 24 hour delayed leg cannot complete on the planting day. The A1 operation is planted with its commit timestamp recorded in runs/2026-11-16-zambo-1/a5_plant.json (due 2026-11-17T15:49:33Z); the delayed leg runs later with: python3 fixtures/harness/lost_response.py --delayed-leg runs/2026-11-16-zambo-1/a5_plant.json | 2026-11-16 |
