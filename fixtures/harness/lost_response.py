#!/usr/bin/env python3
"""Lost-response recovery harness for the contract in ../../CONTRACT.md.

Runs assertions A1 to A5 against a configurable MCP endpoint.

Fault model (from CONTRACT.md, common setup): attempt 1's request is
sent and the server commits its effect, but the harness discards the
response client-side and treats the attempt as lost. Only transport
metadata (timestamps, HTTP status, byte count, JSON-RPC id) is recorded
for a dropped attempt: no body, no result, no receipt id, no digest.
Retries use a fresh JSON-RPC request id, as MCP requires.

External effect counter (fixtures/README.md): the count of distinct
committed executions visible in the system's durable public record,
attributed to the run by a fresh run-scoped session identity and to the
logical operation by K. For Zambo the public record is the public
receipt record at <public_base>/run/<receipt_id>; the harness
enumerates the receipt-backed record for the session through free read
paths and then checks every counted identifier directly against that
public record.

Transport note: this harness uses python `requests` with the header
Accept: application/json only. That is the transport proven to work
from restricted networks against the default endpoint; do not switch
it to urllib.

Usage:
    python3 lost_response.py --config config.zambo.json --out ../../runs/<dir>
    python3 lost_response.py --delayed-leg ../../runs/<dir>/a5_plant.json

No payment is ever made. A payment_required response is recorded as an
observed response class and the affected assertion is scored unproven
when the refusal happened before any commit, per the contract's
scoring rules.
"""

import argparse
import hashlib
import json
import re
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

import requests

MCP_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class RunWriter:
    def __init__(self, out_dir):
        self.dir = Path(out_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def write(self, name, obj):
        path = self.dir / name
        if isinstance(obj, str):
            path.write_text(obj, encoding="utf-8")
        else:
            path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")
        return str(path)


class McpClient:
    """Minimal MCP client over Streamable HTTP using requests."""

    def __init__(self, endpoint):
        self.endpoint = endpoint
        self.session = requests.Session()
        self.caller_handle = None

    def _post(self, payload):
        started = time.time()
        sent_at = utcnow()
        resp = self.session.post(
            self.endpoint, headers=MCP_HEADERS, json=payload, timeout=60
        )
        elapsed_ms = round((time.time() - started) * 1000)
        meta = {
            "sent_at": sent_at,
            "received_at": utcnow(),
            "elapsed_ms": elapsed_ms,
            "http_status": resp.status_code,
            "content_length_header": resp.headers.get("Content-Length"),
            "response_bytes": len(resp.content),
            "jsonrpc_id": payload.get("id"),
        }
        try:
            body = resp.json()
        except ValueError:
            body = {"_non_json_body": resp.text[:4000]}
        return meta, body

    def initialize(self):
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "lost-response-harness", "version": "1.0.0"},
            },
        }
        meta, body = self._post(payload)
        result = body.get("result") or {}
        meta_block = result.get("meta") or result.get("_meta") or {}
        self.caller_handle = meta_block.get("caller_handle")
        return {"transport": meta, "body": body}

    def call_tool(self, name, arguments, drop_response=False):
        """Call a tool. When drop_response is True the body is discarded
        and only transport metadata is returned, simulating the lost
        response: the server committed, the caller perceived a loss."""
        args = dict(arguments)
        if self.caller_handle and "_caller_handle" not in args:
            args["_caller_handle"] = self.caller_handle
        payload = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "tools/call",
            "params": {"name": name, "arguments": args},
        }
        meta, body = self._post(payload)
        if drop_response:
            return {
                "dropped": True,
                "transport": meta,
                "note": "Response body discarded client-side by the fault "
                        "injector. No result, receipt id, or digest from "
                        "this attempt is available to the caller.",
            }
        return {"dropped": False, "transport": meta, "body": body,
                "response_class": classify(body), "receipt_ids": receipt_ids_of(body)}


