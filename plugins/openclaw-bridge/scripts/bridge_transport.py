"""Bounded Gateway RPC through an existing local CLI or SSH connection."""
import json
import shlex
import subprocess

METHODS = ("health", "agent", "agent.wait", "chat.history")

REMOTE = r'''
import json, subprocess, sys
p = json.load(sys.stdin)
if p.get("method") not in ("health", "agent", "agent.wait", "chat.history"):
    raise SystemExit(2)
try:
    r = subprocess.run([p["openclaw_bin"], "gateway", "call", p["method"],
        "--json", "--params", json.dumps(p["params"], ensure_ascii=False),
        "--timeout", str(p["timeout_ms"])], capture_output=True, text=True,
        timeout=p["timeout_ms"] / 1000 + 2)
except (OSError, subprocess.TimeoutExpired):
    print(json.dumps({"bridge_error": "Gateway command unavailable or interrupted"}))
    raise SystemExit(0)
if r.returncode:
    print(json.dumps({"bridge_error": "Gateway call failed"}))
else:
    sys.stdout.write(r.stdout)
'''


def parse_response(output):
    decoder = json.JSONDecoder()
    for i, character in enumerate(output):
        if character != "{":
            continue
        try:
            result, end = decoder.raw_decode(output, i)
        except ValueError:
            continue
        if not output[end:].strip() and isinstance(result, dict) and not result.get("bridge_error"):
            return result
    raise RuntimeError("Gateway returned no usable response. Keep the request ID; do not resend.")


def call(config, method, params):
    if method not in METHODS:
        raise ValueError("Unsupported Gateway method")
    timeout_ms = 35000 if method == "agent.wait" else 8000
    input_text = None
    if config.transport == "local":
        command = [config.openclaw_bin, "gateway", "call", method, "--json",
                   "--params", json.dumps(params, ensure_ascii=False), "--timeout", str(timeout_ms)]
    else:
        remote = [config.remote_python, "-c", REMOTE]
        if config.run_as_user:
            remote = ["sudo", "-n", "-H", "-u", config.run_as_user] + remote
        command = ["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                   "-o", "StrictHostKeyChecking=yes", "-o", "ServerAliveInterval=10",
                   "-o", "ServerAliveCountMax=2", config.ssh_host, shlex.join(remote)]
        input_text = json.dumps({"method": method, "params": params,
                                 "openclaw_bin": config.openclaw_bin, "timeout_ms": timeout_ms}, ensure_ascii=False)
    try:
        response = subprocess.run(command, input=input_text, capture_output=True,
                                  text=True, timeout=timeout_ms / 1000 + 7)
    except (OSError, subprocess.TimeoutExpired):
        raise RuntimeError("CLI/SSH connection unavailable or interrupted. Keep the request ID; do not resend.") from None
    if response.returncode:
        raise RuntimeError("Existing CLI/SSH access failed. Raw diagnostics are withheld; no automatic resend.")
    return parse_response(response.stdout)
