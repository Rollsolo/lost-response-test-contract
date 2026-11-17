#!/usr/bin/env python3
"""Delayed K-only recheck against the diagnosis plant
(K lr-op-a3f246d1fb-diag, planted 2026-11-17T16:29:01Z).

Repeats the two K-only recovery paths from a fresh client after the
longest delay this diagnosis run allows, and records the elapsed
time and exactly what came back. The 24-hour point for this plant is
2026-11-18T16:29:01Z; this recheck does not claim it.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter, normalize_config  # noqa: E402

OUT = Path(__file__).resolve().parent
K = "lr-op-a3f246d1fb-diag"
PLANTED_AT = datetime(2026, 11, 17, 16, 29, 1, tzinfo=timezone.utc)
PLANTED_RECEIPT = "141f1588-f277-48fc-999a-ac6814d760d2"
COMMITTED_DIGEST = "sha256:826aa323ddac9788a7387e1b3f22f5be2139e2b88b8ed4ae3012806df4625f0d"


def utcnow():
    return datetime.now(timezone.utc)


def main():
    config = normalize_config(json.loads((HARNESS / "config.zambo.json")
                                         .read_text(encoding="utf-8")))
    fresh = load_adapter("zambo", config["adapter_config"])
    init, _ = fresh.initialize()
    (OUT / "diag_recheck_initialize.json").write_text(
        json.dumps(init, indent=2, sort_keys=True), encoding="utf-8")
    recovery = fresh.recover_by_key(operation_key=K)
    (OUT / "diag_recheck_konly_run_lookup.json").write_text(
        json.dumps(recovery["files"]["a3_konly_run_lookup.json"],
                   indent=2, sort_keys=True), encoding="utf-8")
    cont = recovery["files"].get("a3_konly_continuity_get_recent.json")
    if cont is not None:
        (OUT / "diag_recheck_konly_continuity_get_recent.json").write_text(
            json.dumps(cont, indent=2, sort_keys=True), encoding="utf-8")
    blob = json.dumps(cont or {})
    now = utcnow()
    summary = {
        "K": K,
        "rechecked_at": now.isoformat().replace("+00:00", "Z"),
        "elapsed_seconds_since_plant": round((now - PLANTED_AT).total_seconds()),
        "attempts": recovery["attempts"],
        "planted_receipt_in_konly_stream": PLANTED_RECEIPT in blob,
        "committed_digest_in_konly_stream": COMMITTED_DIGEST in blob,
        "note": "Lower-bound probe only: the plant's 24h point is "
                "2026-11-18T16:29:01Z and is not claimed by this recheck.",
    }
    (OUT / "diag_recheck_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
