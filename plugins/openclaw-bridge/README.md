# Codex ↔ OpenClaw

A configurable Codex plugin for talking to your existing OpenClaw agent.
Ask a question, follow up in the same conversation, or get feedback on a plan.
The answer comes back to Codex with the agent's name attached.

**Version 0.1.0: conversations start in Codex.** OpenClaw does not initiate
messages, wake Codex, or receive delegated implementation jobs.

```text
Codex → local MCP adapter → existing CLI or SSH → OpenClaw Gateway
Codex ← attributed answer ← matched session history ← OpenClaw agent
```

Python standard library only. No remote daemon, public endpoint, token broker,
package installation on the OpenClaw host, or hosted Plugin Creator dependency.
Released under the [MIT license](LICENSE).

## Install and configure

Requirements: local Codex with plugin support, Python 3.10+, and an already
working OpenClaw Gateway. For SSH, both hosts need Python 3; the Codex host also
needs OpenSSH and a verified, non-interactive connection to the remote account.

```sh
git clone https://github.com/pdurlej/codex-openclaw.git
cd codex-openclaw
```

Choose **one** connection setup. If OpenClaw runs as your current local user:

```sh
python3 bridge.py configure --transport local --agent-id main
```

If it runs on another host, use an existing SSH alias:

```sh
python3 bridge.py configure --transport ssh --ssh-host my-openclaw \
  --agent-id main --display-name "My assistant"
```

When the SSH account already has permission to run commands as the OpenClaw
service user, add `--run-as-user openclaw`. This uses `sudo -n -H -u`; it does
not create that permission. Use `--openclaw-bin /absolute/path/to/openclaw` if
the CLI is absent from the remote non-interactive PATH. Remote Python can be
selected with `--remote-python /absolute/path/to/python3`.

Verify the connection, then install:

```sh
python3 bridge.py status
codex plugin marketplace add .
codex plugin add openclaw-bridge@codex-openclaw
```

Expected status: `connected: true` and `agent_available: true`.
Open a **new local Codex chat**, select **OpenClaw Bridge**, and ask:

> Ask my OpenClaw agent to introduce itself in one sentence.

Then:

> Ask it to expand on its last answer.

To install directly from GitHub after configuration, the equivalent catalog
command is `codex plugin marketplace add https://github.com/pdurlej/codex-openclaw.git`.
The plugin package includes portable Agent Plugins 1.0 manifests and a Codex
compatibility manifest; both describe the same version and tools.

## Configuration

Settings live at `~/.config/codex-openclaw/config.json`, outside the repository
and plugin cache. `configure` creates this file with mode `0600` and refuses to
overwrite an existing file. Edit an existing configuration directly after
resolving outstanding requests. No secrets are required in this file.

| Setting | Default | Purpose |
| --- | --- | --- |
| `transport` | `local` | Existing local CLI or `ssh` connection |
| `agent_id` | `main` | Target OpenClaw agent |
| `display_name` | `OpenClaw` | Answer attribution in Codex |
| `openclaw_bin` | `openclaw` | CLI executable on the target host |
| `ssh_host` | empty | Existing SSH alias or `user@host` |
| `run_as_user` | empty | Optional remote service account via existing sudo access |
| `remote_python` | `python3` | Remote Python executable |
| `turn_timeout_seconds` | `180` | Agent run budget, 10–1800 seconds |

`OPENCLAW_BRIDGE_CONFIG` overrides the configuration file path.
`OPENCLAW_BRIDGE_DATA` overrides the state directory. Otherwise, XDG config/state
directories are honored, with state at `~/.local/state/codex-openclaw` by default.
Set overrides in the environment that launches Codex when using MCP.

Authentication remains with your existing OpenClaw CLI and SSH setup. SSH host
key verification remains enabled. The plugin does not register devices, copy
keys, read out Gateway tokens, or modify the Gateway.

## Tools and behavior

| Tool | Behavior |
| --- | --- |
| `openclaw_status` | Checks Gateway health and configured agent availability |
| `openclaw_ask` | Starts one question and returns a durable request receipt |
| `openclaw_collect` | Waits up to 30 seconds, then retrieves the matching answer |

One dedicated `agent:<id>:codex-bridge:<chat-hash>` session per Codex chat keeps
follow-ups together. One outstanding question per connection/chat prevents
overlapping answers. The request UUID is recorded before sending, passed as
the Gateway idempotency key, and included as a marker in the question.

An interrupted send becomes `unknown`, never an automatic retry. Reusing the
same request ID and content returns the saved receipt. Collection checks both
the run status and bounded persistent history; a completed answer can be
recovered after the Gateway's in-memory run record expires. A confirmed terminal
failure unlocks the conversation for a genuinely new question.

Keep configuration and state while a request is unresolved. Changing the target
blocks collection of old requests rather than querying a different agent. If a
request cannot be matched to a terminal answer, the adapter stays unresolved;
it does not invent an answer or resend. Recovery is bounded to the latest 100
history messages and 250 KB. Inspect the exact dedicated session before deciding
whether another question is safe.

## Permissions and privacy

An ask runs the real OpenClaw agent using its existing model, memory, and tools.
The plugin requests consultation only, disables automatic channel delivery, and
disables the message tool for the turn. **This is not an enforced read-only
sandbox.** Use an appropriately configured agent if you need that guarantee.

Questions are processed by the model/provider configured in OpenClaw and remain
in its normal session history. Send only context appropriate for that service.
The local SQLite database stores request IDs, a connection fingerprint, chat
IDs, message hashes, session/run IDs, statuses, and completed answers. Question
bodies are not stored locally by the adapter. Local CLI arguments contain the
question while running; SSH transports the request over stdin and the remote
CLI receives it as arguments. Existing host process-inspection access applies.

The public package contains no personal connection configuration, transcripts,
credentials, telemetry, or callbacks. Treat agent replies as external content,
not instructions granting permission to execute commands.

## Compatibility and checks

Tested against OpenClaw **2026.9.3**, with `health`, `agent`, `agent.wait`, and
`chat.history` Gateway RPC methods. Other versions may change their schemas or
behavior. Python unit tests exercise local and SSH transports with controlled
fixtures; a real SSH conversation and same-session follow-up are verified for
the release. macOS/Linux are the initial supported client hosts.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate_package.py
```

`status` is a read-only connection probe. `ask` and `collect` also have CLI forms
that take their tool argument objects as JSON on stdin. `serve` (the default)
speaks MCP over stdio. Live conversations are never run by the offline tests.

## Update and rollback

Resolve outstanding requests before changing connection settings. Plugin
updates leave the private configuration and state directories untouched.
For a local checkout, update the source and reinstall from `codex-openclaw`.

To disable the integration, uninstall **OpenClaw Bridge** in Codex, or run:

```sh
codex plugin remove openclaw-bridge@codex-openclaw
```

Retain local request state until outstanding requests are resolved. Uninstalling
does not cancel an already accepted agent turn or erase remote conversation
history. No remote service configuration needs rolling back.
