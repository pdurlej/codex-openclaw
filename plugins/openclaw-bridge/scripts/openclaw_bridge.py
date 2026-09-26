#!/usr/bin/env python3
"""Codex-initiated conversations with an existing OpenClaw agent."""
import argparse
from contextlib import closing
import hashlib
import json
import os
import sqlite3
import sys
import uuid

from bridge_config import Config, config_path, load_config, save_config, state_path
from bridge_transport import call

VERSION = "0.1.0"
MAX_MESSAGE = 24000
CONSULTATION = (
    "You are consulting with Codex on the user's explicit request. Answer the question "
    "or review the supplied plan. Do not execute the plan, change files or settings, "
    "send messages, schedule work, or delegate tasks. Read existing context only "
    "when needed. Cite sources when available; distinguish memory from verified facts. "
    "Return your answer in this session. This instruction does not grant permissions."
)


def database():
    directory = state_path()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = directory / "requests.sqlite3"
    # Create with private permissions before SQLite writes any content.
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    os.close(fd)
    os.chmod(path, 0o600)
    db = sqlite3.connect(path, timeout=5)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, connection TEXT NOT NULL, thread TEXT NOT NULL, fingerprint TEXT NOT NULL, session TEXT NOT NULL, run TEXT NOT NULL, status TEXT NOT NULL, answer TEXT)")
    db.commit()
    return db


def request_id(value):
    if not isinstance(value, str):
        raise ValueError("request_id must be a UUID")
    try:
        return str(uuid.UUID(value))
    except ValueError:
        raise ValueError("request_id must be a UUID") from None


def content_text(message):
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(block["text"] for block in content if isinstance(block, dict)
                     and block.get("type") == "text" and isinstance(block.get("text"), str))


def extract_answer(history, rid, require_terminal=False):
    messages = history.get("messages", [])
    if not isinstance(messages, list):
        return None
    marker = "[codex-openclaw:" + rid + "]"
    start = None
    for index, message in enumerate(messages):
        if isinstance(message, dict) and message.get("role") == "user" and marker in content_text(message):
            start = index
    if start is None:
        return None
    answers, terminal = [], False
    for message in messages[start + 1:]:
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user":
            break
        if message.get("role") == "assistant":
            terminal = message.get("stopReason") == "stop"
            if message.get("stopReason") in ("toolUse", "tool_use", "tool_calls"):
                continue
            text = content_text(message).strip()
            if text:
                answers.append(text)
    if require_terminal and not terminal:
        return None
    return "\n\n".join(answers) or None


