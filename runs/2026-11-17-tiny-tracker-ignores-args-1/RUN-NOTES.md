# Run notes: tiny-tracker --defect idempotency-key-ignores-args

Pinned versions: contract and harness at zambodotdev/lost-response-test-contract
commit 92bf1ba (CONTRACT.md unchanged, still marked draft); adapter
fixtures/harness/adapters/tiny_tracker.py version 0.1.0, added with these
runs; system under test npm @mcp-write-safety/tiny-tracker 0.1.0, run
locally with `tiny-tracker all`, bound to 127.0.0.1 only; Python 3.11,
requests 2.34.2.

Every file in this directory except this note was written by the driver
(lost_response.py) and the adapter, unedited.

Build: `--defect idempotency-key-ignores-args` (create_ticket answers
any call with a seen idempotency_key from a cache keyed by the key alone).
Start command:
`TRACKER_BACKEND_TOKEN=<fresh local test token> npx -y -p @mcp-write-safety/tiny-tracker@0.1.0 tiny-tracker all --port 47330 --backend-port 47331 --defect idempotency-key-ignores-args`

## Scores as written by the driver

A1 pass, A2 fail, A3 unproven, A4 pass, A5 unproven (not run).

- A1: K lr-op-78ed264dc1-a1. Count 1 (T-1) after the dropped attempt and
  after the identical retry; the retry answered success, `replayed: true`,
  T-1.
- A2: K lr-op-78ed264dc1-a2, priority 3 changed to 4. Count stayed 1
  (T-2, priority 3). The retry was not refused: it answered success with
  `replayed: true`, ticket T-2, and the first call's text "Created ticket
  T-2 in project inbox (version 1)". No ticket with priority 4 exists.
- A3: both K-only paths returned T-1 (replay `replayed: true`, count 1
  before and after); no digest.
- A4: retry classes `success` and `success`. Scoring note for joint
  review: the A2 retry's success points at T-2, a committed record of
  (K, A), not of the (K, A') the retry asked for. The driver records it
  as "success corresponding to a committed record" and scores A4 pass;
  whether a replay answer for a different request counts as a generic
  success under A4 is a question for the contract, recorded here and not
  resolved by us.

## A5

Not run on this build: it was stopped after A1 to A4 (key record in
memory; a restart loses it). A5 is run on the correct build only.

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
- K-only recovery paths (a3_konly_*.json): list_tickets by title prefix
  K (works only because the caller put K in the title; tiny-tracker has
  no lookup keyed by the idempotency key), then the same-key replay with
  the caller's own arguments, with the counter read before and after.
- tiny-tracker keeps its data and its idempotency-key record in memory:
  a restart loses both.
