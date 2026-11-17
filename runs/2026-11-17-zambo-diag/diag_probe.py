#!/usr/bin/env python3
"""A5 diagnosis probe, 2026-11-17, run folder runs/2026-11-17-zambo-diag/.

Purpose: pin down WHERE the A5/A3 K-only recovery property breaks on
Zambo production, comparing like with like against run
2026-11-16-zambo-1 (same adapter, same tool journal_log, same argument
template from fixtures/harness/config.zambo.json).

Steps:
  1. Plant a fresh operation exactly the way A5 planted (journal_log,
     K carried as job_id and inputs.operation, fresh run-scoped
     session identity). The response is kept, not dropped: the drop in
     the contract setup is client-side only, and the diagnosis needs
     the committed receipt id and digest from the public record.
  2. Establish the committed record from the public record itself
     (workflow_close snapshot enumeration + /api/v2/receipt/<id>/verify),
     and inspect whether K appears anywhere in the committed record.
  3. K-only recovery at short range (minutes) from a FRESH client whose
     caller holds only K: direct public-record lookup by K, then
     continuity_get_recent with K as the only identifier (the same two
     paths the harness's recover_by_key tries).
  4. Session-scoped read with the planting client (continuity_get_recent
     with the original session id): is the operation's record
     enumerable in the session namespace?
  5. Same-K retries at short range: identical, then one-parameter
     modified. Fresh execution or recognition? Counted through the
     public record after each.
  6. Write diag_plant.json so the harness delayed leg can be re-run
     against this plant, and diag_timing.json with elapsed times.

No payment is ever made. A payment_required response is recorded as
an observed response class, exactly as the harness records it.
"""

import base64
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter, normalize_config  # noqa: E402

OUT = Path(__file__).resolve().parent


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True),
                            encoding="utf-8")