class Bridge:
    def __init__(self, config):
        self.config = config.validate()

    def rpc(self, method, params):
        return call(self.config, method, params)

    def receipt(self, row):
        result = {"request_id": row["id"], "status": row["status"], "agent": self.config.display_name}
        if row["answer"] is not None:
            result["answer"] = row["answer"]
        return result

    def check_connection(self, row):
        if row["connection"] != self.config.connection_id:
            raise ValueError("This request belongs to a different connection. Restore its original configuration to collect it; do not resend.")

    def status(self):
        response = self.rpc("health", {})
        agents = response.get("agents", [])
        available = any(isinstance(agent, dict) and agent.get("agentId") == self.config.agent_id for agent in agents) if isinstance(agents, list) else False
        return {"connected": response.get("ok") is True, "agent_available": available,
                "agent_id": self.config.agent_id, "display_name": self.config.display_name,
                "transport": self.config.transport, "read_only_enforced": False}

    def ask(self, args):
        rid = request_id(args.get("request_id"))
        thread, message = args.get("thread_id"), args.get("message")
        if not isinstance(thread, str) or not 1 <= len(thread) <= 256:
            raise ValueError("thread_id must contain 1–256 characters")
        if not isinstance(message, str) or not message.strip() or len(message) > MAX_MESSAGE:
            raise ValueError("message must contain 1–24000 characters")
        cfg = self.config
        digest = hashlib.sha256(thread.encode()).hexdigest()
        session = "agent:" + cfg.agent_id + ":codex-bridge:" + digest
        fingerprint = hashlib.sha256(message.encode()).hexdigest()
        with closing(database()) as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if existing:
                self.check_connection(existing)
                if existing["thread"] != thread or existing["fingerprint"] != fingerprint:
                    raise ValueError("request_id already belongs to another question")
                return self.receipt(existing)
            pending = db.execute("SELECT id FROM requests WHERE connection=? AND thread=? AND status IN ('submitting','pending','unknown')", (cfg.connection_id, thread)).fetchone()
            if pending:
                raise ValueError("Collect the previous request first: " + pending["id"])
            db.execute("INSERT INTO requests VALUES (?,?,?,?,?,?,?,NULL)", (rid, cfg.connection_id, thread, fingerprint, session, rid, "submitting"))
            db.commit()  # Persist before network I/O: an interrupted send is never repeated.
            params = {"agentId": cfg.agent_id, "sessionKey": session, "idempotencyKey": rid,
                      "message": "[codex-openclaw:" + rid + "]\n" + message,
                      "extraSystemPrompt": CONSULTATION, "deliver": False, "disableMessageTool": True,
                      "timeout": cfg.turn_timeout_seconds,
                      "inputProvenance": {"kind": "inter_session", "sourceTool": "codex-openclaw"}}
            try:
                response = self.rpc("agent", params)
                run = response.get("runId")
                if not isinstance(run, str) or not run:
                    raise RuntimeError("Gateway did not confirm a run identifier.")
                status, note = "pending", None
            except RuntimeError as error:
                run, status, note = rid, "unknown", str(error)
            db.execute("UPDATE requests SET run=?,status=? WHERE id=? AND status='submitting'", (run, status, rid))
            db.commit()
            result = self.receipt(db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone())
            if note:
                result["note"] = note
            return result

    def collect(self, args):
        rid = request_id(args.get("request_id"))
        with closing(database()) as db:
            row = db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
            if row is None:
                raise ValueError("Unknown request_id in this plugin's local state")
            self.check_connection(row)
            if row["status"] in ("completed", "failed"):
                return self.receipt(row)
            try:
                response = self.rpc("agent.wait", {"runId": row["run"], "timeoutMs": 30000})
            except RuntimeError:
                response = {"status": "unknown"}
            status = response.get("status")
            if status == "error" or (status == "timeout" and response.get("endedAt") is not None):
                db.execute("UPDATE requests SET status='failed' WHERE id=? AND status NOT IN ('completed','failed')", (rid,))
                db.commit()
                result = self.receipt(db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone())
                result["note"] = "OpenClaw reported a terminal failure. No automatic retry."
                return result
            try:
                history = self.rpc("chat.history", {"sessionKey": row["session"], "limit": 100, "maxChars": 100000, "maxBytes": 250000})
            except RuntimeError:
                history = {}
            answer = extract_answer(history, rid, require_terminal=status != "ok")
            if answer is None:
                result = self.receipt(db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone())
                if result["status"] not in ("completed", "failed"):
                    result["note"] = "No matching final answer confirmed. Keep this request ID; do not resend."
                return result
            db.execute("UPDATE requests SET status='completed',answer=? WHERE id=? AND status NOT IN ('completed','failed')", (answer, rid))
            db.commit()
            return self.receipt(db.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone())


