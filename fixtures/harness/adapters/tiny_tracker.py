"""tiny-tracker adapter for the lost-response harness.

System under test: tiny-tracker, a small open-source teaching MCP
server (npm @mcp-write-safety/tiny-tracker, source in
isokron-ai/mcp-write-safety under examples/tiny-tracker). It is an
issue tracker: an MCP server (Streamable HTTP, /mcp) in front of a
REST backend that keeps tickets in memory. Its default build is meant
to be correct; its broken builds switch on one named defect each.
The builds this adapter was written for:

  correct build                     create_ticket forwards
                                    idempotency_key to the backend,
                                    which applies a keyed POST once,
                                    answers a repeat as a replay
                                    (structuredContent.replayed: true)
                                    and refuses the same key with a
                                    different request (422,
                                    idempotency_key_reused).
  --defect idempotency-key-dropped  create_ticket accepts the key but
                                    never sends it to the backend.
  --defect idempotency-key-ignores-args
                                    create_ticket answers any call
                                    with a seen key from a cache keyed
                                    by the key alone.

Target tool: create_ticket, with K as its idempotency_key. Every
execution creates exactly one ticket in the backend, so every
execution is countable. The arguments A are a title that starts with
K (so the counter can find every ticket the operation created, also
one created by a mismatched retry), a description naming the
run-scoped session identity (attribution to the run), and a priority.
A2 changes exactly one parameter value: priority.

The shared external effect counter (../../README.md): the backend's
REST record, read directly over HTTP, never through the MCP server.
GET <backend_url>/tickets?title_prefix=<K> lists the tickets; each
listed ticket whose title starts with K and whose description names
the session identity is one committed execution of the operation.
The count is reported with the ticket ids it was counted from and the
raw listing as served. Limits, stated plainly: the backend is local
to the machine running the harness (127.0.0.1) and needs the bearer
token the operator started it with, so a third party recounts from
the published raw listing, not from a live public record; and the
backend keeps everything in memory, so its record lasts only as long
as the process.

Digests: tiny-tracker issues no signed receipts and carries no
committed result digest on a ticket or in a tool result. A ticket
carries an integer version, which the backend also serves as the
ETag ("1", "2", ...); that is a version validator, not a digest of
the result, and it is reported as such under "validators", never
under "digests". fetch_record() therefore returns digests {} and a
recomputation status of "not_computable"; it also records an
informational SHA-256 of the served body, labelled as the harness's
own hash and not a committed digest. The driver scores what that
evidence supports.

Fault point: client-side discard, as the contract allows. The
attempt is sent, the full response is read off the wire (so the
server has finished the call and the ticket is committed), and the
body is then discarded: only transport metadata is kept. tiny-tracker
has no fault hook between the MCP server and the client. (Its own
test suite has a loopback gate between the MCP server and the
backend that cuts the backend's answer; that is a different fault,
where the MCP server itself loses the answer, and it is not used
here.)

K-only recovery paths tried by recover_by_key(), in order:
  1. tools/call list_tickets {title_prefix: K}: a read through the
     MCP server. It finds the record only because the caller chose to
     put K in the title; it is the caller's convention, not a K index
     in tiny-tracker, and the attempt says so.
  2. tools/call create_ticket with the same K and the same arguments
     the caller sent in attempt 1: the replay path. The arguments are
     the caller's own (kept by the adapter from its own execute()
     calls), not anything from the dropped response. The counter is
     read before and after, so a replay that executes again is
     visible as a new effect.
tiny-tracker has no read endpoint keyed by the idempotency key: ticket
ids are server-issued (T-<n>), and the backend's key record is
internal. fetch_record(K) answers 404 for that reason.

Adapter config keys (the config's adapter_config object):
  mcp_url            MCP endpoint, e.g. http://127.0.0.1:47310/mcp.
  backend_url        Backend REST base URL, e.g. http://127.0.0.1:47311.
  backend_token_env  Name of the environment variable that holds the
                     backend bearer token (default
                     TRACKER_BACKEND_TOKEN). The token is never
                     written to the run outputs.
  tool               The target tool (create_ticket).
  args_template      Arguments A, with {K} for the operation identity
                     and {SESSION} for the run-scoped session identity.
                     The adapter binds K as idempotency_key itself.
  mismatch           {"field", "altered_value"}: the one parameter A2
                     changes.
  protocol_version   MCP protocol version sent in initialize (default
                     2025-11-25; tiny-tracker serves it through the
                     SDK's stateless fallback).
  build              Informational: {"defects": [...],
                     "start_command": "..."}, recorded with the run.

Start the system under test (loopback only), then run the harness:

  export TRACKER_BACKEND_TOKEN=<a fresh local test token>
  npx -y -p @mcp-write-safety/tiny-tracker@0.1.0 tiny-tracker all \\
      --port 47310 --backend-port 47311 [--defect <name>]
  python3 lost_response.py --config config.tiny-tracker.json --out ../../runs/<dir>

The first stdout line of tiny-tracker is JSON with the backend and
mcp URLs; they must match the config.
"""

import hashlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import quote

import requests

from .base import SystemAdapter

ADAPTER_VERSION = "0.1.0"


def utcnow():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def parse_mcp_body(resp, jsonrpc_id):
    """Return the JSON-RPC message answering jsonrpc_id from a
    Streamable HTTP response, whether the server answered with
    application/json or with an SSE stream (text/event-stream)."""
    ctype = (resp.headers.get("Content-Type") or "").lower()
    text = resp.content.decode("utf-8", errors="replace")
    if "text/event-stream" in ctype:
        messages, data = [], []
        for line in text.splitlines() + [""]:
            if line.startswith("data:"):
                data.append(line[5:].lstrip())
            elif line == "" and data:
                try:
                    messages.append(json.loads("\n".join(data)))
                except ValueError:
                    messages.append({"_unparsed_sse_data": "\n".join(data)[:4000]})
                data = []
        for msg in messages:
            if isinstance(msg, dict) and msg.get("id") == jsonrpc_id:
                return msg
        return {"_no_matching_message": True, "_sse_messages": messages}
    if not text:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return {"_non_json_body": text[:4000]}


class McpClient:
    """Minimal MCP client over Streamable HTTP, using requests."""

    def __init__(self, endpoint, protocol_version):
        self.endpoint = endpoint
        self.protocol_version = protocol_version
        self.negotiated_version = None
        self.session_id = None
        self.http = requests.Session()

    def _headers(self):
        h = {"Content-Type": "application/json",
             "Accept": "application/json, text/event-stream"}
        if self.negotiated_version:
            h["MCP-Protocol-Version"] = self.negotiated_version
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        return h

    def post(self, payload):
        started = time.time()
        sent_at = utcnow()
        resp = self.http.post(self.endpoint, headers=self._headers(),
                              data=json.dumps(payload), timeout=60)
        raw = resp.content  # the whole response is read off the wire
        meta = {
            "sent_at": sent_at,
            "received_at": utcnow(),
            "elapsed_ms": round((time.time() - started) * 1000),
            "http_status": resp.status_code,
            "content_type": resp.headers.get("Content-Type"),
            "response_bytes": len(raw),
            "jsonrpc_id": payload.get("id"),
            "mcp_session_id_header": resp.headers.get("Mcp-Session-Id"),
        }
        return meta, resp

    def initialize(self):
        payload = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": "initialize",
                   "params": {"protocolVersion": self.protocol_version,
                              "capabilities": {},
                              "clientInfo": {"name": "lost-response-harness",
                                             "version": "1.0.0"}}}
        meta, resp = self.post(payload)
        body = parse_mcp_body(resp, payload["id"])
        self.session_id = resp.headers.get("Mcp-Session-Id")
        result = (body or {}).get("result") or {}
        self.negotiated_version = result.get("protocolVersion")
        note = {"jsonrpc": "2.0", "method": "notifications/initialized"}
        nmeta, nresp = self.post(note)
        return {"initialize": {"request": payload, "transport": meta, "body": body},
                "notifications_initialized": {"request": note, "transport": nmeta,
                                              "body_text": nresp.text[:2000]}}

    def request(self, method, params):
        payload = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method,
                   "params": params}
        meta, resp = self.post(payload)
        return payload, meta, parse_mcp_body(resp, payload["id"])

    def call_tool(self, name, arguments, drop_response=False):
        payload, meta, body = self.request("tools/call",
                                           {"name": name, "arguments": arguments})
        if drop_response:
            del body
            return {"dropped": True, "transport": meta,
                    "note": "Response read off the wire in full (the call had "
                            "finished and committed on the server), then "
                            "discarded client-side by the fault injector. No "
                            "result, ticket id, or digest from this attempt is "
                            "available to the caller."}
        structured = ((body or {}).get("result") or {}).get("structuredContent") or {}
        return {"dropped": False, "transport": meta, "body": body,
                "response_class": classify(meta, body),
                "replayed": structured.get("replayed") if isinstance(structured, dict) else None,
                "mws_outcome": (structured.get("mws") or {}).get("outcome")
                if isinstance(structured, dict) else None,
                "receipt_ids": record_ids_of(body)}