def main():
    config = normalize_config(json.loads((HARNESS / "config.zambo.json")
                                         .read_text(encoding="utf-8")))
    acfg = config["adapter_config"]
    tag = uuid.uuid4().hex[:10]
    session = f"lr-{tag}-diag"
    k_value = f"lr-op-{tag}-diag"
    timing = {"tag": tag, "session_id": session, "K": k_value,
              "planted_at": None, "probes": []}

    def stamp(step):
        timing["probes"].append({"step": step, "at": utcnow()})

    adapter = load_adapter("zambo", acfg)

    init, init_summary = adapter.initialize()
    write("diag_00_initialize.json", init)
    stamp("initialize")

    # 1. Plant (response kept; the contract's drop is client-side only).
    attempt1 = adapter.execute(session_id=session, operation_key=k_value,
                               drop_response=False)
    write("diag_attempt1.json", {"label": "diag_attempt1", "at": utcnow(),
                                 "session_id": session, "K": k_value,
                                 "arguments_sent": attempt1["arguments_sent"],
                                 "call": attempt1["call"]})
    timing["planted_at"] = utcnow()
    stamp("attempt1_plant")

    # 2. Committed record from the public record.
    enum1 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="diag_after_attempt1")
    for name, obj in (enum1.get("files") or {}).items():
        write(name, obj)
    write("count_diag_after_attempt1.json", enum1["evidence"])
    stamp("enumerate_after_attempt1")
    receipt_ids = enum1["evidence"].get("target_tool_execution_receipt_ids") or []
    committed_digest = None
    if receipt_ids:
        record = adapter.fetch_record(receipt_ids[0])
        write("diag_runid_record.json", record)
        committed_digest = (record.get("digests") or {}).get("output_hash")
        # Does K appear anywhere in the committed public record?
        blob = json.dumps(record.get("record_json") or {})
        canon = ((record.get("record_json") or {}).get("receipt") or {}).get(
            "canonical_bytes")
        decoded = ""
        if canon:
            try:
                decoded = base64.b64decode(canon).decode("utf-8", "replace")
            except Exception:
                decoded = ""
        write("diag_record_inspection.json", {
            "receipt_id": receipt_ids[0],
            "http_status": record["http_status"],
            "digests": record.get("digests"),
            "recomputation_status": (record.get("recomputation") or {}).get("status"),
            "K_present_in_record_json": k_value in blob,
            "K_present_in_decoded_canonical_bytes": k_value in decoded,
            "record_top_level_keys": sorted((record.get("record_json") or {}).keys()),
            "receipt_keys": sorted(((record.get("record_json") or {}).get("receipt") or {}).keys()),
        })
    stamp("runid_record_and_inspection")

    # 3. K-only recovery at short range, fresh client holding only K.
    fresh = load_adapter("zambo", acfg)
    finit, _ = fresh.initialize()
    write("diag_konly_initialize.json", finit)
    recovery = fresh.recover_by_key(operation_key=k_value)
    write("diag_konly_run_lookup.json", recovery["files"]["a3_konly_run_lookup.json"])
    cont = recovery["files"].get("a3_konly_continuity_get_recent.json")
    if cont is not None:
        write("diag_konly_continuity_get_recent.json", cont)
    cont_blob = json.dumps(cont or {})
    write("diag_konly_summary.json", {
        "K": k_value,
        "attempts": recovery["attempts"],
        "planted_receipt_id": receipt_ids[0] if receipt_ids else None,
        "planted_receipt_returned_by_konly_lookup": bool(
            receipt_ids and receipt_ids[0] in cont_blob),
        "committed_digest": committed_digest,
        "committed_digest_in_konly_continuity_body": bool(
            committed_digest and committed_digest in cont_blob),
    })
    stamp("konly_recovery_short_range")

    # 4. Session-scoped read with the planting client.
    sess_call = adapter.client.call_tool(
        "continuity_get_recent", {"_session_id": session})
    write("diag_session_continuity_get_recent.json", sess_call)
    sess_blob = json.dumps(sess_call.get("body") or {})
    write("diag_session_read_summary.json", {
        "session_id": session,
        "response_class": sess_call.get("response_class"),
        "planted_receipt_present": bool(receipt_ids and receipt_ids[0] in sess_blob),
        "journal_log_present": "journal_log" in sess_blob,
    })
    stamp("session_scoped_read")

    # 5. Same-K retries at short range.
    retry = adapter.execute(session_id=session, operation_key=k_value,
                            drop_response=False)
    write("diag_retry_identical.json", {"label": "diag_retry_identical",
                                        "at": utcnow(), "session_id": session,
                                        "K": k_value,
                                        "arguments_sent": retry["arguments_sent"],
                                        "call": retry["call"]})
    stamp("retry_identical")
    enum2 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="diag_after_identical")
    for name, obj in (enum2.get("files") or {}).items():
        write(name, obj)
    write("count_diag_after_identical.json", enum2["evidence"])
    stamp("enumerate_after_identical")

    retry_m = adapter.execute(session_id=session, operation_key=k_value,
                              mismatched=True, drop_response=False)
    write("diag_retry_mismatched.json", {"label": "diag_retry_mismatched",
                                         "at": utcnow(), "session_id": session,
                                         "K": k_value,
                                         "arguments_sent": retry_m["arguments_sent"],
                                         "call": retry_m["call"]})
    stamp("retry_mismatched")
    enum3 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="diag_final")
    for name, obj in (enum3.get("files") or {}).items():
        write(name, obj)
    write("count_diag_final.json", enum3["evidence"])
    stamp("enumerate_final")

    # 6. Plant file for a later delayed-leg re-run + timing.
    write("diag_plant.json", {
        "assertion": "A5 (diagnosis plant)",
        "planted_at": timing["planted_at"],
        "delay_hours": 24,
        "K": k_value, "session_id": session,
        "execution_receipt_ids": enum3["evidence"].get(
            "target_tool_execution_receipt_ids"),
        "committed_digest": committed_digest,
        "endpoint": "https://zambo.dev/mcp",
        "adapter": "zambo",
        "adapter_config": acfg,
        "note": "Diagnosis plant planted 2026-11-17. The harness delayed "
                "leg (fixtures/harness/lost_response.py --delayed-leg) "
                "accepts an a5_plant.json shape; this file carries the "
                "same fields for the first planted operation only "
                "(execution_receipt_ids lists every execution observed "
                "for the operation, retries included).",
    })
    write("diag_timing.json", timing)
    print(json.dumps({
        "K": k_value, "session_id": session,
        "attempt1_class": attempt1["call"].get("response_class"),
        "count_after_attempt1": enum1["evidence"]["external_effect_count"],
        "committed_digest": committed_digest,
        "konly_attempts": recovery["attempts"],
        "retry_identical_class": retry["call"].get("response_class"),
        "count_after_identical": enum2["evidence"]["external_effect_count"],
        "retry_mismatched_class": retry_m["call"].get("response_class"),
        "count_final": enum3["evidence"]["external_effect_count"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
