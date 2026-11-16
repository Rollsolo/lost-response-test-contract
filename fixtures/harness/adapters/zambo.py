"""Zambo adapter for the lost-response harness.

Implements the adapter contract in base.py against Zambo production:
an MCP endpoint (https://zambo.dev/mcp) whose durable public record
is the public AER-1 receipt record. This is the adapter the recorded
runs in ../../../runs/ were executed with; it was extracted from the
original harness without behavior changes, and the 2026-11-16
adapter-refactor run (runs/2026-11-16-zambo-2/) reproduces the
original run's scores through it.

Adapter config keys (the config's adapter_config object):
  endpoint            MCP endpoint to test.
  public_base         Base URL of the durable public record.
  tool                The target mutating tool (journal_log; see
                      ../README.md for the choice rationale).
  args_template       Arguments A for the target tool, with {K} for
                      the stable operation identity and {SESSION} for
                      the fresh run-scoped session identity.
  mismatch            {"field", "altered_value"}: the one parameter
                      A2 changes.
  konly_lookup_tools  Tool-call lookup paths tried by the K-only
                      recovery leg, each {"name", "arguments"} with
                      {K} and {SESSION} placeholders.

Transport note: this adapter uses python `requests` with the header
Accept: application/json only. That is the transport proven to work
from restricted networks against the endpoint; do not switch it to
urllib.

The counter: the count of distinct committed executions visible in
the public receipt record, enumerated through a workflow snapshot of
the job's persisted receipts and attributed child by child through
each child's public JSON record (../../../fixtures/README.md).
"""

import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone

import requests

from .base import SystemAdapter

MCP_HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


class PublicRecord:
    """Reads against the durable public record.

    Two public surfaces per receipt: the human page at /run/<id> (which
    answers HTTP 200 with a "Receipt not found" page for unknown ids,
    so its status alone proves nothing) and the JSON record at
    /api/v2/receipt/<id>/verify (which answers a real 404 with
    receipt_not_found for unknown ids). Resolution and digest work use
    the JSON record; the page is recorded as served."""

    def __init__(self, public_base):
        self.base = public_base.rstrip("/")
        self.session = requests.Session()

    def fetch_receipt(self, receipt_id):
        page_url = f"{self.base}/run/{receipt_id}"
        api_url = f"{self.base}/api/v2/receipt/{receipt_id}/verify"
        started = time.time()
        page = self.session.get(page_url, headers={"Accept": "text/html"}, timeout=30)
        api = self.session.get(api_url, headers={"Accept": "application/json"}, timeout=30)
        record = {
            "receipt_id": receipt_id,
            "page_url": page_url,
            "page_http_status": page.status_code,
            "page_title_not_found": "Receipt not found" in page.text[:2000],
            "api_url": api_url,
            "fetched_at": utcnow(),
            "http_status": api.status_code,
            "elapsed_ms": round((time.time() - started) * 1000),
            "content_type": api.headers.get("Content-Type"),
            "body_text": api.text[:40000],
        }
        try:
            record["record_json"] = api.json()
        except ValueError:
            record["record_json"] = None
        record["digests_found"] = extract_digests(api.text)
        record["digests"] = record["digests_found"]
        record["recomputation"] = recompute_digest(api.text)
        return record

    def resolves(self, receipt_id):
        url = f"{self.base}/api/v2/receipt/{receipt_id}/verify"
        resp = self.session.get(url, headers={"Accept": "application/json"}, timeout=30)
        return resp.status_code == 200


def extract_digests(text):
    """Digest values named in a receipt record, as served. For Zambo
    records the result digest is the receipt's output_hash and the
    input commitment is its input_hash."""
    out = {}
    try:
        doc = json.loads(text)
    except ValueError:
        doc = None
    if isinstance(doc, dict) and isinstance(doc.get("receipt"), dict):
        receipt = doc["receipt"]
        for field in ("output_hash", "input_hash", "evidence_sha256", "state_hash"):
            value = receipt.get(field)
            if isinstance(value, str) and value:
                out[field] = value.lower()
        return out
    for field in ("result_digest", "output_digest", "digest", "result_hash",
                  "canonical_digest", "content_digest"):
        m = re.search(r'"%s"\s*:\s*"([0-9a-fA-F]{32,64})"' % field, text)
        if m:
            out[field] = m.group(1).lower()
    return out


def recompute_digest(text):
    """AER-1 Section 6 recomputation from the public record.

    Zambo records carry the canonical bytes (base64) and the
    output_hash they commit to: the commitment check is SHA-256 of the
    exact decoded canonical bytes equals output_hash. The harness
    recomputes that itself from the served record, and also records
    the record's own verification status and checks as served."""
    try:
        doc = json.loads(text)
    except ValueError:
        return {"status": "not_computable",
                "reason": "public record at the JSON URL is not a JSON document"}
    if not isinstance(doc, dict) or not isinstance(doc.get("receipt"), dict):
        return {"status": "not_computable",
                "reason": "record does not carry a receipt object",
                "record_keys": sorted(doc.keys()) if isinstance(doc, dict) else []}
    receipt = doc["receipt"]
    out = {"verification_status_served": doc.get("verification_status"),
           "checks_served": doc.get("checks")}
    output_hash = (receipt.get("output_hash") or "").lower().removeprefix("sha256:")
    canonical_b64 = receipt.get("canonical_bytes")
    if receipt.get("canonical_bytes_withheld_for_privacy") or not canonical_b64:
        out["status"] = "not_computable"
        out["reason"] = "canonical bytes are withheld in the public record, so independent recomputation is not possible from the record alone"
        out["output_hash_served"] = output_hash or None
        return out
    import base64
    try:
        canonical = base64.b64decode(canonical_b64)
    except Exception as exc:  # served bytes not decodable as base64
        out["status"] = "not_computable"
        out["reason"] = f"canonical_bytes did not base64-decode: {exc}"
        return out
    computed = hashlib.sha256(canonical).hexdigest()
    out["computed_sha256_of_decoded_canonical_bytes"] = computed
    out["output_hash_served"] = output_hash or None
    out["status"] = "matched" if computed == output_hash else "mismatched"
    return out


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