def classify(body):
    """Classify a tools/call response body into the classes A4 records."""
    if not isinstance(body, dict):
        return "unparseable"
    if "error" in body and body.get("error"):
        err = body["error"]
        msg = json.dumps(err).lower()
        if "payment" in msg:
            return "payment_required"
        return "jsonrpc_error:" + str(err.get("code", "unknown"))
    result = body.get("result") or {}
    structured = result.get("structuredContent") or {}
    if isinstance(structured, dict) and structured:
        if structured.get("ok") is True:
            return "success"
        err = structured.get("error") or {}
        code = str(err.get("code", "")).lower()
        if "payment" in code:
            return "payment_required"
        if code:
            return "tool_error:" + code
        if structured.get("ok") is False:
            return "tool_error:unspecified"
    if result.get("isError"):
        text = json.dumps(result).lower()
        if "payment_required" in text or "payment required" in text:
            return "payment_required"
        return "tool_error:isError"
    if result:
        return "success"
    return "empty_result"


def receipt_ids_of(body):
    """Receipt identifiers carried in a tools/call response body."""
    found = []
    def walk(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str):
                    for m in re.finditer(r"/run/([A-Za-z0-9_-]+)", value):
                        found.append(m.group(1))
                    if key in ("receipt_id", "run_id") and len(value) >= 6:
                        found.append(value)
                else:
                    walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(body)
    seen, out = set(), []
    for item in found:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def receipt_entries_of(body):
    """(receipt_id, tool_hint) pairs from an enumeration response."""
    entries = []
    def walk(node):
        if isinstance(node, dict):
            ids_here = []
            tool_hint = None
            for key, value in node.items():
                if isinstance(value, str):
                    for m in re.finditer(r"/run/([A-Za-z0-9_-]+)", value):
                        ids_here.append(m.group(1))
                    if key in ("receipt_id", "run_id") and len(value) >= 6:
                        ids_here.append(value)
                    if key in ("tool_name", "tool") and value:
                        tool_hint = value
                else:
                    walk(value)
            for rid in ids_here:
                entries.append({"receipt_id": rid, "tool_hint": tool_hint})
        elif isinstance(node, list):
            for item in node:
                walk(item)
    walk(body)
    seen, out = set(), []
    for e in entries:
        key = (e["receipt_id"], e["tool_hint"])
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


class PublicRecord:
    """Reads against the durable public record (receipt pages)."""

    def __init__(self, public_base):
        self.base = public_base.rstrip("/")
        self.session = requests.Session()

    def fetch_receipt(self, receipt_id):
        url = f"{self.base}/run/{receipt_id}"
        started = time.time()
        resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=30)
        record = {
            "receipt_id": receipt_id,
            "url": url,
            "fetched_at": utcnow(),
            "http_status": resp.status_code,
            "elapsed_ms": round((time.time() - started) * 1000),
            "content_type": resp.headers.get("Content-Type"),
            "body_text": resp.text[:20000],
        }
        record["digests_found"] = extract_digests(resp.text)
        record["recomputation"] = recompute_digest(resp.text)
        return record

    def resolves(self, receipt_id):
        url = f"{self.base}/run/{receipt_id}"
        resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=30)
        return resp.status_code == 200


def extract_digests(text):
    """Digest values named in a receipt record, as served."""
    out = {}
    for field in ("result_digest", "output_digest", "digest", "result_hash",
                  "canonical_digest", "content_digest"):
        m = re.search(r'"%s"\s*:\s*"([0-9a-fA-F]{32,64})"' % field, text)
        if m:
            out[field] = m.group(1).lower()
    return out


def recompute_digest(text):
    """AER-1 Section 6 style recomputation, best effort and honest:
    if the record parses as JSON and carries both a result value and a
    named digest, recompute SHA-256 over the canonical JSON of the
    result and compare. Otherwise report why recomputation is not
    computable from the public record alone."""
    try:
        record = json.loads(text)
    except ValueError:
        return {"status": "not_computable",
                "reason": "public record is not a JSON document at this URL; "
                          "digest fields were extracted as served instead"}
    if not isinstance(record, dict):
        return {"status": "not_computable", "reason": "record is not a JSON object"}
    digests = {}
    for field in ("result_digest", "output_digest", "digest", "result_hash",
                  "canonical_digest", "content_digest"):
        value = record.get(field)
        if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{32,64}", value):
            digests[field] = value.lower()
    result_value = None
    for key in ("result", "output", "saved_result"):
        if key in record:
            result_value = record[key]
            break
    if not digests:
        return {"status": "not_computable",
                "reason": "record carries no named digest field at top level",
                "record_keys": sorted(record.keys())}
    if result_value is None:
        return {"status": "not_computable",
                "reason": "record carries a digest but no result value to recompute from",
                "digests_served": digests,
                "record_keys": sorted(record.keys())}
    computed = sha256_hex(canonical_json(result_value))
    matched = [f for f, v in digests.items() if v == computed]
    return {"status": "matched" if matched else "mismatched",
            "computed_sha256_canonical_result": computed,
            "digests_served": digests,
            "matched_fields": matched}


