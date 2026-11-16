"""TEMPLATE adapter. Copy this file, rename it, and fill in the five
operations for your system. It implements nothing: every operation
raises NotImplementedError with a pointer to what it must do. It is
shaped for a system that, like the systems this contract was written
around, executes operations under a caller-supplied operation
identity K against some authorization or commitment record and keeps
a durable record of committed effects. That shape is a starting
point only. No behavior of any real system is described or implied
by this template.

How to use it:
  1. Copy this file to adapters/<your_system>.py and rename the class
     (keep the class name `Adapter` and set `name` to your file's
     stem).
  2. Implement each operation against your system, following the
     return shapes in base.py. The driver scores from what your
     operations return; return observed evidence, never conclusions.
  3. Write a config JSON (see ../config.example.json) with
     "adapter": "<your_system>" and your adapter's own keys under
     "adapter_config", and document those keys in your module
     docstring.
  4. Run: python3 lost_response.py --config <your config> --out ../../runs/<dir>
"""

from .base import SystemAdapter


class Adapter(SystemAdapter):
    """Template. Replace this docstring with your system's name, what
    its durable public record is, and your adapter_config keys."""

    name = "stub"

    def initialize(self):
        # Open whatever session or handshake your system needs before
        # the first execution. Return (evidence, summary) as base.py
        # specifies; the evidence is published with the run.
        raise NotImplementedError(
            "initialize: open the run against your system and return "
            "(evidence, summary); see adapters/base.py")

    def execute(self, *, session_id, operation_key, mismatched=False,
                drop_response=False):
        # Execute ONE attempt of the logical operation.
        # - Bind operation_key as the operation identity K, and
        #   session_id as the run-scoped attribution identity, in
        #   whatever fields your system carries them.
        # - With mismatched=True, change exactly one parameter value
        #   (which one is your adapter's configuration).
        # - With drop_response=True, let the attempt commit on the
        #   system, then discard the response: the returned call dict
        #   carries transport metadata only, no result, no record id,
        #   no digest.
        # Return {"arguments_sent": ..., "call": {...}} with the
        # caller-visible response_class set honestly, including your
        # system's refusal classes.
        raise NotImplementedError(
            "execute: run one attempt (dropped, identical, or "
            "mismatched) and return the caller-visible outcome; "
            "see adapters/base.py")

    def count_effects(self, *, session_id, operation_key, label):
        # Read the shared external effect counter from your system's
        # durable public record (fixtures/README.md): the number of
        # distinct committed executions of this operation, attributed
        # by session_id and operation_key. Return the count AND the
        # identifier list it was counted from, plus the raw
        # enumeration evidence under "files", so a third party can
        # recount from the same record.
        raise NotImplementedError(
            "count_effects: count committed executions of the "
            "operation in the durable public record; "
            "see adapters/base.py")

    def fetch_record(self, record_id):
        # Resolve one committed record by the server-issued id the
        # caller legitimately holds. Return the record as served, the
        # digests it carries, and a recomputation verdict: recompute
        # the committed digest from the record's own bytes if your
        # system publishes enough to do that, and report the outcome
        # exactly as it comes out (matched, mismatched, or
        # not_computable with the reason).
        raise NotImplementedError(
            "fetch_record: resolve a record by id and check its "
            "digest; see adapters/base.py")

    def recover_by_key(self, *, operation_key):
        # Attempt outcome recovery holding ONLY operation_key: no run
        # id, no response, no result, no digest from attempt 1. Try
        # each recovery path your system offers a caller in that
        # position (a key-keyed lookup, a record query, a status
        # endpoint), in order, and return every attempt with its
        # exact caller-visible outcome. If a path returns the
        # committed record, mark its response_class "found" and carry
        # the recovered digest in the attempt.
        raise NotImplementedError(
            "recover_by_key: try recovery holding only K and report "
            "each path's outcome; see adapters/base.py")