def classify(meta, body):
    """The caller-visible response class of a tools/call answer."""
    if meta["http_status"] != 200 and not body:
        return f"http_error:{meta['http_status']}"
    if not isinstance(body, dict) or body.get("_no_matching_message") or body.get("_non_json_body"):
        return "unparseable"
    if body.get("error"):
        return "jsonrpc_error:" + str((body["error"] or {}).get("code", "unknown"))
    result = body.get("result")
    if not result:
        return "empty_result"
    structured = result.get("structuredContent") or {}
    if result.get("isError"):
        code = None
        if isinstance(structured, dict):
            code = (structured.get("mws") or {}).get("code") or structured.get("error")
        return "tool_error:" + (str(code) if code else "isError")
    return "success"


def record_ids_of(body):
    """Ticket ids a create_ticket answer carries (structuredContent.id)."""
    structured = (((body or {}).get("result") or {}).get("structuredContent") or {})
    if isinstance(structured, dict) and isinstance(structured.get("id"), str):
        return [structured["id"]]
    return []


def ticket_number(ticket_id):
    try:
        return int(str(ticket_id).split("-", 1)[1])
    except (IndexError, ValueError):
        return 0


class Backend:
    """Direct reads of the tiny-tracker backend's REST record."""

    def __init__(self, base_url, token):
        self.base = base_url.rstrip("/")
        self.token = token
        self.http = requests.Session()

    def get(self, path):
        url = self.base + path
        started = time.time()
        resp = self.http.get(url, headers={"Authorization": f"Bearer {self.token}",
                                           "Accept": "application/json"}, timeout=30)
        out = {"url": url, "method": "GET", "fetched_at": utcnow(),
               "elapsed_ms": round((time.time() - started) * 1000),
               "http_status": resp.status_code,
               "content_type": resp.headers.get("Content-Type"),
               "etag": resp.headers.get("ETag"),
               "body_text": resp.text}
        try:
            out["body_json"] = resp.json()
        except ValueError:
            out["body_json"] = None
        return out, resp.content


