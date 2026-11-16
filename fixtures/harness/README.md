# Lost-response harness

A small, documented Python harness that runs assertions A1 to A5 of
the contract in ../../CONTRACT.md. The driver owns the scoring; a
per-system adapter owns execution, the external effect counter, and
recovery on the system under test. It uses only the Python standard
library plus `requests`.

## Run it

```bash
pip install -r requirements.txt
python3 lost_response.py --config config.zambo.json --out ../../runs/my-run
```

The runner writes raw outputs into the output directory: one JSON file
per step (request arguments sent, transport metadata, full response
bodies for non-dropped attempts, enumeration evidence, receipt records
as served), plus `summary.json` and a `RESULTS-snippet.md` formatted
for pasting into ../../RESULTS.md. Both parties publish raw outputs,
not summaries, per the contract's common setup.

The config selects the adapter and carries its settings:

```json
{
  "adapter": "zambo",
  "system_name": "Zambo production",
  "a5_delay_hours": 24,
  "adapter_config": { "endpoint": "...", "public_base": "...",
                      "tool": "...", "args_template": { } }
}
```

The driver reads only the top-level keys; everything under
`adapter_config` belongs to the named adapter. For the Zambo adapter
the knobs are `endpoint`, `public_base`, `tool`, and `args_template`.
The template uses two placeholders: `{K}` for the stable operation
identity the caller supplies, and `{SESSION}` for the fresh
run-scoped session identity used to attribute records to the run.

## Adapters

To run the contract against a different system, write an adapter:
five operations (initialize, execute, count the external effect
counter, resolve a record by id, recover holding only K) behind the
contract in adapters/base.py. adapters/zambo.py is the reference
implementation; adapters/stub.py is a copyable template that
implements nothing. The full guide, including what to publish back,
is adapters/README.md (also linked from the repository README's
"Run it against your system" section).

## How the fault is injected

Attempt 1's request is sent normally and the server commits its
effect. The harness then discards the response body client-side and
records transport metadata only: send and receive timestamps, HTTP
status, response byte count, elapsed time, and the JSON-RPC request
id. No result, receipt id, or digest from attempt 1 is available to
the retry or recovery code, which is the caller's position after a
real lost response. Retries use a fresh JSON-RPC request id, as MCP
requires.

## The counter

The external effect counter is defined in ../README.md. In short: the
count of distinct committed executions visible in the system's durable
public record after all attempts, attributed by the run-scoped session
identity and by K, with every counted identifier checked directly
against the public record. For Zambo the harness enumerates the
receipt-backed record for the session through a free read path (a
workflow snapshot of every persisted receipt from the job), then
attributes each enumerated receipt identifier through its public
JSON record at https://zambo.dev/api/v2/receipt/<id>/verify, which
names the tool and step status, and counts only executions of the
target tool with a successful step. The human-readable record for
each counted receipt is at https://zambo.dev/run/<receipt_id>. A
caller-scoped recent-work read is not used for counting: the
2026-11-16 run showed it is not scoped to the job.

Receipt count alone is not treated as evidence of anything else: the
count is reported with the identifier list it was counted from, so a
third party can recount from the same public record.

## Target tool choice for Zambo

Default target: `journal_log`.

Why it fits the contract's common setup:

- It is a mutating, append-only tool: every execution appends one log
  entry and writes exactly one durable public AER-1 receipt, so every
  execution is externally countable in the public record.
- Its contract metadata marks it non-idempotent with side effects, so
  a retry that executes again is a real second effect, not a replay
  the tool promises to collapse.
- The caller supplies a stable job identifier, `job_id`, which carries
  the operation identity K, plus `executor_identity`. The arguments A
  are the remaining fields (`action`, `inputs`, and the session
  identity). A2 changes exactly one parameter value: `action`.
- Alternatives considered from the live tools/list on 2026-11-16:
  `continuity_start_thread` is documented as create-or-reuse and
  marked idempotent, so it cannot show a duplicate effect;
  `memory_remember` writes a private record whose receipts are not
  the countable public effect the contract wants a third party to
  recount. `journal_log` is the fit.

The endpoint's catalog at run time: 153 total tools, 37 on the
default surface. The harness reads the live endpoint; it does not
assume the catalog.

## How each assertion runs

- A1: attempt 1 with (K, A), response dropped; count from the public
  record; identical retry with (K, A) under a fresh request id; count
  again. Pass is a final count of exactly 1.
- A2: a separate operation (fresh session and K). Attempt 1 dropped;
  retry with (K, A') where A' changes exactly one parameter value
  (`action`). Pass requires no new effect and an explicit refusal
  class, not a success and not a generic error.
- A3, both legs, reusing the A1 operation, whose attempt 1 already
  committed with its response lost:
  - Run-id leg: the caller holds a server-issued run id (a receipt id
    from the public record), resolves the record through the public
    JSON record at https://zambo.dev/api/v2/receipt/<id>/verify
    (AER-1 Section 9 resolution; the human-readable page is
    https://zambo.dev/run/<id>), and checks the digest: the harness
    recomputes SHA-256 over the exact decoded canonical bytes in the
    record and compares it with the served output_hash (AER-1
    Section 6), recording the outcome exactly as it comes out.
  - K-only leg: a recovery caller that holds only K. It tries the
    direct record lookup by K and the configured K-keyed lookup
    tools, possessing no run id, response, result, or digest from
    attempt 1. Pass requires a recovered digest equal to the
    committed digest, with no second effect.
- A4: scored from the exact response classes recorded for the A1 and
  A2 retries. A generic success corresponding to no committed record
  is a fail.
- A5: the harness plants the A1 operation: `a5_plant.json` records K,
  the session identity, the committed receipt ids, the committed
  digest, and the commit timestamp with a due time 24 hours later.
  The delayed leg runs later against the same plant:

  ```bash
  python3 lost_response.py --delayed-leg ../../runs/my-run/a5_plant.json
  ```

  It writes `a5_delayed_result.json` next to the plant. A5 is scored
  unproven on the planting day, by construction.

## Free-tier and payment behavior

The harness never pays anything. Against Zambo, metering is per
network: each metered tool allows one free successful call per
network per UTC day plus three shared continue calls. If a call
returns a `payment_required` response class, the harness records it
as an observed response class. When that refusal happens before any
commit, the lost-response precondition never occurred and the
affected assertion is scored unproven with that reason, never
borrowed from any published baseline.

## Context

Brennan Zambo created agent execution receipts; Zambo is the origin
product; AER-1 is the defining standard. Receipts in this harness are
evidence that a saved result was not changed; they are never treated
as proof that a result was correct.