class Adapter(SystemAdapter):
    """The Zambo production adapter. See the module docstring for the
    config keys. Behavior is the original harness behavior, moved
    behind the adapter contract unchanged."""

    name = "zambo"

    def __init__(self, config):
        super().__init__(config)
        self.endpoint = self.config["endpoint"]
        self.tool_name = self.config["tool"]
        self.client = McpClient(self.endpoint)
        self.public = PublicRecord(self.config.get("public_base", self.endpoint))

    # -- adapter contract -------------------------------------------
    def initialize(self):
        evidence = self.client.initialize()
        summary = {"http_status": evidence["transport"]["http_status"],
                   "caller_handle_issued": bool(self.client.caller_handle)}
        return evidence, summary

    def execute(self, *, session_id, operation_key, mismatched=False,
                drop_response=False):
        template = dict(self.config["args_template"])
        if mismatched:
            field = self.config["mismatch"]["field"]
            template[field] = self.config["mismatch"]["altered_value"]
        args = substitute(template, {"K": operation_key, "SESSION": session_id})
        call = self.client.call_tool(self.tool_name, args,
                                     drop_response=drop_response)
        return {"arguments_sent": args, "call": call}

    def count_effects(self, *, session_id, operation_key, label):
        """Enumerate the receipt-backed record for a session and count
        target-tool executions.

        Method (../../../fixtures/README.md): workflow_close returns a
        fixed snapshot of every persisted receipt from the job (its
        children, each with the receipt id and its output hash); the
        snapshot excludes the workflow_close receipt itself. Every
        child id is then attributed by reading its public JSON record
        at /api/v2/receipt/<id>/verify, which names the tool and the
        step status. The external effect count for the operation is
        the number of distinct children whose public record shows the
        target tool with a success step. Enumeration receipts from
        earlier snapshots appear as children in later snapshots and
        are filtered out by that same attribution, never by hand."""
        evidence = {"label": label, "session_id": session_id, "at": utcnow(),
                    "method": "workflow_close snapshot children, each attributed "
                              "through its public /api/v2/receipt/<id>/verify record"}
        spec = {"name": "workflow_close", "arguments": {"_session_id": "{SESSION}"}}
        args = substitute(spec["arguments"], {"SESSION": session_id, "K": session_id})
        call = self.client.call_tool(spec["name"], args)
        files = {f"enum_{label}_workflow_close.json": call}
        evidence["snapshot_response_class"] = call.get("response_class")
        children = []
        body = call.get("body") or {}
        result = (body.get("result") or {}).get("structuredContent") or {}
        snapshot = result.get("result") or {}
        for child in snapshot.get("children", []) or []:
            if isinstance(child, dict) and child.get("id"):
                children.append({"receipt_id": child["id"],
                                 "output_hash_in_snapshot": child.get("output_hash")})
        evidence["snapshot_count_field"] = snapshot.get("count")
        evidence["snapshot_children"] = children
        attributed = []
        execution_ids = []
        for child in children:
            rid = child["receipt_id"]
            record = self.public.fetch_receipt(rid)
            receipt = (record.get("record_json") or {}).get("receipt") or {}
            tools = receipt.get("tools") or ([receipt["tool"]] if receipt.get("tool") else [])
            steps = receipt.get("steps") or []
            step_status = steps[0].get("status") if steps else None
            is_execution = (record["http_status"] == 200
                            and self.tool_name in tools
                            and step_status == "success")
            attributed.append({"receipt_id": rid, "tools": tools,
                               "step_status": step_status,
                               "resolves_in_public_record": record["http_status"] == 200,
                               "output_hash": receipt.get("output_hash"),
                               "counted_as_target_execution": is_execution})
            if is_execution:
                execution_ids.append(rid)
        evidence["attributed_children"] = attributed
        evidence["target_tool_execution_receipt_ids"] = execution_ids
        evidence["execution_record_ids"] = execution_ids
        evidence["external_effect_count"] = len(execution_ids)
        return {"evidence": evidence, "files": files}

    def fetch_record(self, record_id):
        return self.public.fetch_receipt(record_id)

    def recover_by_key(self, *, operation_key):
        """K-only recovery: the direct public-record lookup by K, then
        each configured K-keyed lookup tool. The recovery caller holds
        only K: no run id, response, result, or digest from attempt 1."""
        attempts = []
        files = {}
        rec = self.public.fetch_receipt(operation_key)
        files["a3_konly_run_lookup.json"] = rec
        attempts.append({"path": "GET /api/v2/receipt/<K>/verify and GET /run/<K>",
                         "http_status": rec["http_status"],
                         "page_http_status": rec["page_http_status"],
                         "page_title_not_found": rec["page_title_not_found"],
                         "response_class": "found" if rec["http_status"] == 200 else "not_found"})
        for spec in self.config.get("konly_lookup_tools", []):
            args = substitute(spec.get("arguments", {}),
                              {"K": operation_key, "SESSION": operation_key})
            call = self.client.call_tool(spec["name"], args)
            files[f"a3_konly_{spec['name']}.json"] = call
            attempts.append({"path": f"tools/call {spec['name']} with K as the only identifier",
                             "response_class": call.get("response_class"),
                             "receipt_ids_returned": call.get("receipt_ids", [])})
        return {"attempts": attempts, "files": files}
