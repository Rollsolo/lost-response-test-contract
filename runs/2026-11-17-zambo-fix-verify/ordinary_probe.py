#!/usr/bin/env python3
"""Ordinary journal_log regression re-probe, 2026-11-17, part of
runs/2026-11-17-zambo-fix-verify/.

The first ordinary probe (fv_ordinary_journal_log.json) omitted two
schema-required arguments (job_id, executor_identity) and was refused
invalid_tool_arguments; that refusal is a probe defect, recorded as
such. This re-probe sends a complete ordinary journal_log call: its
own job_id, an action, and inputs WITHOUT the operation marker (no
inputs.operation binding). Crew claim under test: ordinary
journal_log calls without the matching operation marker remain
appendable. A second identical ordinary call checks that an unmarked
job also does not replay (it must append a second entry or follow
the tool's normal semantics; what is observed is recorded).
"""

import json
import sys
import uuid
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter, normalize_config  # noqa: E402

OUT = Path(__file__).resolve().parent


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True),
                            encoding="utf-8")


def main():
    config = normalize_config(json.loads((HARNESS / "config.zambo.json")
                                         .read_text(encoding="utf-8")))
    acfg = config["adapter_config"]
    adapter = load_adapter("zambo", acfg)
    adapter.initialize()
    tag = uuid.uuid4().hex[:10]
    session = f"lr-{tag}-ord2"
    args = {"_session_id": session,
            "action": "fix_verify_ordinary_append",
            "executor_identity": "lost-response-harness",
            "inputs": {"note": "ordinary append, no operation marker"},
            "job_id": f"ordinary-job-{tag}"}
    call1 = adapter.client.call_tool("journal_log", args)
    write("fv_ordinary2_call1.json", call1)
    call2 = adapter.client.call_tool("journal_log", dict(args))
    write("fv_ordinary2_call2.json", call2)
    out = {"job_id": args["job_id"],
           "call1_class": call1.get("response_class"),
           "call1_receipt_ids": call1.get("receipt_ids"),
           "call2_class": call2.get("response_class"),
           "call2_receipt_ids": call2.get("receipt_ids")}
    sc = (((call1.get("body") or {}).get("result") or {})
          .get("structuredContent") or {})
    out["call1_status"] = sc.get("status")
    out["call1_idempotent_replay"] = sc.get("idempotent_replay")
    write("fv_ordinary2_summary.json", out)
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
