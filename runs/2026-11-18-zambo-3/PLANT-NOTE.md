# Run 2026-11-18-zambo-3: key-binding fix acceptance + A5 plant

Published fix (crew, 2026-11-18 ~13:34 EST): replay protection and
key-only recovery bound to the operation key (job_id + parameter
digest), independent of caller_handle.

Phase 1 (p1_*): fresh-client probes against the zambo-2 operation
lr-op-13118ee094-a1, the operation whose delayed retry executed
fresh that morning. Post-publish: K-only continuity returns the
original receipt + committed digest; identical retry replays the
original receipt e3af210e with the replay marker, no third
execution; modified-parameter retry refused before execution.
The operation's two historical executions stand.

Phase 2 (p2_*): fresh plant lr-op-bb150ceec1-a1 / session
lr-bb150ceec1-a1, planted 2026-11-18T18:37:56Z, receipt
e2568939-b651-4150-b059-a1eeebbf7319, committed digest
sha256:c63fbfb9a34b33df4e5d2d821186ba7020c7e67217d8f80958b228710f106818,
effect count 1. Short-range A1/A2/A3 all pass from fresh clients.
A5 delayed leg due 2026-11-19T18:38:16Z (a5_plant.json).
