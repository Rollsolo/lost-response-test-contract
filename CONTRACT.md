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
- Both implementations are measured against the same independently
  observable external effect counter (for example, one durable ledger row
  or one public record per actual execution). The concrete counter is
  defined in the fixtures, so both sides measure the same thing.
- APC column: the retry MUST NOT execute; it resolves against the
  committed effect.
- AER-1 / Zambo column: every execution MUST carry exactly one durable
  receipt, and the receipts remain part of the evidence; the receipt count
  alone does not substitute for the shared external effect count. The run
  reports the observed external count as the result (a count of 2 is a
  recorded fail, not a rounding).
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
  caller attempts recovery using only K. The recovery caller holds only
  K: it must not possess the original run ID, response, result, or digest
  from attempt 1.
- Pass condition: the caller obtains the original committed outcome, and
  the recovered outcome is independently checked against the original
  committed result digest; the digests must be equal. Digest equality is
  the pass evidence: it proves the lookup path was taken rather than a
  re-execution returning fresh output.
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
  the contract before running). The delay is measured from the original
  commit time.
- Pass condition: recovery still succeeds and the digest still confirms;
  a lookup miss inside the window is a fail, not a fresh operation.
  During the delay period the operation identity remains protected
  against fresh execution, including when a delayed retry uses modified
  parameters.
- Basis: a record store pruning faster than clients can retry recreates
  the ambiguity this contract tests.

## Historical baselines

Baseline observations published before the contract is frozen are
preserved as historical evidence. They are kept separate from the
official jointly executed results recorded in RESULTS.md, and they do
not count as runs of this contract. Both implementations are evaluated
under the same frozen contract and equivalent conditions.

## Scoring and publication

Each assertion is scored separately per system as pass, fail, or
unproven, with the raw outputs linked; no aggregate score; disagreements
about scoring are published as disagreements, not resolved by either
party unilaterally.
