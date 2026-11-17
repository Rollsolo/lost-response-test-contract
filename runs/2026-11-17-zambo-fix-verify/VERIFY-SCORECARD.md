# A5 fix live verification, 2026-11-17 (short range)

The crew published the lost-response recovery fix to Zambo production
on 2026-11-17. This run verifies the fix live, minutes after
publication, against a fresh operation planted the way the harness
plants: K lr-op-a026e944d8-fv, session lr-a026e944d8-fv, target tool
journal_log, arguments from fixtures/harness/config.zambo.json.
Committed: receipt 1005ed7d-c070-412c-82d3-24dcf70473c7, digest
sha256:4fab4e75ac1d85f9e55a4e62fbe9c1bb460a06f36f3933019bb41ce582f145d2,
external effect count 1 (count_fv_after_attempt1.json), public-record
recomputation matched (fv_runid_record.json).

Triple-verify standard (Brennan's order, 2026-11-17 12:06 EST):
every load-bearing claim below is read three independent ways; all
three agree unless a disagreement is stated.

## (a) Plant: PASS

Attempt 1 committed on the first call (response class success,
fv_attempt1_plant.json); the workflow snapshot attributes exactly
one journal_log execution to the operation.

## (b) K-only recovery: PASS, triple-verified

A recovery caller holding only K (no run id, response, result, or
digest) recovered the saved outcome, the receipt id, and the
committed digest. Three reads agree on outcome and digest:

- R1, harness recover_by_key (fv_a3_konly_run_lookup.json,
  fv_a3_konly_continuity_get_recent.json): the direct lookup returns
  HTTP 200 with output_hash equal to the committed digest; the
  K-keyed continuity_get_recent call (K as the only identifier)
  returns status "found" with operation_key = K, receipt_id =
  1005ed7d-c070-412c-82d3-24dcf70473c7, output_digest equal to the
  committed digest, and the original outcome.
- R2, direct python-requests GET /api/v2/receipt/<K>/verify
  (fv_R2_direct_verify_by_key.json): HTTP 200, receipt id
  1005ed7d-c070-412c-82d3-24dcf70473c7, output_hash equal to the
  committed digest, verification_status "verified".
- R3, public-record read of the returned receipt with the harness's
  own recomputation (fv_R3_returned_receipt_record.json): HTTP 200,
  digests equal, recomputation "matched" (SHA-256 of the decoded
  canonical bytes equals the served output_hash).

Two scope observations, recorded exactly:

- The HTML page GET /run/<K> still renders a "Receipt not found"
  title (page_title_not_found in fv_a3_konly_run_lookup.json). The
  JSON verify endpoint resolves K; the human page does not.
- The fix is forward-looking. Operations committed BEFORE the fix
  have no K binding: run 1's K (lr-op-498c01b299-a1) and the
  diagnosis plant's K (lr-op-a3f246d1fb-diag) still return HTTP 404
  on the direct lookup, and their K-keyed continuity calls return
  the generic recent-events stream with no recovery record
  (legacy_k_probe.py, legacy_k_summary.json). A delayed leg re-run
  on either pre-fix plant would still fail its K-only leg. The
  post-fix delayed leg therefore runs on a new plant:
  runs/2026-11-17-zambo-2/.

The session-scoped continuity read with the planting caller handle
(fv_pathC_continuity_stable_handle.json) returned the committed
receipt id inside the recent-events stream but not the digest; the
digest-bearing recovery paths are the two K-keyed paths above.

## (c) Identical retry: PASS, triple-verified no-new-execution

- Response body (fv_retry_identical.json): success with
  idempotent_replay: true, status "replayed", the original outcome,
  output_digest equal to the committed digest, and receipt_id =
  1005ed7d-c070-412c-82d3-24dcf70473c7 (the original receipt).
- Workflow snapshot attribution (count_fv_after_identical.json):
  effect count stays 1; the only journal_log execution receipt in
  the job snapshot is the original.
- Session receipt stream (fv_stream_after_identical.json): contains
  the committed receipt; no second execution receipt for the
  operation appears.

## (d) Modified-parameter retry: PASS, triple-verified refusal

- Response body (fv_retry_mismatched.json): HTTP 409, error code
  idempotency_conflict, "This operation key is already bound to
  different parameters. No journal entry was added; use a new
  job_id for a different operation.", executed: false, and a
  refusal receipt issued for the refused call itself:
  8b0b9095-f8a7-46fd-9639-e0a743d035ba.
- The refusal receipt's public record
  (fv_refusal_receipt_8b0b9095-f8a7-46fd-9639-e0a743d035ba.json):
  HTTP 200, tool journal_log, step status
  rejected_before_execution, recomputation matched.
- Effect count (count_fv_final.json): unchanged at 1; the final
  snapshot's remaining children are the workflow_close and
  continuity_get_recent read-path receipts, each attributed through
  its public record, none a journal_log execution.

## (e) Regression sanity: PASS

- initialize HTTP 200; tools/list HTTP 200 with 37 default tools
  (fv_00_initialize.json, fv_00_tools_list.json).
- Ordinary journal_log without the operation marker remains
  appendable (ordinary_probe.py, fv_ordinary2_summary.json): a
  complete call with its own job_id and no inputs.operation marker
  appended (status "logged", receipt
  3cecd089-946c-4d0a-ac93-b1ed20bf3928), and an identical second
  unmarked call appended a second entry with its own receipt
  (eb3b1ec2-8034-4761-9ab1-e9a3c525f37c) instead of replaying.
- The first ordinary probe (fv_ordinary_journal_log.json) omitted
  two schema-required arguments (job_id, executor_identity) and was
  refused invalid_tool_arguments; that refusal is a probe defect,
  recorded as such, and is superseded by the corrected probe above.
- Every call in this run carried a receipt whose public record
  resolves HTTP 200 with recomputation matched.

## Standing of prior results

Nothing here changes any recorded score. Run 2026-11-16-zambo-1's
A5 FAIL stands exactly as observed. The formal post-fix A5 delayed
leg runs on runs/2026-11-17-zambo-2/ (planted 2026-11-17T17:12:46Z,
due 2026-11-18T17:12:46Z).
