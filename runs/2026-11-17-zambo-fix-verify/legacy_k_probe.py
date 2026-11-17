#!/usr/bin/env python3
"""Legacy-K probes, 2026-11-17, part of runs/2026-11-17-zambo-fix-verify/.

Question: does the crew's recovery fix resolve K for operations
committed BEFORE the fix shipped? Two pre-fix committed operations
with known committed digests:

  run 1 A1: K lr-op-498c01b299-a1, receipt
    b49c66f5-5386-4bda-8bd6-2726bdfee7d1, committed digest
    sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970
  diagnosis plant: K lr-op-a3f246d1fb-diag, receipt
    141f1588-f277-48fc-999a-ac6814d760d2, committed digest
    sha256:826aa323ddac9788a7387e1b3f22f5be2139e2b88b8ed4ae3012806df4625f0d

Reads: (1) direct python-requests GET /api/v2/receipt/<K>/verify;
(2) harness adapter recover_by_key (direct lookup + K-keyed
continuity_get_recent). All reads are free public-record reads or
read-path tool calls; nothing executes the target tool.
"""

import json
import sys
from pathlib import Path

import requests

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter, normalize_config  # noqa: E402

OUT = Path(__file__).resolve().parent

CASES = [
    {"name": "run1_a1", "K": "lr-op-498c01b299-a1",
     "receipt_id": "b49c66f5-5386-4bda-8bd6-2726bdfee7d1",
     "committed_digest": "sha256:d832cc994b22460549e19f3ee8282de128b23103462c76d078adcc8141113970"},
    {"name": "diag_plant", "K": "lr-op-a3f246d1fb-diag",
     "receipt_id": "141f1588-f277-48fc-999a-ac6814d760d2",
     "committed_digest": "sha256:826aa323ddac9788a7387e1b3f22f5be2139e2b88b8ed4ae3012806df4625f0d"},
]


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True),
                            encoding="utf-8")


def main():
    config = normalize_config(json.loads((HARNESS / "config.zambo.json")
                                         .read_text(encoding="utf-8")))
    acfg = config["adapter_config"]
    summary = {}
    for case in CASES:
        k = case["K"]
        r = requests.get(f"https://zambo.dev/api/v2/receipt/{k}/verify",
                         headers={"Accept": "application/json"}, timeout=30)
        try:
            body = r.json()
        except ValueError:
            body = {"_non_json": r.text[:4000]}
        write(f"legacy_{case['name']}_R2_direct.json",
              {"url": f"https://zambo.dev/api/v2/receipt/{k}/verify",
               "http_status": r.status_code, "body": body})
        receipt = (body.get("receipt") or {}) if isinstance(body, dict) else {}
        adapter = load_adapter("zambo", acfg)
        adapter.initialize()
        recovery = adapter.recover_by_key(operation_key=k)
        for name, obj in (recovery.get("files") or {}).items():
            write(f"legacy_{case['name']}_" + name, obj)
        summary[case["name"]] = {
            "K": k,
            "R2_http_status": r.status_code,
            "R2_receipt_id": receipt.get("id") or receipt.get("receipt_id"),
            "R2_output_hash": receipt.get("output_hash"),
            "expected_receipt_id": case["receipt_id"],
            "expected_digest": case["committed_digest"],
            "R1_attempts": recovery["attempts"],
        }
    write("legacy_k_summary.json", summary)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
