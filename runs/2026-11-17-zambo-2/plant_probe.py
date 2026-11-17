#!/usr/bin/env python3
"""Formal A5 delayed-leg plant for run 2026-11-17-zambo-2.

Planted 2026-11-17 after the short-range fix verification in
runs/2026-11-17-zambo-fix-verify/ scored (b) K-only recovery,
(c) identical-retry replay and (d) modified-parameter conflict
refusal all PASS, triple-verified. This plant follows the harness's
A1/A5 shape exactly (fixtures/harness/lost_response.py): attempt 1
of a fresh operation is sent with the response dropped client-side,
the commit is established from the durable public record
(workflow_close snapshot attribution + /api/v2/receipt/<id>/verify),
and a5_plant.json is written in the harness's own format so the
delayed leg runs with:

    python3 fixtures/harness/lost_response.py --delayed-leg \
        runs/2026-11-17-zambo-2/a5_plant.json

at or after due_at (planted_at + 24h). Run 2026-11-16-zambo-1's A5
FAIL row in RESULTS.md is historical evidence and is never edited;
this run scores as its own run section.
"""

import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
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
    adapter = load_adapter("zambo", acfg)
    init, init_summary = adapter.initialize()
    write("00_initialize.json", init)

    tag = uuid.uuid4().hex[:10]
    session = f"lr-{tag}-a1"
    k_value = f"lr-op-{tag}-a1"

    # Attempt 1: response dropped client-side, per the contract setup.
    attempt1 = adapter.execute(session_id=session, operation_key=k_value,
                               drop_response=True)
    write("a1_attempt1_dropped.json", {
        "label": "a1_attempt1_dropped", "at": utcnow(),
        "session_id": session, "K": k_value,
        "arguments_sent": attempt1["arguments_sent"],
        "call": attempt1["call"]})
    planted_at = utcnow()

    enum1 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="a1_after_attempt1")
    for name, obj in (enum1.get("files") or {}).items():
        write(name, obj)
    write("count_a1_after_attempt1.json", enum1["evidence"])
    receipt_ids = enum1["evidence"].get("target_tool_execution_receipt_ids") or []

    committed_digest = None
    if receipt_ids:
        record = adapter.fetch_record(receipt_ids[0])
        write("a3_runid_leg_receipt.json", record)
        committed_digest = (record.get("digests") or {}).get("output_hash")

    planted_dt = datetime.now(timezone.utc)
    due_at = (planted_dt + timedelta(hours=24)).isoformat().replace("+00:00", "Z")
    plant = {"assertion": "A5", "planted_at": planted_at,
             "delay_hours": 24, "due_at": due_at, "K": k_value,
             "session_id": session, "execution_receipt_ids": receipt_ids,
             "committed_digest": committed_digest,
             "endpoint": "https://zambo.dev/mcp", "adapter": "zambo",
             "system_name": config.get("system_name"),
             "adapter_config": acfg,
             "note": "Delayed leg: run the harness with --delayed-leg on "
                     "this file at or after due_at. Planted 2026-11-17 "
                     "after the production recovery fix; short-range "
                     "verification in runs/2026-11-17-zambo-fix-verify/."}
    write("a5_plant.json", plant)
    out = {"K": k_value, "session_id": session, "planted_at": planted_at,
           "due_at": due_at,
           "count_after_attempt1": enum1["evidence"]["external_effect_count"],
           "execution_receipt_ids": receipt_ids,
           "committed_digest": committed_digest}
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
