# Diagnosis: where the A5 recovery property breaks (2026-11-17)

Question: run 2026-11-16-zambo-1 scored A5 fail (RESULTS.md): after
the 24-hour delay, K-only recovery returned no committed outcome and
same-K retries executed fresh. This run pins down where the property
breaks, comparing like with like: same harness, same Zambo adapter,
same target tool (journal_log), same argument template
(fixtures/harness/config.zambo.json), K carried as job_id and as
inputs.operation. Method: diag_probe.py and diag_recheck.py in this
folder; every claim below names its raw output file.

Diagnosis plant: K lr-op-a3f246d1fb-diag, session
lr-a3f246d1fb-diag, planted 2026-11-17T16:29:01Z. Attempt 1 committed:
external effect count 1 (count_diag_after_attempt1.json), receipt
141f1588-f277-48fc-999a-ac6814d760d2, committed digest
sha256:826aa323ddac9788a7387e1b3f22f5be2139e2b88b8ed4ae3012806df4625f0d.

## What works (observed)

- The committed record persists and resolves by its server-issued
  receipt id. Minutes after today's plant: HTTP 200, digests served,
  harness recomputation matched (diag_runid_record.json,
  diag_record_inspection.json). At 24 hours on run 1: resolution
  returned the unaltered record, the served digest equaled the
  committed digest sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970,
  recomputation matched (runs/2026-11-16-zambo-1/a5_delayed_runid_receipt.json).
  The receipt store does not prune inside the contract window.
- The operation's record is enumerable in the caller's session
  namespace at short range: continuity_get_recent with the original
  session id, from the planting client, listed the planted receipt
  minutes after commit (diag_session_continuity_get_recent.json,
  diag_session_read_summary.json; same observation in run 1's
  enum_a1_final_continuity_get_recent.json). That path requires the
  session identity; the contract's K-only recovery caller holds
  only K.

## What breaks (observed)

1. No direct K addressability, at any probed range. GET
   /api/v2/receipt/<K>/verify returns HTTP 404 with body
   {"error":"receipt_not_found", ..., "hint":"Check the id; receipt
   ids are UUIDs from _meta[\"dev.zambo/receipt\"].id"} and GET
   /run/<K> answers HTTP 200 with a "Receipt not found" page.
   Observed at: ~44 seconds after commit (diag_konly_run_lookup.json,
   plant 16:29:01Z, probe 16:29:45Z), ~169 seconds after commit
   (diag_recheck_konly_run_lookup.json), minutes after commit in
   run 1's A3 and run 2's A3 (2026-11-16), and 24 hours after commit
   in run 1's delayed leg (a5_delayed_konly_run_lookup.json). The
   public record's only address is the server-issued receipt UUID;
   the 404 body states that rule itself.
2. The K-keyed tool lookup returns a stream, not the outcome.
   continuity_get_recent with K as the only identifier answers
   success with the caller's recent-events stream: today, 20 events
   spanning 6 tools of unrelated activity on the shared network
   (diag_konly_continuity_get_recent.json). The planted operation's
   event was present only because the plant was seconds old and
   same-network; its entry carries tool, status, timestamp and a
   receipt id, no outcome and no digest, and nothing in the stream
   is keyed by K (the string K appears in the body only inside the
   payment block, echoing the session id the caller itself
   supplied). The committed digest appears nowhere in the response
   (diag_konly_summary.json), and the same held at the ~169-second
   recheck (diag_recheck_summary.json). At 24 hours the same lookup
   returned 24 receipt ids with the operation's receipt not among
   them (runs/2026-11-16-zambo-1/a5_delayed_extra.json). In run 1's
   A3 the same call was refused payment_required before returning
   anything. In no run, at any range, did a K-only path return the
   committed outcome or its digest.
3. K is not stored in the committed record. The string K appears
   nowhere in the planted operation's public record, checked over
   the full record JSON and the decoded canonical bytes, in run 1
   and again today (diag_record_inspection.json). The arguments
   carrying K (job_id, inputs.operation) are committed only through
   the receipt's input_hash. There is no K field on the public
   record for a lookup to key on.
4. No same-K execution recognition, wherever a retry reaches
   execution. Run 1 A1, minutes after commit: identical retry
   executed fresh, effect count 1 to 2. Run 2 A2, minutes: the
   modified-parameter retry executed fresh, count 1 to 2. Run 1 A5,
   24 hours: identical and modified-parameter delayed retries both
   executed fresh, count 2 to 4. In the diagnosis run both retries
   were refused at the metering layer (payment_required) before
   executing (diag_retry_identical.json, diag_retry_mismatched.json;
   count stayed 1), so recognition was not exercised today. No
   observed response in any run returns the original outcome or a
   conflict for a same-K retry.

## Time dimension

K-only recovery fails at the earliest probed point (~44 seconds
after commit) and at every later probed point: ~169 seconds (this
run), minutes (runs 1 and 2, A3), and beyond 24 hours (run 1, A5).
No probed range exists in which it works; the property is absent
from the start, not lost over the window. This run does not claim a
24-hour re-test of the diagnosis plant: its delayed leg is due
2026-11-18T16:29:01Z (diag_plant.json) and is part of the armed
re-test procedure recorded with this run.

## Root cause

From the observed responses: the recovery record is keyed only by
the server-issued receipt UUID, K is not a field of the committed
record, and no probed surface resolves K to the record; executions
carrying the same K are not recognized as the same operation.
Inference, labeled as such: the break is the absence of a
K-to-outcome index and of same-K execution recognition, not record
retention. The contract's stated A5 failure basis (a record store
pruning faster than clients can retry) is contradicted for the
receipt record itself, which outlives the window. Whether
production keeps any internal K-keyed record with a shorter
lifetime is not observable from outside; every externally
observable path behaves as if no K binding exists at any probed
time.

## Standing of prior results

Nothing here changes any recorded score. RESULTS.md's A5 fail for
run 2026-11-16-zambo-1 stands exactly as observed. This diagnosis
adds no new protection evidence (today's retries were meter-refused
before executing); the protection failure stands on run 1 (A1 and
A5) and run 2 (A2).
