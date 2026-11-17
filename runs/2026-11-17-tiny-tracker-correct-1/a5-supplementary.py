"""Supplementary A5 evidence for tiny-tracker (not driver output, not a score).

The driver's --delayed-leg reads the record by id and calls
fetch_record(K); it does not call recover_by_key(). tiny-tracker serves
no digest and has no record addressable by K, so the delayed leg cannot
show whether the key is still recognized at +24 h. This script records
that observation separately, at or after the plant's due_at:

1. The adapter's recover_by_key() for the planted K: list_tickets by
   title prefix K (a read), then a same-key replay of create_ticket with
   the caller's own original arguments (K plus A; a write call), with the
   counter read before and after. The caller's own arguments are seeded
   from the run's a1_attempt1_dropped.json (the caller's own request log;
   nothing response-derived).
2. One changed-arguments retry with the same K (the A2 mismatch), with
   the counter read before and after, to observe whether the identity is
   still protected against fresh execution with modified parameters.

Output: <run-dir>/a5_supplementary_konly.json.

Usage (TRACKER_BACKEND_TOKEN set to the build's token), from the repo root:
  python3 runs/2026-11-17-tiny-tracker-correct-1/a5-supplementary.py runs/2026-11-17-tiny-tracker-correct-1
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def parse_utc(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso_z(moment):
    return moment.isoformat().replace("+00:00", "Z")


if len(sys.argv) != 2:
    sys.exit("usage: a5-supplementary.py <run-dir>")

run = Path(sys.argv[1]).resolve()
harness = run.parent.parent / "fixtures" / "harness"
sys.path.insert(0, str(harness))
from adapters import load_adapter  # noqa: E402

plant = json.loads((run / "a5_plant.json").read_text())
attempt1 = json.loads((run / "a1_attempt1_dropped.json").read_text())

now = datetime.now(timezone.utc)
if now < parse_utc(plant["due_at"]):
    sys.exit(f"Not due yet: now {iso_z(now)}, due_at {plant['due_at']} "
             f"(a5_plant.json). Run this at or after due_at. Nothing was sent.")

attempt1_sent_at = attempt1["call"]["transport"]["sent_at"]
elapsed_hours = (now - parse_utc(attempt1_sent_at)).total_seconds() / 3600

K = plant["K"]
session_id = attempt1["session_id"]
adapter = load_adapter(plant["adapter"], plant["adapter_config"])
adapter.sent_args[K] = {"arguments": attempt1["arguments_sent"],
                        "session_id": session_id}

# 1. The adapter's recovery paths: the read by K, then the identical same-key replay.
out = adapter.recover_by_key(operation_key=K)

# 2. One changed-arguments retry with the same K, counter read before and after.
before = adapter.count_effects(session_id=session_id, operation_key=K,
                               label="a5_supplementary_before_changed_retry")
changed = adapter.execute(session_id=session_id, operation_key=K, mismatched=True)
after = adapter.count_effects(session_id=session_id, operation_key=K,
                              label="a5_supplementary_after_changed_retry")
count_before = before["evidence"]["external_effect_count"]
count_after = after["evidence"]["external_effect_count"]
changed_retry = {
    "arguments_sent": changed["arguments_sent"],
    "call": changed["call"],
    "response_class": changed["call"].get("response_class"),
    "effect_count_before": count_before,
    "effect_count_after": count_after,
    "execution_record_ids_before": before["evidence"]["execution_record_ids"],
    "execution_record_ids_after": after["evidence"]["execution_record_ids"],
    "new_effect": count_after > count_before,
    "count_evidence_before": before["evidence"],
    "count_evidence_after": after["evidence"],
    "listings": {**before["files"], **after["files"]},
}

record = {"assertion": "A5 supplementary: same-key replay with the caller's own "
                       "arguments (not driver output, not a score)",
          "written_by": "a5-supplementary.py",
          "run_at": iso_z(now),
          "K": K, "due_at": plant["due_at"],
          "attempt1_sent_at": attempt1_sent_at,
          "elapsed_hours_since_attempt1_sent": round(elapsed_hours, 3),
          "committed_record_ids_in_plant": plant["execution_receipt_ids"],
          "attempts": out["attempts"], "files": out["files"],
          "changed_arguments_retry": changed_retry}
(run / "a5_supplementary_konly.json").write_text(json.dumps(record, indent=2, sort_keys=True))
print(json.dumps({"attempts": out["attempts"],
                  "changed_arguments_retry": {
                      "response_class": changed_retry["response_class"],
                      "effect_count_before": count_before,
                      "effect_count_after": count_after,
                      "new_effect": changed_retry["new_effect"]}}, indent=2))
