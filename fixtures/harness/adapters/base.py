"""The adapter contract for the lost-response harness.

The harness driver (../lost_response.py) owns the contract's scoring:
it runs assertions A1 to A5 of ../../CONTRACT.md and scores each one
pass, fail, or unproven from observed evidence. An adapter owns
everything system-specific: how an operation is executed, how the
shared external effect counter is read, and how an outcome is
recovered. An adapter never scores anything.

To run the contract against a new system, implement the five
operations below in a subclass of SystemAdapter, in a module in this
directory, and point the harness config at it. See README.md in this
directory for the full guide and stub.py for a copyable template.

The five operations the driver needs, mapped to the contract:

  initialize()      Open the run: handshake or session setup. The
                    evidence is recorded in 00_initialize.json.

  execute()         Execute one attempt of the logical operation with
                    operation identity K and the system's arguments.
                    With drop_response=True the adapter must run the
                    attempt to commit on the system and then discard
                    the response client-side, returning transport
                    metadata only: no result, no record id, no digest.
                    That is the lost-response fault. Retries are just
                    execute() again with the same K (identical) or
                    with mismatched=True (exactly one parameter value
                    changed, per the adapter's own configuration).

  count_effects()   Read the shared external effect counter defined
                    in ../../fixtures/README.md: the number of
                    distinct committed executions of the operation
                    visible in the system's durable public record,
                    attributed by the run-scoped session identity and
                    by K, with the identifier list the count was taken
                    from, so a third party can recount.

  fetch_record()    Resolve one committed record by the server-issued
                    record id the caller legitimately holds (the A3
                    run-id leg and the A5 delayed leg). Returns the
                    record as served, the digests it carries, and a
                    recomputation verdict: the adapter recomputes the
                    committed digest from the record's own bytes where
                    the system makes that possible, and reports the
                    outcome exactly as it comes out.

  recover_by_key()  Attempt outcome recovery holding ONLY K: no run
                    id, no response, no result, no digest from attempt
                    1. Caller authentication, operation scoping, and
                    retrieval permission are the caller's own and are
                    not part of what "only K" excludes (CONTRACT.md
                    A3). Returns every recovery path tried, in order,
                    with the exact caller-visible outcome of each.

Return shapes are specified per method. Extra adapter-specific
evidence is welcome inside the returned dicts; the keys named in the
docstrings are the ones the driver reads. Raw evidence an adapter
wants published with the run is returned under a "files" key as a
{filename: object} dict; the driver writes those files verbatim into
the run directory. File contents are JSON-serializable objects or
plain strings.
"""

import abc


class SystemAdapter(abc.ABC):
    """Base class for lost-response harness adapters.

    Subclasses set `name` to the module's adapter name (the value the
    harness config's "adapter" key carries) and implement the five
    operations. `config` is the config's adapter_config object: its
    keys are adapter-defined and documented by the adapter itself.
    """

    name = "base"

    def __init__(self, config):
        self.config = config or {}

    @abc.abstractmethod
    def initialize(self):
        """Open the run and return (evidence, summary).

        evidence: JSON-serializable dict recorded verbatim as the
        run's 00_initialize.json (handshake request/response, session
        identifiers issued, transport metadata).
        summary: small dict recorded in summary.json under
        "initialize" (for example, whether the system issued the
        caller identity the run needs).
        """

    @abc.abstractmethod
    def execute(self, *, session_id, operation_key, mismatched=False,
                drop_response=False):
        """Execute one attempt; return {"arguments_sent", "call"}.

        arguments_sent: the exact arguments the attempt carried, with
        K bound as the operation identity and session_id as the
        run-scoped attribution identity. With mismatched=True exactly
        one parameter value differs from the base arguments.
        call: the caller-visible outcome of the attempt:
          {"dropped": bool,
           "transport": {...} or None,
           "body": <full response body> (absent when dropped),
           "response_class": <short class string the driver records
             for A4, for example "success", "payment_required",
             "tool_error:<code>", "jsonrpc_error:<code>">,
           "receipt_ids": [record identifiers the response carries]}
        When drop_response is True, "dropped" is True and no body,
        result, record id, or digest from the attempt is present
        anywhere in the return value.
        """

    @abc.abstractmethod
    def count_effects(self, *, session_id, operation_key, label):
        """Read the shared external effect counter for one operation.

        Returns {"evidence": {...}, "files": {filename: object}}.
        evidence must carry:
          "external_effect_count": int, the count itself;
          "execution_record_ids": the identifier list counted from;
          "label", "session_id", "at": attribution and timing.
        The driver records evidence as count_<label>.json and writes
        files verbatim (raw enumeration responses belong there).
        """

    @abc.abstractmethod
    def fetch_record(self, record_id):
        """Resolve one committed record by its server-issued id.

        Returns a dict carrying at least:
          "record_id", "http_status" (or the system's equivalent
          found/not-found signal), "digests" (the digest values the
          record carries, by the system's own field names), and
          "recomputation": {"status": "matched" | "mismatched" |
          "not_computable", ...} from recomputing the committed
          digest against the record's served bytes where the system
          permits it. The full record as served belongs in the dict
          as well; it is recorded verbatim in the run outputs.
        """

    @abc.abstractmethod
    def recover_by_key(self, *, operation_key):
        """Try to recover the committed outcome holding only K.

        Returns {"attempts": [...], "files": {filename: object}}.
        Each attempt is a dict with at least:
          "path": what was tried, in words;
          "response_class": the caller-visible outcome class (use
          "found" for a path that returned the committed record, and
          a precise not-found or error class otherwise);
        plus whatever identifiers or digests the path returned. The
        driver scores the K-only leg from these attempts and from
        nothing else the adapter knows: if a path recovered the
        record, its attempt must say so in its response_class and
        carry the recovered digest for comparison.
        """
