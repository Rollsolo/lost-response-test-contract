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
