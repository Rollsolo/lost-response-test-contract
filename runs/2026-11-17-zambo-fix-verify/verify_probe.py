#!/usr/bin/env python3
"""A5 fix live verification probe, 2026-11-17, run folder
runs/2026-11-17-zambo-fix-verify/.

Context: the crew published the lost-response recovery fix to Zambo
production on 2026-11-17. Their stated build: same job_id+params
retry replays the saved result and original receipt; changed params
refused HTTP 409 with a refusal receipt; the original receipt is
verifiable using the operation key; continuity_get_recent recovers
the saved outcome, receipt ID and digest with the same stable caller
handle; recovery records have no application TTL; ordinary
journal_log without the operation marker unaffected.

This probe verifies the fix live, TRIPLE-VERIFY standard (Brennan's
order 2026-11-17 12:06 EST): every load-bearing claim is read three
independent ways and all three must agree.

  K-only recovery, three reads:
    R1 harness adapter recover_by_key (direct lookup + K-keyed tool)
    R2 direct python-requests GET /api/v2/receipt/<K>/verify
    R3 public-record read of the receipt the recovery returned, with
       the harness's own SHA-256 recomputation over canonical bytes
  No-new-execution for each retry shape, three reads:
    C1 workflow_close snapshot attribution (adapter count_effects)
    C2 continuity_get_recent stream for the session (receipt ids)
    C3 the retry response bodies themselves (receipt ids returned)
  409 conflict refusal, three reads:
    F1 the mismatched retry response body
    F2 the refusal receipt's own public record
    F3 the unchanged effect count (C1 after the mismatched retry)

Same harness, same adapter, same target tool (journal_log), same
argument template (fixtures/harness/config.zambo.json) as runs
2026-11-16-zambo-1, 2026-11-16-zambo-2 and 2026-11-17-zambo-diag.
No payment is ever made. A payment_required response is recorded as
an observed response class, exactly as the harness records it.
"""

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

HARNESS = Path(__file__).resolve().parents[2] / "fixtures" / "harness"
sys.path.insert(0, str(HARNESS))

from adapters import load_adapter, normalize_config  # noqa: E402
from adapters.zambo import receipt_ids_of  # noqa: E402

OUT = Path(__file__).resolve().parent
ENDPOINT = "https://zambo.dev/mcp"
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(name, obj):
    (OUT / name).write_text(json.dumps(obj, indent=2, sort_keys=True),
                            encoding="utf-8")


def norm_digest(d):
    if not d:
        return None
    return d.lower().removeprefix("sha256:")


