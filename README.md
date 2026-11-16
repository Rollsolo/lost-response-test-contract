# Lost-Response Test Contract

A neutral, shared test contract for one narrow failure case in agent-to-tool
systems: a mutating tool call commits its external effect, the response is
lost before the caller receives it, and the caller retries.

This repository is the canonical home for the contract text, the fixtures,
the execution instructions, and the recorded results. It belongs to no
single implementation. The public discussion lives in the MCP issue thread
that raised the case (modelcontextprotocol/modelcontextprotocol issue
#3394); this repository is where the test itself is kept.

## The three properties, kept separate

The contract scores three properties independently. A system can pass one
and fail another, and the results are recorded that way.

1. **Effect count.** Under same-operation retries after a lost response,
   the external effect happens exactly once.
2. **Authorization binding.** A retry whose action or parameters no longer
   match the original authorization, under the same operation identity, is
   rejected and produces no effect.
3. **Outcome recovery.** The caller can recover the original committed
   outcome, with digest equality against the original committed result as
   the evidence that the original record was recovered rather than the
   operation re-executed.

## Neutrality rule

The same contract, equivalent failure conditions, and independently
recorded results for both systems. Neither side changes its implementation
to satisfy the test before the contract is established. If either
implementation fails an assertion, the failure is reported as observed.
Scores are recorded per assertion, per system, with raw outputs linked.
There is no aggregate score.

## Status

Draft, under joint review. The assertion set in CONTRACT.md is the
starting text, open for joint revision before any run counts. Results go
in RESULTS.md.

## Run the harness

The runnable fixture harness lives in fixtures/harness/. It runs
assertions A1 to A5 against any MCP endpoint, with the fault injector,
the shared external effect counter defined in fixtures/README.md, and
raw outputs per run.

```bash
cd fixtures/harness
pip install -r requirements.txt
python3 lost_response.py --config config.zambo.json --out ../../runs/my-run
```

Configuration knobs (in the config JSON): `endpoint` (the MCP endpoint
to test), `public_base` (where the system's durable public record
lives), `tool` (the target mutating tool), `args_template` (the
arguments A, with `{K}` for the stable operation identity and
`{SESSION}` for the fresh run-scoped session identity), `mismatch`
(the one parameter A2 changes, and its altered value), and
`a5_delay_hours` (the A5 delay, 24 by default). The delayed A5 leg
runs later against a planted run:

```bash
python3 lost_response.py --delayed-leg ../../runs/my-run/a5_plant.json
```

Full harness documentation, including the target tool choice for
Zambo and how each assertion is executed and scored, is in
fixtures/harness/README.md. Recorded runs and their raw outputs are
in runs/, scored in RESULTS.md.

## Changelog

- 2026-11-16: Yared Mengistu reviewed assertions A1 to A5 and agreed
  with the assertions and the scoring model. Four clarifications from
  that review are incorporated in CONTRACT.md: a common external effect
  counter for A1, K-only recovery for A3, retention semantics for A5,
  and historical baselines preserved separately from jointly executed
  results. The contract is ready to freeze on both parties'
  confirmation.
