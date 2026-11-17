# MWS-RETRY-2 scorecard: Zambo production, tool journal_log

Run of 2026-11-17, executed reciprocally for the MCP issue 3394
thread: zambodotdev offered (comment 6934532293) to run the
MWS-RETRY-2 test method (MWS 0.9, isokron-ai/mcp-write-safety,
spec/mws.md) against Zambo and post the results in that thread;
rafe-walker accepted (comment 6935542605). This directory is the raw
record. The contract harness run in this same directory
(summary.json) supplies the A1 to A5 scores on the same operations;
the MWS steps below were driven with the harness's own Zambo adapter
and the shared external effect counter (fixtures/README.md), so the
counts are the same counts.

## Scope and key carrier, stated plainly

MWS-RETRY-2 applies when a write tool accepts an idempotency key.
The write-tool manifest posted on the thread earlier the same day
(comment 6942229307, 2026-11-17T07:58Z) recorded that no tool on
Zambo's default surface accepted a caller-supplied idempotency key.
That was true when written. Later the same day, the production
recovery fix (the subject of runs/2026-11-17-zambo-fix-verify/) bound
journal_log calls that carry an operation marker: the caller-supplied
operation key K is carried as the journal_log job_id and as
inputs.operation, scoped by the session id. This run tests
journal_log under that binding, and only journal_log. The other
write tools on the surface still accept no caller key, so
MWS-RETRY-2 does not apply to them and this run does not test them.

Trace: one committed journal_log execution leaves one durable public
receipt; the count is read from the job's workflow snapshot, each
child attributed through its public record, exactly as the harness
counts. Steps were run 2026-11-17T20:57Z to 21:05Z.

## Step (a), black-box record: held

Fresh K lr-op-ef631377b2-mwsa, answer received before the repeat.
First call: success, receipt 767bd78f-d41b-4c2c-aee9-22d7aa6001fb.
Repeat, same key and same arguments: success with
idempotent_replay: true, status "replayed", naming the same receipt
767bd78f and the first call's output digest
sha256:919f5b8b108018e54c4471a85bceef8b05902e9e1fe1537383c815561280632c.
External effect count for the operation: 1.
Raw: mws_step_a_blackbox.json, count_mwsa_final.json.

## Step (b), same black-box record: held

Same write under a new key lr-op-ef631377b2-mwsb (arguments identical
except the key itself, which the declared carrier embeds): success,
not a replay, applied as its own write (receipt
6304e38a-ad6c-43d2-8067-398b852146f2, count 1 for its operation).
Treated as a new write, as the second clause requires.
Raw: mws_step_b_newkey.json, count_mwsb_final.json.

## Step (c), same black-box record: held

From the harness run in this directory (A2): K lr-op-d99166563b-a2
reused with one argument changed (action). Refused as a tool
execution error, code idempotency_conflict ("This operation key is
already bound to different parameters. No journal entry was added"),
which is the refusal form the test method expects where the key is a
tool argument. No new effect; the count stayed 1.
Raw: a2_attempt1_dropped.json, a2_retry_mismatched.json,
count_a2_final.json.

Black-box record for steps (a), (b), (c): held. All three forced
their condition and held.

## Proxy-assisted step, own record: held

Run in the contract's client-side-drop form (the harness A1 leg):
attempt 1 with K lr-op-d99166563b-a1 committed (count 1, receipt
2e9ebf1f-5743-48de-a34b-5b3584c4c102) and its response was discarded
client-side after the effect and the completion record committed;
the caller held no part of the answer. The repeat gave the first
call's outcome: idempotent_replay: true, the original receipt and
outcome, output digest
sha256:b57197d5333af492c73260784de351c587545b6837ddab98500386714d931b87,
and the trace still counts exactly one application. Form note,
recorded honestly: Zambo is a hosted service and there is no
interposer in a path we control between its MCP endpoint and its
store, so the cut was made where the contract's common setup makes
it, between the server and the caller, after commit. The verdict
follows the proxy-assisted rule for a repeat that gives the outcome
with one application: held, without the "outcome not established"
note, because the outcome was established and given.
Raw: a1_attempt1_dropped.json, a1_retry_identical.json,
count_a1_after_attempt1.json, count_a1_final.json.

## Step (d), simultaneous repeat, own record: not observed

10 pairs stated in the record; all 10 pairs overlapped. No pair
applied the write more than once, so no violation was observed.
In 5 pairs one call succeeded and the simultaneous twin answered as
a replay (idempotent_replay: true). In 3 pairs one twin was refused
at the metering layer (payment_required, a refusal that says nothing
about the write itself) before it could commit, and the other
applied the write once. In 2 pairs both twins were refused at the
metering layer and neither applied the write; those pairs did not
force the condition and are recorded, not counted as passes. Step
(d) can give only violated or not observed: not observed.
Raw: mws_step_d_simultaneous.json, count_mwsd*_final.json.

## Step (e) and its crash form, own records: not tested

The declaration gives no means to stop and start the hosted server,
so under the test method's own rule both give not tested. The
contract's A5 assertion (recognition after a 24 hour delay, with
protection against fresh execution inside the window) is the nearest
analogue in the shared contract; it is planted for this run (K
lr-op-d99166563b-a1, due 2026-11-18T20:58:24Z, a5_plant.json) and is
scored under the contract in RESULTS.md when its delayed leg runs,
not under this requirement.

## Contract scores from the same run (summary.json)

A1 pass (effect count exactly 1). A2 pass (mismatched retry refused,
no new effect). A3 pass (K-only recovery returned the original
committed outcome; recovered digest equals committed digest
sha256:b57197d5333af492c73260784de351c587545b6837ddab98500386714d931b87;
the run-id leg also passed). A4 pass (A1 retry success naming the
committed record; A2 retry an explicit non-success state). A5
unproven on the planting day; delayed leg due 2026-11-18T20:58:24Z.