def main():
    config = normalize_config(json.loads((HARNESS / "config.zambo.json")
                                         .read_text(encoding="utf-8")))
    acfg = config["adapter_config"]
    tag = uuid.uuid4().hex[:10]
    session = f"lr-{tag}-fv"
    k_value = f"lr-op-{tag}-fv"
    obs = {"tag": tag, "session_id": session, "K": k_value,
           "started_at": utcnow()}

    adapter = load_adapter("zambo", acfg)

    # ---- (e) sanity part 1: initialize + tools/list ----------------
    init, init_summary = adapter.initialize()
    write("fv_00_initialize.json", init)
    obs["initialize_http_status"] = init_summary["http_status"]
    tl = requests.post(ENDPOINT, headers=HEADERS, timeout=60, json={
        "jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "tools/list",
        "params": {}})
    tl_body = tl.json()
    write("fv_00_tools_list.json", {"http_status": tl.status_code,
                                    "body": tl_body})
    tools = ((tl_body.get("result") or {}).get("tools") or [])
    obs["tools_list_http_status"] = tl.status_code
    obs["tools_list_count"] = len(tools)

    # ---- (a) plant -------------------------------------------------
    attempt1 = adapter.execute(session_id=session, operation_key=k_value,
                               drop_response=False)
    write("fv_attempt1_plant.json", {
        "label": "fv_attempt1_plant", "at": utcnow(), "session_id": session,
        "K": k_value, "arguments_sent": attempt1["arguments_sent"],
        "call": attempt1["call"]})
    obs["plant_response_class"] = attempt1["call"].get("response_class")
    obs["plant_receipt_ids_in_body"] = attempt1["call"].get("receipt_ids")

    enum1 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="fv_after_attempt1")
    for name, obj in (enum1.get("files") or {}).items():
        write(name, obj)
    write("count_fv_after_attempt1.json", enum1["evidence"])
    obs["count_after_attempt1"] = enum1["evidence"]["external_effect_count"]
    receipt_ids = enum1["evidence"].get("target_tool_execution_receipt_ids") or []
    obs["committed_receipt_ids"] = receipt_ids

    committed_digest = None
    if receipt_ids:
        record = adapter.fetch_record(receipt_ids[0])
        write("fv_runid_record.json", record)
        committed_digest = (record.get("digests") or {}).get("output_hash")
        obs["committed_digest"] = committed_digest
        obs["runid_recomputation"] = (record.get("recomputation") or {}).get("status")

    # ---- (b) K-only recovery, three reads --------------------------
    # R1: harness recover_by_key from a fresh client holding only K.
    fresh = load_adapter("zambo", acfg)
    finit, _ = fresh.initialize()
    write("fv_konly_initialize.json", finit)
    recovery = fresh.recover_by_key(operation_key=k_value)
    for name, obj in (recovery.get("files") or {}).items():
        write("fv_" + name, obj)
    obs["R1_attempts"] = recovery["attempts"]
    r1_lookup = recovery["files"]["a3_konly_run_lookup.json"]
    obs["R1_direct_lookup_http_status"] = r1_lookup["http_status"]
    obs["R1_direct_lookup_digests"] = r1_lookup.get("digests")
    r1_cont = recovery["files"].get("a3_konly_continuity_get_recent.json") or {}
    r1_cont_blob = json.dumps(r1_cont)
    obs["R1_continuity_class"] = r1_cont.get("response_class")
    obs["R1_continuity_has_receipt_id"] = bool(
        receipt_ids and receipt_ids[0] in r1_cont_blob)
    obs["R1_continuity_has_digest"] = bool(
        committed_digest and norm_digest(committed_digest) in r1_cont_blob.lower())

    # R2: direct python-requests GET of the crew's shipped verify path.
    r2 = requests.get(f"https://zambo.dev/api/v2/receipt/{k_value}/verify",
                      headers={"Accept": "application/json"}, timeout=30)
    try:
        r2_body = r2.json()
    except ValueError:
        r2_body = {"_non_json": r2.text[:4000]}
    write("fv_R2_direct_verify_by_key.json", {
        "url": f"https://zambo.dev/api/v2/receipt/{k_value}/verify",
        "http_status": r2.status_code, "body": r2_body})
    obs["R2_http_status"] = r2.status_code
    r2_receipt = (r2_body.get("receipt") or {}) if isinstance(r2_body, dict) else {}
    obs["R2_receipt_id"] = r2_receipt.get("id") or r2_receipt.get("receipt_id")
    obs["R2_output_hash"] = r2_receipt.get("output_hash")
    obs["R2_verification_status"] = (
        r2_body.get("verification_status") if isinstance(r2_body, dict) else None)

    # R3: public-record read of the receipt the recovery returned,
    # with digest recomputation (adapter fetch_record does both).
    r3_id = obs["R2_receipt_id"] or (receipt_ids[0] if receipt_ids else None)
    if r3_id:
        r3 = adapter.fetch_record(r3_id)
        write("fv_R3_returned_receipt_record.json", r3)
        obs["R3_receipt_id_read"] = r3_id
        obs["R3_http_status"] = r3["http_status"]
        obs["R3_digests"] = r3.get("digests")
        obs["R3_recomputation"] = (r3.get("recomputation") or {}).get("status")

    # Crew path C: continuity_get_recent recovery with the same stable
    # caller handle (fresh transport, planting client's caller handle,
    # original session id).
    fresh2 = load_adapter("zambo", acfg)
    fresh2.initialize()
    fresh2.client.caller_handle = adapter.client.caller_handle
    pathc = fresh2.client.call_tool("continuity_get_recent",
                                    {"_session_id": session})
    write("fv_pathC_continuity_stable_handle.json", pathc)
    pathc_blob = json.dumps(pathc.get("body") or {})
    obs["pathC_response_class"] = pathc.get("response_class")
    obs["pathC_has_receipt_id"] = bool(
        receipt_ids and receipt_ids[0] in pathc_blob)
    obs["pathC_has_digest"] = bool(
        committed_digest and norm_digest(committed_digest) in pathc_blob.lower())
    obs["pathC_receipt_ids"] = pathc.get("receipt_ids")

    # ---- (c) identical retry, three-way count ----------------------
    retry = adapter.execute(session_id=session, operation_key=k_value,
                            drop_response=False)
    write("fv_retry_identical.json", {
        "label": "fv_retry_identical", "at": utcnow(), "session_id": session,
        "K": k_value, "arguments_sent": retry["arguments_sent"],
        "call": retry["call"]})
    obs["retry_identical_class"] = retry["call"].get("response_class")
    obs["retry_identical_receipt_ids"] = retry["call"].get("receipt_ids")

    enum2 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="fv_after_identical")
    for name, obj in (enum2.get("files") or {}).items():
        write(name, obj)
    write("count_fv_after_identical.json", enum2["evidence"])
    obs["count_after_identical_C1"] = enum2["evidence"]["external_effect_count"]

    stream1 = adapter.client.call_tool("continuity_get_recent",
                                       {"_session_id": session})
    write("fv_stream_after_identical.json", stream1)
    obs["stream_after_identical_receipt_ids"] = stream1.get("receipt_ids")
    obs["count_after_identical_C2_stream_ids"] = stream1.get("receipt_ids")

    # ---- (d) mismatched retry, three-way count + refusal record ----
    retry_m = adapter.execute(session_id=session, operation_key=k_value,
                              mismatched=True, drop_response=False)
    write("fv_retry_mismatched.json", {
        "label": "fv_retry_mismatched", "at": utcnow(), "session_id": session,
        "K": k_value, "arguments_sent": retry_m["arguments_sent"],
        "call": retry_m["call"]})
    obs["retry_mismatched_class"] = retry_m["call"].get("response_class")
    obs["retry_mismatched_receipt_ids"] = retry_m["call"].get("receipt_ids")
    obs["retry_mismatched_http_status"] = (
        retry_m["call"].get("transport") or {}).get("http_status")
    m_blob = json.dumps(retry_m["call"].get("body") or {})
    obs["retry_mismatched_body_has_409"] = "409" in m_blob
    obs["retry_mismatched_body_has_conflict"] = "conflict" in m_blob.lower()

    enum3 = adapter.count_effects(session_id=session,
                                  operation_key=k_value,
                                  label="fv_final")
    for name, obj in (enum3.get("files") or {}).items():
        write(name, obj)
    write("count_fv_final.json", enum3["evidence"])
    obs["count_final_C1"] = enum3["evidence"]["external_effect_count"]
    obs["final_execution_receipt_ids"] = enum3["evidence"].get(
        "target_tool_execution_receipt_ids")
    obs["final_snapshot_children"] = [
        c.get("receipt_id") for c in enum3["evidence"].get("snapshot_children", [])]

    stream2 = adapter.client.call_tool("continuity_get_recent",
                                       {"_session_id": session})
    write("fv_stream_after_mismatched.json", stream2)
    obs["stream_after_mismatched_receipt_ids"] = stream2.get("receipt_ids")

    # F2: the refusal receipt's own public record. Any receipt id in
    # the mismatched body that is not the committed execution receipt
    # is a candidate refusal receipt; read each one's public record.
    candidates = [r for r in (retry_m["call"].get("receipt_ids") or [])
                  if r not in (receipt_ids or [])]
    obs["refusal_receipt_candidates"] = candidates
    for cand in candidates:
        rec = adapter.fetch_record(cand)
        write(f"fv_refusal_receipt_{cand}.json", rec)
    # Also inspect every final snapshot child that is not a counted
    # execution (a refusal record would persist in the job snapshot).
    extra_children = [c for c in obs["final_snapshot_children"]
                      if c not in (obs["final_execution_receipt_ids"] or [])]
    obs["final_snapshot_non_execution_children"] = extra_children
    for cand in extra_children:
        if cand not in candidates:
            rec = adapter.fetch_record(cand)
            write(f"fv_snapshot_child_{cand}.json", rec)

    # ---- (e) ordinary journal_log without the operation marker -----
    osession = f"lr-{tag}-ord"
    ocall = adapter.client.call_tool("journal_log", {
        "_session_id": osession,
        "action": "fix_verify_ordinary_append",
        "inputs": {"note": "ordinary journal_log append check, no operation marker"},
    })
    write("fv_ordinary_journal_log.json", ocall)
    obs["ordinary_response_class"] = ocall.get("response_class")
    obs["ordinary_receipt_ids"] = ocall.get("receipt_ids")
    if ocall.get("receipt_ids"):
        orec = adapter.fetch_record(ocall["receipt_ids"][0])
        write("fv_ordinary_receipt_record.json", orec)
        obs["ordinary_receipt_http_status"] = orec["http_status"]

    obs["finished_at"] = utcnow()
    write("fv_observations.json", obs)
    print(json.dumps(obs, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