class Adapter(SystemAdapter):
    """The tiny-tracker adapter. See the module docstring for what is
    counted, the fault point, the recovery paths, and the config
    keys."""

    name = "tiny_tracker"

    def __init__(self, config):
        super().__init__(config)
        self.endpoint = self.config["mcp_url"]
        self.tool_name = self.config.get("tool", "create_ticket")
        token_env = self.config.get("backend_token_env", "TRACKER_BACKEND_TOKEN")
        token = os.environ.get(token_env)
        if not token:
            raise RuntimeError(f"set {token_env} to the backend bearer token the "
                               "tiny-tracker build under test was started with")
        self.backend = Backend(self.config["backend_url"], token)
        self.client = McpClient(self.endpoint,
                                self.config.get("protocol_version", "2025-11-25"))
        # The caller's own request log: the arguments it sent per K.
        # Used by the K-only replay path; nothing from any response.
        self.sent_args = {}

    def _args(self, session_id, operation_key, mismatched):
        template = dict(self.config["args_template"])
        if mismatched:
            m = self.config["mismatch"]
            template[m["field"]] = m["altered_value"]
        args = substitute(template, {"K": operation_key, "SESSION": session_id})
        args["idempotency_key"] = operation_key
        return args

    # -- adapter contract -------------------------------------------
    def initialize(self):
        evidence = {"adapter": self.name, "adapter_version": ADAPTER_VERSION,
                    "mcp_url": self.endpoint, "backend_url": self.backend.base,
                    "build": self.config.get("build"),
                    "at": utcnow()}
        evidence.update(self.client.initialize())
        payload, meta, body = self.client.request("tools/list", {})
        evidence["tools_list"] = {"request": payload, "transport": meta, "body": body}
        init_body = evidence["initialize"]["body"] or {}
        result = init_body.get("result") or {}
        tools = ((body or {}).get("result") or {}).get("tools") or []
        target = next((t for t in tools if t.get("name") == self.tool_name), None)
        summary = {
            "http_status": evidence["initialize"]["transport"]["http_status"],
            "protocol_version": result.get("protocolVersion"),
            "server_info": result.get("serverInfo"),
            "mcp_session_id_issued": bool(self.client.session_id),
            "server_instructions": result.get("instructions"),
            "target_tool_listed": bool(target),
            "target_tool_annotations": (target or {}).get("annotations"),
            "target_tool_accepts_idempotency_key": "idempotency_key" in
            (((target or {}).get("inputSchema") or {}).get("properties") or {}),
            "build": self.config.get("build"),
        }
        return evidence, summary

    def execute(self, *, session_id, operation_key, mismatched=False,
                drop_response=False):
        args = self._args(session_id, operation_key, mismatched)
        if not mismatched:
            self.sent_args.setdefault(operation_key, {"arguments": dict(args),
                                                      "session_id": session_id})
        call = self.client.call_tool(self.tool_name, args, drop_response=drop_response)
        return {"arguments_sent": args, "call": call}

    def _count(self, session_id, operation_key):
        listing, _ = self.backend.get(f"/tickets?title_prefix={quote(operation_key, safe='')}")
        tickets = ((listing.get("body_json") or {}).get("tickets") or [])
        attributed, ids = [], []
        for t in sorted(tickets, key=lambda t: ticket_number(t.get("id"))):
            title_ok = str(t.get("title", "")).startswith(operation_key)
            session_ok = session_id is None or session_id in str(t.get("description", ""))
            counted = listing["http_status"] == 200 and title_ok and session_ok
            attributed.append({"ticket_id": t.get("id"), "title": t.get("title"),
                               "priority": t.get("priority"),
                               "created_at": t.get("created_at"),
                               "title_starts_with_K": title_ok,
                               "description_names_session": session_ok,
                               "counted_as_execution": counted})
            if counted:
                ids.append(t.get("id"))
        return listing, attributed, ids

    def count_effects(self, *, session_id, operation_key, label):
        listing, attributed, ids = self._count(session_id, operation_key)
        evidence = {
            "label": label, "session_id": session_id, "K": operation_key, "at": utcnow(),
            "method": "GET <backend>/tickets?title_prefix=<K> on the tiny-tracker backend "
                      "REST API, read directly (not through MCP); each listed ticket whose "
                      "title starts with K and whose description names the session identity "
                      "is one committed execution of create_ticket for the operation",
            "listing_http_status": listing["http_status"],
            "attributed_records": attributed,
            "execution_record_ids": ids,
            "external_effect_count": len(ids),
            "refusal_records": [],
            "refusal_records_note": "tiny-tracker writes no record for a refused call",
        }
        return {"evidence": evidence, "files": {f"backend_{label}_listing.json": listing}}

    def fetch_record(self, record_id):
        served, raw = self.backend.get(f"/tickets/{quote(str(record_id), safe='')}")
        ticket = (served.get("body_json") or {}).get("ticket")
        return {
            "record_id": record_id,
            "http_status": served["http_status"],
            "url": served["url"],
            "fetched_at": served["fetched_at"],
            "content_type": served["content_type"],
            "body_text": served["body_text"],
            "record_json": served["body_json"],
            "digests": {},
            "validators": {"etag": served["etag"],
                           "version": (ticket or {}).get("version")},
            "receipt_note": "tiny-tracker issues no signed receipts and its records carry "
                            "no committed result digest; the ETag is the ticket's integer "
                            "version, a validator, not a digest",
            "recomputation": {
                "status": "not_computable",
                "reason": "the record carries no committed result digest to recompute "
                          "against; tiny-tracker issues no receipts",
                "informational_sha256_of_served_body": hashlib.sha256(raw).hexdigest(),
                "informational_note": "the harness's own SHA-256 of the bytes served now; "
                                      "not a digest committed by the system at commit time",
            },
        }

    def recover_by_key(self, *, operation_key):
        attempts, files = [], {}
        # Path 1: a read through MCP, by the caller's own title convention.
        payload, meta, body = self.client.request(
            "tools/call", {"name": "list_tickets",
                           "arguments": {"title_prefix": operation_key}})
        cls = classify(meta, body)
        listed = ((((body or {}).get("result") or {}).get("structuredContent") or {})
                  .get("tickets") or [])
        listed_ids = [t.get("id") for t in listed if isinstance(t, dict)]
        if cls == "success":
            cls = ("found" if len(listed_ids) == 1 else
                   "not_found" if not listed_ids else f"found_multiple:{len(listed_ids)}")
        files["a3_konly_list_tickets.json"] = {"request": payload, "transport": meta,
                                               "body": body}
        attempts.append({
            "path": "tools/call list_tickets {title_prefix: K}",
            "response_class": cls, "record_ids_returned": listed_ids,
            "digest_returned": None,
            "depends_on_caller_convention": True,
            "note": "finds tickets only because the caller put K at the start of the "
                    "title; tiny-tracker has no lookup keyed by the idempotency key, and "
                    "the listing carries no digest"})
        # Path 2: the same-key replay with the caller's own arguments.
        sent = self.sent_args.get(operation_key)
        if sent is None:
            attempts.append({"path": "tools/call create_ticket replay with the same K and "
                                     "the same arguments",
                             "response_class": "not_attempted",
                             "note": "this caller holds no record of the arguments it sent "
                                     "for K (fresh process), so it cannot replay"})
            return {"attempts": attempts, "files": files}
        args, session_id = sent["arguments"], sent["session_id"]
        before = self._count(session_id, operation_key)
        call = self.client.call_tool(self.tool_name, dict(args))
        after = self._count(session_id, operation_key)
        rid = call.get("receipt_ids") or []
        new_effect = len(after[2]) > len(before[2])
        if call["response_class"] == "success":
            if new_effect:
                cls = "executed_again"
            elif call.get("replayed") is True:
                cls = "found"
            else:
                cls = "success_without_replay_flag"
        else:
            cls = call["response_class"]
        files["a3_konly_replay_create_ticket.json"] = {
            "arguments_sent": args, "call": call,
            "count_before": {"execution_record_ids": before[2],
                             "external_effect_count": len(before[2]),
                             "listing": before[0]},
            "count_after": {"execution_record_ids": after[2],
                            "external_effect_count": len(after[2]),
                            "listing": after[0]}}
        attempts.append({
            "path": "tools/call create_ticket with the same K and the same arguments "
                    "(the caller's own, not response-derived): the replay path",
            "response_class": cls,
            "record_ids_returned": rid,
            "replayed_flag": call.get("replayed"),
            "effect_count_before": len(before[2]),
            "effect_count_after": len(after[2]),
            "new_effect": new_effect,
            "digest_returned": None,
            "note": "a replay answer carries the ticket id and version of the keyed "
                    "write and replayed: true; it carries no digest, so digest equality "
                    "with a committed result digest cannot be shown"})
        return {"attempts": attempts, "files": files}
