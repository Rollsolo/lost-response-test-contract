# Fixtures

Fixtures for the contract runs: the fault-injection harness, the
countable-effect tool definition, and per-system adapters. Nothing in
this directory is final until the contract in ../CONTRACT.md is
established.

The fixtures define the concrete shared external effect counter used by
assertion A1, so both implementations are measured against the same
independently observable count.

## The shared external effect counter

The counter is a count of durable public records, not a count of
responses the caller happened to receive.

Definition: for one logical operation (operation identity K, arguments
A), the external effect count is the number of distinct committed
executions of that operation that are visible in the system's durable
public record after all attempts finish.

Rules:

1. One actual execution produces exactly one durable public record.
   Records produced for refused or unexecuted attempts do not count as
   executions, and they are reported separately when they exist.
2. The count is read from the public record itself, by either party or
   by a third party, after the run. It is never read from the caller's
   received responses, because attempt 1's response is dropped by the
   fault injector and the caller never sees it.
3. Attribution: every attempt in a run carries a unique run-scoped
   caller or session identity, generated fresh for the run and recorded
   in the run's raw outputs. Records are attributed to the run by that
   identity, and within the run to the logical operation by K.
4. A count is only reported with the list of record identifiers it was
   counted from, so anyone can recount from the same public record.

## The counter for Zambo

For Zambo, the durable public record is the public receipt record.
Every tool execution writes exactly one AER-1 receipt, readable by
anyone at https://zambo.dev/run/<receipt_id> with no login. Receipts
prove the saved result was not changed after the fact.

Concretely, the harness counts Zambo executions for one logical
operation as follows:

1. Each assertion run uses a fresh run-scoped session identity
   (the MCP `_session_id` argument), recorded in the run outputs.
   The operation identity K is the `job_id` argument of the target
   tool (see the harness README for the tool choice and the mapping).
2. After the attempts, the harness enumerates the receipt-backed
   record for that session through a free read path: a workflow
   snapshot of every persisted receipt from the job, which lists the
   job's receipt identifiers (its children) and excludes the snapshot
   call's own receipt. A caller-scoped recent-work read is not a
   valid enumerator for this counter, because it is not scoped to
   the job; the 2026-11-16 run confirmed that first-hand and the
   harness does not use it for counting.
3. Each enumerated receipt identifier is then attributed and checked
   directly against the public record: the JSON record at
   https://zambo.dev/api/v2/receipt/<receipt_id>/verify names the
   tool and step status for that receipt, and the human-readable
   record lives at https://zambo.dev/run/<receipt_id>. Only
   identifiers whose public record shows the target tool with a
   successful step count as executions of the operation.
4. The external effect count for the operation is the number of
   distinct resolving receipt identifiers attributed to (session, K).

The receipt count here is not a substitute for the shared counter, as
CONTRACT.md A1 requires: it is the shared counter for Zambo, because
the contract's common setup defines the counter as one durable public
record per actual execution, readable by both parties and by a third
party, and the public receipt record is exactly that record for this
system. A receipt written for a refused attempt, if one exists, is
reported as a refusal record and is not counted as an execution of the
operation; the harness separates execution receipts from refusal
records by the outcome recorded in each receipt.

## The harness

The runnable harness lives in harness/ in this directory. The
driver owns the scoring; each system under test is reached through
an adapter in harness/adapters/ (the Zambo adapter is the reference
implementation, and a stub adapter is the template for a new
system). See harness/README.md for how to run it, the configuration
knobs, the target tool choice for Zambo, and how each assertion
A1 to A5 is executed and scored, and harness/adapters/README.md
for the adapter contract and how to run the contract against a
different system.
