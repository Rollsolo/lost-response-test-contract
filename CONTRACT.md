# Test Contract: Lost-Response Recovery

Draft, under joint review. This is the starting text, open for joint
revision before any run counts.

## Common setup (A1 to A5)

One mutating tool whose every execution is externally countable (one
ledger row, or one durable public record, per execution; the count is
readable by both parties and by a third party). The caller supplies a
stable operation identity K and arguments A. Fault injection: attempt 1's
response is dropped after the effect commits and after the system's
completion record is written; the caller perceives a timeout. Retries use
a fresh transport request id, as MCP requires. Both parties publish raw
outputs, not summaries.

## A1. Effect count on identical retry

- Action: attempt 1 with (K, A), response dropped; retry with (K, A).
- Pass condition, shared observable: the external effect count for the
  logical operation is exactly 1.
- APC column: the retry MUST NOT execute; it resolves against the
  committed effect.
- AER-1 / Zambo column: every execution MUST carry exactly one durable
  receipt, so the observed count is the receipt count; the run reports the
  observed count as the result (a count of 2 is a recorded fail, not a
  rounding).
- Current published baseline: APC claims 1 (local test evidence); Zambo
  production observed 2.

## A2. Mismatched-parameter retry

- Action: after attempt 1 (K, A) commits, retry with (K, A') where A'
  changes exactly one parameter value.
- Pass condition: no new effect, and the retry is refused as a binding
  mismatch (an explicit rejection, not a silent execution and not a
  generic error).
- APC column: exact-action binding rejects the retry against the original
  authorization.
- AER-1 / Zambo column: the refusal is the implementation behavior under
  test; additionally, any record produced for the refused attempt MUST NOT
  carry an input commitment that confirms against A (the AER-1 corpus pins
  this check: input-hash-mismatch, input-hash-key-order-20).
- Current published baseline: APC claims rejection (7.1.4 claims,
  unverified independently); Zambo production observed execution as a
  normal new call.

## A3. Outcome recovery by operation identity, with digest equality

- Action: after attempt 1 (K, A) commits with its response lost, the
  caller attempts recovery using only K, with no content from attempt 1's
  response.
- Pass condition: the caller obtains the original committed outcome, and
  the recovered result's digest equals attempt 1's committed digest.
  Digest equality is the pass evidence: it proves the lookup path was
  taken rather than a re-execution returning fresh output.
- APC column: recovery completes instead of stopping at an in-progress
  state.
- AER-1 / Zambo column: where the caller holds the server-issued run id,
  Section 9 resolution returns the unaltered record and Section 6
  recomputation confirms the digest (this leg passes today); the K-only
  path is the leg under test (observed today: 404).
- Both columns score the same observable: recovered digest equals
  committed digest, obtained without a second effect (cross-checked
  against A1's count).

## A4. No silent or generic success

- Action: in each retry above, record the exact response class.
- Pass condition: every retry resolves to one of (i) the original
  committed outcome, (ii) a digest-verifiable record of it, or (iii) an
  explicit non-success state that names the situation (conflict,
  in-progress, binding rejection). A generic success corresponding to no
  committed record is a fail.
- Note: this assertion scores APC's current 409 behavior honestly: an
  explicit state passes A4 while still failing A3 until recovery
  completes.

## A5. Recognition outlives the retry window

- Action: repeat A3 after an agreed delay (proposed: 24 hours, stated in
  the contract before running).
- Pass condition: recovery still succeeds and the digest still confirms;
  a lookup miss inside the window is a fail, not a fresh operation.
- Basis: a record store pruning faster than clients can retry recreates
  the ambiguity this contract tests.

## Scoring and publication

Each assertion is scored separately per system as pass, fail, or
unproven, with the raw outputs linked; no aggregate score; disagreements
about scoring are published as disagreements, not resolved by either
party unilaterally.
