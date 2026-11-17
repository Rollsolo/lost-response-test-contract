# Run notes: tiny-tracker correct build

Pinned versions: contract and harness at zambodotdev/lost-response-test-contract
commit 92bf1ba (CONTRACT.md unchanged, still marked draft); adapter
fixtures/harness/adapters/tiny_tracker.py version 0.1.0, added with these
runs; system under test npm @mcp-write-safety/tiny-tracker 0.1.0, run
locally with `tiny-tracker all`, bound to 127.0.0.1 only; Python 3.11,
requests 2.34.2.

Every file in this directory except this note was written by the driver
(lost_response.py) and the adapter, unedited.

Build: correct (no defect). Start command:
`TRACKER_BACKEND_TOKEN=<fresh local test token> npx -y -p @mcp-write-safety/tiny-tracker@0.1.0 tiny-tracker all --port 47310 --backend-port 47311`

## Scores as written by the driver

A1 pass, A2 pass, A3 unproven, A4 pass, A5 unproven (pending).

- A1: K lr-op-409891e807-a1. Count 1 after the dropped attempt (T-1),
  1 after the identical retry. The retry answered success with
  `replayed: true` and ticket T-1.
- A2: K lr-op-409891e807-a2, priority 3 changed to 4 on the retry. Count
  stayed 1 (T-2). The retry was refused: isError, code
  `idempotency_key_reused`, outcome `not_applied`.
- A3: both K-only paths returned T-1 (the replay with `replayed: true`,
  count 1 before and after). Neither carries a digest.
- A4: retry classes `success` (a replay of the committed T-1) and
  `tool_error:idempotency_key_reused`.

## A5 (pending)

This build was left running after the run, detached, bound to 127.0.0.1,
so the delayed leg can run against the same process:

- process: npm exec PID 22448, node PID 22489 (started 2026-11-17T02:12:47Z)
- ports: MCP 47310 (/mcp), backend 47311
- planted K lr-op-409891e807-a1, record T-1, attempt 1 sent
  2026-11-17T02:13:28.537813Z
- due (UTC): 2026-11-18T02:13:28.566512Z (a5_plant.json `due_at`)
- delayed leg: `python3 fixtures/harness/lost_response.py --delayed-leg runs/2026-11-17-tiny-tracker-correct-1/a5_plant.json`
  (with TRACKER_BACKEND_TOKEN set to this build's token)

Known before the delayed leg runs: the driver's delayed leg scores pass
only when the record serves a digest equal to the committed digest and
fetch_record(K) answers 200. tiny-tracker serves no digest and has no
record addressable by K, so the delayed leg will not score pass whatever
the process remembers. The K-only replay at +24 h (the adapter's
recover_by_key) is the observation that shows whether the key is still
recognized; it will be recorded beside the delayed leg's output. If the
process is restarted before then, the key record is gone (in memory), and
A5 cannot be run on this plant.

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
