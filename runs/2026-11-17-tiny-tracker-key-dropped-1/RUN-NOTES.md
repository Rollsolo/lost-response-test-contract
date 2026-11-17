# Run notes: tiny-tracker --defect idempotency-key-dropped

Pinned versions: contract and harness at zambodotdev/lost-response-test-contract
commit 92bf1ba (CONTRACT.md unchanged, still marked draft); adapter
fixtures/harness/adapters/tiny_tracker.py version 0.1.0, added with these
runs; system under test npm @mcp-write-safety/tiny-tracker 0.1.0, run
locally with `tiny-tracker all`, bound to 127.0.0.1 only; Python 3.11,
requests 2.34.2.

Every file in this directory except this note was written by the driver
(lost_response.py) and the adapter, unedited.

Build: `--defect idempotency-key-dropped` (create_ticket accepts
idempotency_key but never sends it to the backend). Start command:
`TRACKER_BACKEND_TOKEN=<fresh local test token> npx -y -p @mcp-write-safety/tiny-tracker@0.1.0 tiny-tracker all --port 47320 --backend-port 47321 --defect idempotency-key-dropped`

## Scores as written by the driver

A1 fail, A2 fail, A3 unproven, A4 pass, A5 unproven (not run).

- A1: K lr-op-626d87b0f2-a1. Count 1 after the dropped attempt (T-1), 2
  after the identical retry (T-1, T-2). The retry answered success,
  `replayed: false`, "Created ticket T-2".
- A2: K lr-op-626d87b0f2-a2, priority 3 changed to 4. Count rose from 1
  (T-3) to 2 (T-3, T-4); the retry answered success.
- A3: list_tickets by prefix K returned two tickets (T-1, T-2); the
  same-key replay executed again and created T-5 (count 2 before, 3
  after; a3_konly_replay_create_ticket.json). No path carries a digest,
  so the driver scored unproven; the replay path did not return the
  original outcome.
- A4: both retries `success`, each matching a ticket it created.

## A5

Not run on this build: it was stopped after A1 to A4. tiny-tracker keeps
its data and key record in memory, so a restarted build has no record of
the planted operation. A5 is run on the correct build only.

## Limits, stated plainly

- Local run against our own sample server. tiny-tracker is a teaching
  server published by the same people who ran this test (IsoKron); it is
  not a production system.
- The counter is the tiny-tracker backend's REST record, read directly
  (GET /tickets?title_prefix=<K>), not through the MCP server. The backend
  is on 127.0.0.1 and needs the bearer token it was started with (the token
  is not in any output), so a third party recounts from the published raw
  listings (backend_*_listing.json), not from a live public record.
- Fault point: client-side discard. The full response was read off the
  wire (so the call had finished and the ticket was committed), then the
  body was discarded; only transport metadata is kept in the
  *_attempt1_dropped.json files.
- No digests: tiny-tracker issues no signed receipts and carries no
  committed result digest. A ticket's ETag is its integer version, a
  validator, not a digest (recorded under `validators` in
  a3_runid_leg_receipt.json). The driver therefore scores A3 unproven
  ("no committed digest exists"), and it scores the run-id leg "fail"
  because its pass rule requires a served digest: the record itself
  resolved (HTTP 200), so that "fail" means "no digest to check", not
  "record not found". The run-id leg's `note` text is the driver's fixed
  text written for Zambo (AER-1 Sections 6 and 9) and does not describe
  this system.
- Recovery paths (files named a3_konly_*.json by the adapter):
  list_tickets by title prefix K (works only because the caller put K in
  the title; tiny-tracker has no lookup keyed by the idempotency key),
  then the same-key replay with the caller's own original arguments (K
  plus A; a write call), with the counter read before and after. No
  direct lookup by K (GET /tickets/<K>) was tried; it is a 404 by design
  and would make the driver score A3 fail.
- tiny-tracker keeps its data and its idempotency-key record in memory:
  a restart loses both.
