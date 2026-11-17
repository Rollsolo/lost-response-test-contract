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

Run of 2026-11-16 (adapter refactor reproduction): Zambo production
(https://zambo.dev/mcp), target tool journal_log, raw outputs in
runs/2026-11-16-zambo-2/. This run was executed through the adapter
interface in fixtures/harness/adapters/ (the harness refactor that
separates the scoring driver from the per-system adapter; the Zambo
adapter is the original harness behavior, moved unchanged) to prove
the refactor before any other system is run through it. A1, A3, and
A4 reproduce the first run exactly. A2 differs, and the difference
is in the observation, not the code: in the first run the mismatched
retry was refused at the metering layer before it could execute, so
the binding check was never exercised and A2 was unproven; in this
run the mismatched retry executed, so A2 is scored on the exercised
behavior and recorded as observed.

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | Zambo | fail | External effect count 2, not 1: attempt 1 (response dropped) produced public receipt 6b7d958a-f31b-47d1-8aef-09a868e2e865 and the identical retry produced a second distinct public receipt 1fb3a09e-1029-464c-9872-fb02fcc35a65, each counted from the job's workflow snapshot and attributed through its public record. Raw: runs/2026-11-16-zambo-2/count_a1_final.json, runs/2026-11-16-zambo-2/a1_retry_identical.json | 2026-11-16 |
| A2 | Zambo | fail | Attempt 1 committed (effect count 1, receipt 0c555b90-97fc-4763-a3c6-daa9fe1765dd). The mismatched retry (one parameter changed: action) executed as a normal new call: the effect count rose to 2 (second receipt 5ab9b4c5-3ec4-4598-81c9-8e9f428a17a7), the response class was success, and no binding rejection was returned. This exercises the check the first run could not reach (there the retry was refused with payment_required before executing, and A2 was recorded unproven). Raw: runs/2026-11-16-zambo-2/a2_retry_mismatched.json, runs/2026-11-16-zambo-2/count_a2_final.json | 2026-11-16 |
| A3 | Zambo | fail | K-only leg failed: recovery holding only K (lr-op-f63fe15895-a1) returned no committed outcome; the public record lookup by K returned 404 receipt_not_found and the K-keyed tool lookup returned no outcome or digest. Run-id leg passed separately: holding receipt id 6b7d958a-f31b-47d1-8aef-09a868e2e865, resolution returned the unaltered record and recomputation matched (SHA-256 of the decoded canonical bytes equals the served output_hash sha256:70a8dacb73738cf7e9d62f90e17d40191f42f7360fcb344d78a65753a2cd7fc1). Raw: runs/2026-11-16-zambo-2/a3_summary.json, runs/2026-11-16-zambo-2/a3_runid_leg_receipt.json, runs/2026-11-16-zambo-2/a3_konly_run_lookup.json | 2026-11-16 |
| A4 | Zambo | pass | Recorded retry response classes: A1 retry success, corresponding to a committed record (the retry's own second receipt, counted in A1); A2 retry success, corresponding to a committed record (the mismatched retry's own second execution, counted in A2). Neither is a generic success with no committed record. Raw: runs/2026-11-16-zambo-2/summary.json | 2026-11-16 |
| A5 | Zambo | unproven | The 24 hour delayed leg cannot complete on the planting day. The A1 operation is planted with its commit timestamp recorded in runs/2026-11-16-zambo-2/a5_plant.json (due 2026-11-17T20:33:31Z); the delayed leg runs later with: python3 fixtures/harness/lost_response.py --delayed-leg runs/2026-11-16-zambo-2/a5_plant.json | 2026-11-16 |

Runs of 2026-11-17: tiny-tracker 0.1.0 (npm
@mcp-write-safety/tiny-tracker), a small open-source teaching MCP
server published by IsoKron, run locally on 127.0.0.1 in three builds:
the correct build and two builds with one deliberate defect each.
Target tool create_ticket with K as its idempotency_key; the external
effect counter is the tiny-tracker backend's REST record, read
directly (GET /tickets?title_prefix=<K>), one ticket per execution.
Executed through fixtures/harness/adapters/tiny_tracker.py (adapter
0.1.0) at contract and harness commit 92bf1ba. Fault point:
client-side discard after the full response was read. tiny-tracker
issues no signed receipts and carries no committed result digest, so
A3 cannot reach digest equality on any build; the run-id leg resolved
the record (HTTP 200) and the driver scored that leg fail only because
no digest is served. Limits and per-run details are in each run
directory's RUN-NOTES.md.

Correct build, raw outputs in runs/2026-11-17-tiny-tracker-correct-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (correct build) | pass | External effect count 1: attempt 1 (response dropped) created ticket T-1; the identical retry answered success with replayed: true and ticket T-1, and the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-correct-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-correct-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (correct build) | pass | Attempt 1 committed (T-2). The retry with one parameter changed (priority 3 to 4) was refused: isError, code idempotency_key_reused, outcome not_applied; the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-correct-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-correct-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (correct build) | unproven | Holding only K, both paths returned the original ticket T-1: list_tickets by title prefix K (a caller convention, not a K index) and the same-key replay (replayed: true, count 1 before and after). Neither carries a digest, and the record carries no committed result digest, so digest equality cannot be shown. Run-id leg: T-1 resolved with HTTP 200; scored fail by the driver because no digest is served. Raw: runs/2026-11-17-tiny-tracker-correct-1/a3_summary.json, runs/2026-11-17-tiny-tracker-correct-1/a3_konly_replay_create_ticket.json, runs/2026-11-17-tiny-tracker-correct-1/a3_runid_leg_receipt.json | 2026-11-17 |
| A4 | tiny-tracker (correct build) | pass | Retry response classes: A1 retry success (a replay naming the committed T-1); A2 retry tool_error:idempotency_key_reused, an explicit refusal. Raw: runs/2026-11-17-tiny-tracker-correct-1/summary.json | 2026-11-17 |
| A5 | tiny-tracker (correct build) | unproven | Pending, due 2026-11-18T02:13:28Z. The build is left running on 127.0.0.1 for the delayed leg; it keeps its key record in memory, so a restart before then loses it. Plant: runs/2026-11-17-tiny-tracker-correct-1/a5_plant.json; delayed leg: python3 fixtures/harness/lost_response.py --delayed-leg runs/2026-11-17-tiny-tracker-correct-1/a5_plant.json | 2026-11-17 |

Build with --defect idempotency-key-dropped, raw outputs in
runs/2026-11-17-tiny-tracker-key-dropped-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (idempotency-key-dropped) | fail | External effect count 2, not 1: attempt 1 (response dropped) created T-1 and the identical retry created T-2, answering success with replayed: false. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-key-dropped-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (idempotency-key-dropped) | fail | Attempt 1 committed (T-3). The retry with priority changed executed as a new call: the count rose from 1 to 2 (T-4), response class success, no binding rejection. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-key-dropped-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (idempotency-key-dropped) | unproven | Scored unproven by the driver because no committed digest exists. Observed: list_tickets by title prefix K returned two tickets (T-1, T-2), and the same-key replay executed again, creating T-5 (count 2 before, 3 after); no path returned the original outcome as such. Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/a3_summary.json, runs/2026-11-17-tiny-tracker-key-dropped-1/a3_konly_replay_create_ticket.json | 2026-11-17 |
| A4 | tiny-tracker (idempotency-key-dropped) | pass | Retry response classes: A1 retry success and A2 retry success, each corresponding to a ticket that retry created (counted in A1 and A2). Raw: runs/2026-11-17-tiny-tracker-key-dropped-1/summary.json | 2026-11-17 |
| A5 | tiny-tracker (idempotency-key-dropped) | unproven | Not run: the build was stopped after A1 to A4, and tiny-tracker keeps its record in memory. A5 runs on the correct build only. | 2026-11-17 |

Build with --defect idempotency-key-ignores-args, raw outputs in
runs/2026-11-17-tiny-tracker-ignores-args-1/:

| Assertion | System | Outcome | Evidence | Date |
|---|---|---|---|---|
| A1 | tiny-tracker (idempotency-key-ignores-args) | pass | External effect count 1: attempt 1 (response dropped) created T-1; the identical retry answered success with replayed: true and T-1. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/count_a1_final.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a1_retry_identical.json | 2026-11-17 |
| A2 | tiny-tracker (idempotency-key-ignores-args) | fail | Attempt 1 committed (T-2, priority 3). The retry with priority 4 was not refused: it answered success with replayed: true and ticket T-2, from a cache keyed by the key alone; no ticket with priority 4 exists and the count stayed 1. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/a2_retry_mismatched.json, runs/2026-11-17-tiny-tracker-ignores-args-1/count_a2_final.json | 2026-11-17 |
| A3 | tiny-tracker (idempotency-key-ignores-args) | unproven | Holding only K, both paths returned T-1 (the replay with replayed: true, count 1 before and after); no digest is carried, so digest equality cannot be shown. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/a3_summary.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a3_konly_replay_create_ticket.json | 2026-11-17 |
| A4 | tiny-tracker (idempotency-key-ignores-args) | pass | Scored by the driver from the classes success (A1 retry, replay of T-1) and success (A2 retry). Recorded for joint review, not resolved: the A2 retry's success names T-2, a committed record of (K, A), not of the (K, A') it was asked for. Raw: runs/2026-11-17-tiny-tracker-ignores-args-1/summary.json, runs/2026-11-17-tiny-tracker-ignores-args-1/a2_retry_mismatched.json | 2026-11-17 |
| A5 | tiny-tracker (idempotency-key-ignores-args) | unproven | Not run: the build was stopped after A1 to A4, and tiny-tracker keeps its record in memory. A5 runs on the correct build only. | 2026-11-17 |