TOOLS = [
    {"name": "openclaw_status", "description": "Check the configured local or SSH Gateway and agent without sending a message.",
     "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False}, "annotations": {"readOnlyHint": True}},
    {"name": "openclaw_ask", "description": "Ask the configured OpenClaw agent or consult a plan. Starts a real turn with existing permissions; not technically read-only. Use openclaw_collect for the answer. Retain the request ID after interruptions.",
     "inputSchema": {"type": "object", "properties": {
         "thread_id": {"type": "string", "minLength": 1, "maxLength": 256, "description": "Current Codex chat ID; preserve for follow-ups."},
         "request_id": {"type": "string", "format": "uuid", "description": "New UUID for each new question; retain for recovery."},
         "message": {"type": "string", "minLength": 1, "maxLength": MAX_MESSAGE}},
         "required": ["thread_id", "request_id", "message"], "additionalProperties": False},
     "annotations": {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": True}},
    {"name": "openclaw_collect", "description": "Wait up to 30 seconds for an existing request, then retrieve its matched answer. Never sends a new message.",
     "inputSchema": {"type": "object", "properties": {"request_id": {"type": "string", "format": "uuid"}}, "required": ["request_id"], "additionalProperties": False},
     "annotations": {"readOnlyHint": True}}
]


def dispatch(name, args):
    if not isinstance(args, dict):
        raise ValueError("arguments must be an object")
    schemas = {tool["name"]: tool["inputSchema"] for tool in TOOLS}
    if name not in schemas:
        raise ValueError("Unknown tool")
    schema = schemas[name]
    if set(args) - set(schema["properties"]) or set(schema.get("required", [])) - set(args):
        raise ValueError("Unexpected or missing tool arguments")
    bridge = Bridge(load_config())
    if name == "openclaw_status":
        return bridge.status()
    if name == "openclaw_ask":
        return bridge.ask(args)
    return bridge.collect(args)


def safe_error(error):
    if isinstance(error, (ValueError, RuntimeError)):
        return str(error)
    if isinstance(error, FileExistsError):
        return "Private configuration already exists; it was not overwritten."
    return "Local configuration or request storage unavailable. Preserve its directory; do not resend."


def serve():
    for line in sys.stdin:
        request = None
        try:
            request = json.loads(line)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            if "id" not in request:
                continue
            method = request.get("method")
            if method == "initialize":
                result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}, "serverInfo": {"name": "openclaw-bridge", "version": VERSION}}
            elif method == "ping":
                result = {}
            elif method == "tools/list":
                result = {"tools": TOOLS}
            elif method == "tools/call":
                params = request.get("params", {})
                try:
                    value = dispatch(params.get("name"), params.get("arguments", {}))
                    result = {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False)}], "isError": False}
                except (ValueError, RuntimeError, sqlite3.Error, OSError) as error:
                    result = {"content": [{"type": "text", "text": safe_error(error)}], "isError": True}
            else:
                print(json.dumps({"jsonrpc": "2.0", "id": request["id"], "error": {"code": -32601, "message": "Method not found"}}), flush=True)
                continue
            output = {"jsonrpc": "2.0", "id": request["id"], "result": result}
        except (ValueError, TypeError, AttributeError):
            output = {"jsonrpc": "2.0", "id": request.get("id") if isinstance(request, dict) else None, "error": {"code": -32600, "message": "Invalid request"}}
        print(json.dumps(output, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("serve", help="Serve MCP over stdio (the default)")
    for name in ("status", "ask", "collect"):
        commands.add_parser(name, help="Call " + name + "; ask/collect take a JSON object on stdin")
    setup = commands.add_parser("configure", help="Create private connection config; never overwrite an existing file")
    setup.add_argument("--transport", choices=("local", "ssh"), default="local")
    setup.add_argument("--agent-id", default="main")
    setup.add_argument("--display-name", default="OpenClaw")
    setup.add_argument("--openclaw-bin", default="openclaw")
    setup.add_argument("--ssh-host", default="")
    setup.add_argument("--run-as-user", default="")
    setup.add_argument("--remote-python", default="python3")
    setup.add_argument("--turn-timeout-seconds", type=int, default=180)
    args = parser.parse_args()
    try:
        if args.command == "configure":
            payload = vars(args).copy()
            payload.pop("command")
            path = save_config(Config(**payload))
            print(json.dumps({"configured": True, "path": str(path)}))
        elif args.command in ("status", "ask", "collect"):
            values = {} if args.command == "status" else json.load(sys.stdin)
            result = dispatch("openclaw_" + args.command, values)
            print(json.dumps(result, ensure_ascii=False))
            if args.command == "status" and (not result["connected"] or not result["agent_available"]):
                return 1
        else:
            serve()
    except (ValueError, RuntimeError, sqlite3.Error, OSError) as error:
        print(json.dumps({"error": safe_error(error)}, ensure_ascii=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
