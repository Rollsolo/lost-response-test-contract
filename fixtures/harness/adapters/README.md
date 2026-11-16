# Adapters

The harness driver (../lost_response.py) owns the contract's scoring.
An adapter owns everything system-specific: how an operation is
executed on the system under test, how the shared external effect
counter is read from that system's durable public record, and how an
outcome is recovered. The driver runs assertions A1 to A5 of
../../CONTRACT.md through the adapter and scores each assertion
pass, fail, or unproven from the evidence the adapter returns. An
adapter never scores anything, and it returns observed evidence,
never conclusions.

## The five operations

An adapter is a Python class implementing the contract in base.py:

| Operation | What it does | Contract role |
|---|---|---|
| `initialize()` | Open the run: handshake or session setup. | Recorded as the run's `00_initialize.json`. |
| `execute(session_id, operation_key, mismatched, drop_response)` | Execute one attempt binding K as the operation identity. With `drop_response=True` the attempt commits and the response is discarded client-side: transport metadata only, no result, no record id, no digest. With `mismatched=True` exactly one parameter value is changed. | Attempt 1, the identical retry (A1), and the mismatched retry (A2) are all this one operation. |
| `count_effects(session_id, operation_key, label)` | Read the shared external effect counter (../../fixtures/README.md) from the system's durable public record: the number of distinct committed executions of the operation, with the identifier list counted from. | The A1 observable, and the no-new-effect check in A2. |
| `fetch_record(record_id)` | Resolve one committed record by the server-issued id the caller legitimately holds, with the digests it carries and a recomputation verdict over its served bytes. | The A3 run-id leg and the A5 delayed leg. |
| `recover_by_key(operation_key)` | Try every recovery path available to a caller holding ONLY K: no run id, response, result, or digest from attempt 1. Caller authentication, operation scoping, and retrieval permission are the caller's own; "only K" excludes response-derived identifiers, not those (CONTRACT.md A3). | The A3 K-only leg, the contract's pass condition for A3. |

Return shapes are specified in base.py. Raw evidence an adapter
wants published with the run is returned under a `files` key as a
{filename: object} dict; the driver writes those files verbatim into
the run directory.

## Configuration

One JSON file per system under test:

```json
{
  "adapter": "zambo",
  "system_name": "Zambo production",
  "a5_delay_hours": 24,
  "adapter_config": {
    "...": "adapter-defined keys, documented in the adapter module"
  }
}
```

The driver reads only the top-level keys. `adapter` is the adapter
module's file stem in this directory; the module defines a class
named `Adapter`. Everything under `adapter_config` belongs to that
adapter. ../config.example.json is a fill-in template;
../config.zambo.json is the working example.

## Run the contract against your system

1. Copy stub.py to `adapters/<your_system>.py`. Rename nothing else:
   the class stays `Adapter`, and its `name` attribute is your
   file's stem. The stub is a template with guidance in each method;
   it describes no real system's behavior.
2. Implement the five operations against your system. Two rules
   matter more than any other:
   - The dropped attempt must be genuinely dropped. After a
     `drop_response=True` execute(), nothing from that response (no
     result, record id, or digest) may reach the retry or recovery
     code. That is the caller's position after a real lost response,
     and the contract measures exactly that position.
   - The counter is read from the durable public record, never from
     responses the caller received, and is reported with the
     identifier list it was counted from so a third party can
     recount.
3. Write your config JSON (see above) and document your
   `adapter_config` keys in your module's docstring.
4. Run it:

   ```bash
   cd fixtures/harness
   pip install -r requirements.txt
   python3 lost_response.py --config <your config>.json --out ../../runs/<run-dir>
   ```

   The A5 delayed leg runs at or after the delay in CONTRACT.md
   (24 hours by default), against the plant the run writes:

   ```bash
   python3 lost_response.py --delayed-leg ../../runs/<run-dir>/a5_plant.json
   ```

5. Publish the run (next section) and add its rows to ../../RESULTS.md.

## What to publish back

Per the contract's scoring and publication rules, a run is published
as raw outputs, not summaries:

- the pinned versions: the contract and harness commit the run was
  executed against, and the adapter's name and version or commit;
- the full run directory: every raw output the driver and the
  adapter wrote, including the dropped attempts' transport metadata
  and `summary.json`;
- the external effect counts for A1 and A2, each with the identifier
  list it was counted from;
- the caller-visible outcomes: the exact response class of every
  retry and every recovery path tried, as returned, including
  refusals and not-found results;
- one row per assertion in RESULTS.md: pass, fail, or unproven, with
  the evidence linked. No aggregate score. Failures are reported as
  observed; disagreements about scoring are published as
  disagreements.

## The adapters here

- `zambo.py`: the reference implementation, against Zambo production
  (MCP endpoint; the durable public record is the public AER-1
  receipt record). The recorded runs in ../../../runs/ were executed
  with it.
- `stub.py`: the copyable template. It implements nothing.
- `base.py`: the contract itself, as an abstract base class.