def substitute(template, values):
    if isinstance(template, str):
        out = template
        for key, value in values.items():
            out = out.replace("{" + key + "}", value)
        return out
    if isinstance(template, dict):
        return {k: substitute(v, values) for k, v in template.items()}
    if isinstance(template, list):
        return [substitute(v, values) for v in template]
    return template


class Harness:
    def __init__(self, config, writer):
        self.cfg = config
        self.w = writer
        self.client = McpClient(config["endpoint"])
        self.public = PublicRecord(config.get("public_base", config["endpoint"]))
        self.run_tag = uuid.uuid4().hex[:10]
        self.summary = {"run_tag": self.run_tag, "started_at": utcnow(),
                        "endpoint": config["endpoint"], "tool": config["tool"],
                        "assertions": {}}

    # -- counter -----------------------------------------------------
    def enumerate_session(self, session_id, label):
        """Enumerate the receipt-backed record for a session through
        free read paths and check each candidate against the public
        record. Returns the counting evidence."""
        evidence = {"label": label, "session_id": session_id, "at": utcnow(),
                    "paths": {}}
        candidates = {}
        enum_tools = self.cfg.get("enumerate_tools", [])
        for spec in enum_tools:
            args = substitute(spec.get("arguments", {}),
                              {"SESSION": session_id, "K": session_id})
            call = self.client.call_tool(spec["name"], args)
            self.w.write(f"enum_{label}_{spec['name']}.json", call)
            evidence["paths"][spec["name"]] = {
                "response_class": call.get("response_class"),
                "entries": receipt_entries_of(call.get("body", {})),
            }
            for entry in evidence["paths"][spec["name"]]["entries"]:
                candidates.setdefault(entry["receipt_id"], set()).add(entry["tool_hint"])
            for rid in call.get("receipt_ids", []):
                candidates.setdefault(rid, set()).add(spec["name"] + " (self)")
        checked = []
        for rid, hints in sorted(candidates.items()):
            ok = self.public.resolves(rid)
            checked.append({"receipt_id": rid, "tool_hints": sorted(h for h in hints if h),
                            "resolves_in_public_record": ok})
        evidence["candidates"] = checked
        target = self.cfg["tool"]
        execution_ids = []
        for item in checked:
            if not item["resolves_in_public_record"]:
                continue
            hints = item["tool_hints"]
            if not hints or target in hints:
                execution_ids.append(item["receipt_id"])
        evidence["target_tool_execution_receipt_ids"] = execution_ids
        evidence["external_effect_count"] = len(execution_ids)
        self.w.write(f"count_{label}.json", evidence)
        return evidence

    # -- one logical operation --------------------------------------
    def attempt(self, session_id, k_value, args_template, drop, label, values_extra=None):
        values = {"K": k_value, "SESSION": session_id}
        if values_extra:
            values.update(values_extra)
        args = substitute(args_template, values)
        call = self.client.call_tool(self.cfg["tool"], args, drop_response=drop)
        record = {"label": label, "at": utcnow(), "session_id": session_id,
                  "K": k_value, "arguments_sent": args, "call": call}
        self.w.write(f"{label}.json", record)
        return record

    def run(self):
        init = self.client.initialize()
        self.w.write("00_initialize.json", init)
        self.summary["initialize"] = {"http_status": init["transport"]["http_status"],
                                      "caller_handle_issued": bool(self.client.caller_handle)}
        cfg = self.cfg
        a1 = self._run_a1(cfg)
        a2 = self._run_a2(cfg)
        a3 = self._run_a3(cfg, a1)
        self._run_a4(a1, a2)
        self._run_a5(cfg, a1, a3)
        self.summary["finished_at"] = utcnow()
        self.w.write("summary.json", self.summary)
        self.w.write("RESULTS-snippet.md", results_snippet(self.summary))
        return self.summary

    def _run_a1(self, cfg):
        session = f"lr-{self.run_tag}-a1"
        k_value = f"lr-op-{self.run_tag}-a1"
        attempt1 = self.attempt(session, k_value, cfg["args_template"],
                                drop=True, label="a1_attempt1_dropped")
        count_after_1 = self.enumerate_session(session, "a1_after_attempt1")
        retry = self.attempt(session, k_value, cfg["args_template"],
                             drop=False, label="a1_retry_identical")
        count_final = self.enumerate_session(session, "a1_final")
        committed_1 = count_after_1["external_effect_count"] >= 1
        final_count = count_final["external_effect_count"]
        retry_class = retry["call"].get("response_class")
        if not committed_1 and retry_class == "payment_required":
            score, reason = "unproven", "attempt 1 was refused before any commit (payment_required class observed in the run); the lost-response precondition never occurred"
        elif not committed_1:
            score, reason = "unproven", "no committed execution for attempt 1 is visible in the public record, so the lost-response precondition is not established"
        elif final_count == 1:
            score, reason = "pass", "external effect count for the logical operation is exactly 1"
        else:
            score, reason = "fail", f"external effect count for the logical operation is {final_count}, not 1"
        result = {"score": score, "reason": reason,
                  "count_after_attempt1": count_after_1["external_effect_count"],
                  "final_external_effect_count": final_count,
                  "retry_response_class": retry_class,
                  "session_id": session, "K": k_value,
                  "execution_receipt_ids": count_final["target_tool_execution_receipt_ids"]}
        self.summary["assertions"]["A1"] = result
        return result

    def _run_a2(self, cfg):
        session = f"lr-{self.run_tag}-a2"
        k_value = f"lr-op-{self.run_tag}-a2"
        attempt1 = self.attempt(session, k_value, cfg["args_template"],
                                drop=True, label="a2_attempt1_dropped")
        count_after_1 = self.enumerate_session(session, "a2_after_attempt1")
        mismatch_template = dict(cfg["args_template"])
        field = cfg["mismatch"]["field"]
        mismatch_template[field] = cfg["mismatch"]["altered_value"]
        retry = self.attempt(session, k_value, mismatch_template,
                             drop=False, label="a2_retry_mismatched")
        count_final = self.enumerate_session(session, "a2_final")
        committed_1 = count_after_1["external_effect_count"] >= 1
        final_count = count_final["external_effect_count"]
        retry_class = retry["call"].get("response_class")
        explicit_rejection = retry_class not in ("success", None) and retry_class != "payment_required"
        if not committed_1:
            score, reason = "unproven", "attempt 1 did not commit visibly in the public record, so the mismatched-retry precondition is not established"
        elif final_count == count_after_1["external_effect_count"] and explicit_rejection:
            score, reason = "pass", "mismatched retry produced no new effect and was explicitly refused"
        elif final_count > count_after_1["external_effect_count"]:
            score, reason = "fail", f"mismatched retry executed as a new call: effect count rose from {count_after_1['external_effect_count']} to {final_count}, response class {retry_class}"
        elif retry_class == "success":
            score, reason = "fail", "mismatched retry returned a generic success with no binding rejection recorded"
        else:
            score, reason = "unproven", f"retry response class {retry_class} with unchanged count; cannot distinguish a binding rejection from a generic error from the raw output alone"
        result = {"score": score, "reason": reason,
                  "count_after_attempt1": count_after_1["external_effect_count"],
                  "final_external_effect_count": final_count,
                  "retry_response_class": retry_class,
                  "mismatched_field": field,
                  "session_id": session, "K": k_value,
                  "execution_receipt_ids": count_final["target_tool_execution_receipt_ids"]}
        self.summary["assertions"]["A2"] = result
        return result

    def _run_a3(self, cfg, a1):
        """Both legs. Run-id leg: the caller holds the server-issued run
        id (a receipt id from the public record for the A1 operation),
        resolves the record, and checks the digest. K-only leg: a fresh
        recovery caller holds only K: no run id, response, result, or
        digest from attempt 1."""
        out = {"legs": {}}
        receipt_ids = a1.get("execution_receipt_ids") or []
        if receipt_ids:
            record = self.public.fetch_receipt(receipt_ids[0])
            self.w.write("a3_runid_leg_receipt.json", record)
            digests = record["digests_found"]
            recomp = record["recomputation"]
            leg_pass = record["http_status"] == 200 and bool(digests) and recomp["status"] in ("matched", "not_computable")
            out["legs"]["run_id"] = {
                "receipt_id": receipt_ids[0], "http_status": record["http_status"],
                "digests_served": digests, "recomputation": recomp,
                "score": "pass" if leg_pass else "fail",
                "note": "Section 9 resolution returned the record; digest evidence is the served digest plus the recomputation outcome recorded here. A not_computable recomputation means the public record at this URL does not expose the canonical inputs, and that limit is recorded rather than rounded into a pass on recomputation itself.",
            }
            committed_digest = next(iter(digests.values()), None)
        else:
            out["legs"]["run_id"] = {"score": "unproven",
                                     "note": "no committed receipt id exists for the A1 operation, so the run-id leg cannot execute"}
            committed_digest = None
        # K-only leg: only K is used. No run id, response, result, digest.
        k_value = a1["K"]
        konly = {"K": k_value, "attempts": []}
        rec = self.public.fetch_receipt(k_value)
        self.w.write("a3_konly_run_lookup.json", rec)
        konly["attempts"].append({"path": "GET /run/<K>",
                                  "http_status": rec["http_status"],
                                  "response_class": "found" if rec["http_status"] == 200 else "not_found"})
        for spec in cfg.get("konly_lookup_tools", []):
            args = substitute(spec.get("arguments", {}), {"K": k_value, "SESSION": k_value})
            call = self.client.call_tool(spec["name"], args)
            self.w.write(f"a3_konly_{spec['name']}.json", call)
            konly["attempts"].append({"path": f"tools/call {spec['name']} with K as the only identifier",
                                      "response_class": call.get("response_class"),
                                      "receipt_ids_returned": call.get("receipt_ids", [])})
        recovered_digest = None
        for attempt in konly["attempts"]:
            if attempt.get("response_class") == "found":
                recovered_digest = committed_digest
        if committed_digest and recovered_digest == committed_digest:
            konly["score"] = "pass"
            konly["reason"] = "recovered digest equals committed digest using only K"
        elif any(a.get("http_status") == 404 or a.get("response_class") in ("not_found",) for a in konly["attempts"]) and not recovered_digest:
            konly["score"] = "fail"
            konly["reason"] = "K-only recovery did not return the original committed outcome; the direct record lookup by K returned not found and no K-keyed lookup returned the committed digest"
        else:
            konly["score"] = "fail" if committed_digest else "unproven"
            konly["reason"] = "K-only recovery did not return a digest equal to the committed digest" if committed_digest else "no committed digest exists, so K-only recovery cannot be scored"
        out["legs"]["k_only"] = konly
        out["score"] = konly["score"]
        out["reason"] = ("contract pass condition is the K-only leg: " + konly["reason"] +
                         f"; run-id leg scored {out['legs']['run_id']['score']} separately in the evidence")
        out["committed_digest"] = committed_digest
        self.summary["assertions"]["A3"] = out
        self.w.write("a3_summary.json", out)
        return out

    def _run_a4(self, a1, a2):
        classes = {"A1_retry": a1.get("retry_response_class"),
                   "A2_retry": a2.get("retry_response_class")}
        allowed_explicit = lambda c: c and (c.startswith("tool_error:") or c.startswith("jsonrpc_error:"))
        verdicts = {}
        for name, cls in classes.items():
            if cls == "success":
                verdicts[name] = "success corresponding to a committed record (see the A1/A2 counts); not a generic success with no record"
            elif allowed_explicit(cls):
                verdicts[name] = "explicit non-success state"
            elif cls == "payment_required":
                verdicts[name] = "explicit non-success state naming the situation (payment_required)"
            else:
                verdicts[name] = f"unclassifiable response class: {cls}"
        if any(v.startswith("unclassifiable") for v in verdicts.values()):
            score = "unproven"
        else:
            score = "pass"
        result = {"score": score, "response_classes": classes, "verdicts": verdicts,
                  "reason": "every recorded retry resolved to the original outcome, a digest-verifiable record of it, or an explicit non-success state" if score == "pass" else "at least one retry response class could not be classified from the raw output"}
        self.summary["assertions"]["A4"] = result
        return result

    def _run_a5(self, cfg, a1, a3):
        plant = {"assertion": "A5", "planted_at": utcnow(),
                 "delay_hours": cfg.get("a5_delay_hours", 24),
                 "due_at": None, "K": a1["K"], "session_id": a1["session_id"],
                 "execution_receipt_ids": a1.get("execution_receipt_ids", []),
                 "committed_digest": a3.get("committed_digest"),
                 "endpoint": cfg["endpoint"],
                 "note": "Delayed leg: run this harness with --delayed-leg on this file at or after due_at. The delay is measured from the original commit time (planted_at approximates it within the run; the exact attempt 1 send time is in a1_attempt1_dropped.json)."}
        from datetime import timedelta
        planted = datetime.now(timezone.utc)
        plant["due_at"] = (planted + timedelta(hours=plant["delay_hours"])).isoformat().replace("+00:00", "Z")
        self.w.write("a5_plant.json", plant)
        result = {"score": "unproven",
                  "reason": "the 24 hour delayed leg cannot complete on the planting day; attempt 1 is planted with its commit timestamp recorded and the delayed leg is runnable later by run id and by K",
                  "plant_file": "a5_plant.json", "due_at": plant["due_at"]}
        self.summary["assertions"]["A5"] = result
        return result


def results_snippet(summary):
    lines = [f"Run {summary['run_tag']} against {summary['endpoint']} "
             f"(tool {summary['tool']}), started {summary['started_at']}.",
             "", "| Assertion | Outcome | Evidence |", "|---|---|---|"]
    for name in ("A1", "A2", "A3", "A4", "A5"):
        a = summary["assertions"].get(name, {})
        lines.append(f"| {name} | {a.get('score', 'unproven')} | {a.get('reason', '')} |")
    return "\n".join(lines) + "\n"


def delayed_leg(plant_path):
    plant = json.loads(Path(plant_path).read_text(encoding="utf-8"))
    out_dir = Path(plant_path).parent
    writer = RunWriter(out_dir)
    public = PublicRecord(plant.get("endpoint", "https://zambo.dev/mcp").rsplit("/mcp", 1)[0])
    result = {"assertion": "A5", "delayed_leg_run_at": utcnow(), "plant": plant,
              "legs": {}}
    ids = plant.get("execution_receipt_ids") or []
    if ids:
        record = public.fetch_receipt(ids[0])
        writer.write("a5_delayed_runid_receipt.json", record)
        digests = record["digests_found"]
        served = next(iter(digests.values()), None)
        result["legs"]["run_id"] = {"http_status": record["http_status"],
                                    "digest_served": served,
                                    "committed_digest": plant.get("committed_digest"),
                                    "digest_equal": bool(served and plant.get("committed_digest") and served == plant["committed_digest"]),
                                    "recomputation": record["recomputation"]}
    rec = public.fetch_receipt(plant["K"])
    result["legs"]["k_only_direct_lookup"] = {"http_status": rec["http_status"]}
    runid_ok = result["legs"].get("run_id", {}).get("digest_equal")
    result["score"] = "pass" if runid_ok and rec["http_status"] == 200 else "fail"
    if not ids:
        result["score"] = "unproven"
        result["reason"] = "plant carries no committed receipt id"
    else:
        result["reason"] = "scored from the delayed run-id digest equality and the K-only lookup, exactly as observed; see a5_delayed_result.json"
    writer.write("a5_delayed_result.json", result)
    print(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).parent / "config.zambo.json"))
    parser.add_argument("--out", default=None, help="run output directory")
    parser.add_argument("--delayed-leg", default=None, help="path to a5_plant.json")
    args = parser.parse_args()
    if args.delayed_leg:
        delayed_leg(args.delayed_leg)
        return 0
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    out = args.out or str(Path.cwd() / ("run-" + utcnow().replace(":", "").replace("-", "")))
    writer = RunWriter(out)
    harness = Harness(config, writer)
    summary = harness.run()
    print(json.dumps(summary, indent=2))
    print(f"\nRaw outputs in {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
