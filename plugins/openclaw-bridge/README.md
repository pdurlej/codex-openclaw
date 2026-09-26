# Codex ↔ OpenClaw

**Bring your coding agent and your personal OpenClaw agent into the same feedback loop.**

OpenClaw Bridge lets Codex ask your OpenClaw agent questions, collect its answers,
and follow up in the same conversation. Use it to investigate unexpected behavior,
shape new personalizations, and get feedback from the agent that will live with
your changes — without manually relaying every question and answer between apps.

Codex works with your code and tests. Your OpenClaw agent contributes the context,
preferences, and perspective available to it. You decide which changes to accept.
The bridge connects those roles through your existing local CLI or SSH connection.
It is configurable for your own agent; personal connection settings stay local.

## What can you do with it?

### Debug OpenClaw with Codex

When your agent behaves differently from what you intended, let Codex compare the
implementation with the agent's account of the behavior. Ask focused questions,
form a hypothesis, make an authorized change, and bring the result back into the
same conversation for feedback.

> My OpenClaw agent keeps producing long answers despite my preference for short
> ones. Inspect the relevant instructions in this project, ask my agent how it
> interprets them, and propose the smallest fix. After the change, run the local
> checks and ask it to respond to the same example again.

**Useful result:** a concrete before/after example, the code or instruction change
behind it, and test evidence. The agent's explanation is a clue to investigate,
not proof of which instructions or runtime path caused the behavior.

### Build and refine personalizations

Use the agent as a feedback partner while Codex develops prompts, skills, response
styles, or workflows. Discuss acceptance examples before implementation, then ask
for feedback on the changed instructions and representative outputs.

> Help me build a concise daily-planning personalization. Ask my OpenClaw agent
> which preferences it already has available, agree on three example requests and
> expected responses, then implement the change in this project. Show the test
> results and ask the agent what still feels unclear or inconsistent.

**Useful result:** explicit examples of what “works for me” means, a tested change,
and a focused list of remaining gaps. A bridge conversation uses a dedicated
session; checking a real channel, scheduled workflow, or deployed installation
still requires exercising that actual path.

### Collaborate on tests and acceptance

Pair a coding agent with an OpenClaw agent that helps personalize your assistant.
Codex can explain a proposed change, ask for edge cases, and return with results.
The OpenClaw agent can challenge assumptions or review examples against the user
context available to it.

> Consult this proposed personalization with my OpenClaw agent. Ask for missing
> acceptance cases and ambiguous behavior. Implement the agreed scope, run the
> relevant tests, then send a concise summary and sample outputs back for review.
> Separate observed test results from the agent's opinions and open questions.

**Useful result:** technical checks plus contextual feedback, together in your
Codex chat. Feedback supports your acceptance decision; an agent saying “looks
right” does not establish that a deployment or user flow passed.

## The feedback loop

1. **Ask:** Codex sends a focused question and the relevant context you authorize.
2. **Collect:** the bridge retrieves the matching answer, attributed to your agent.
3. **Act and check:** Codex uses the feedback in its normal coding and testing work.
4. **Follow up:** continue in the same bridge conversation with results or questions.

This can make iterations easier and potentially cheaper by reducing manual
handoffs and repeated context setup. Cost savings are **not benchmarked or
guaranteed**: both agents still use their configured models, and each new
OpenClaw question can incur the usual provider costs. Start with a small example
and ask targeted follow-ups.

**v1 scope: conversations start in Codex.** The bridge requests consultation from
OpenClaw; it does not provide autonomous OpenClaw-to-Codex messages, wake-ups, or
delegated implementation jobs. Changes and execution remain subject to each
agent's existing permissions. See [Permissions and privacy](#permissions-and-privacy).

```text
Your Codex chat → question + relevant context → your OpenClaw agent
Your Codex chat ← attributed answer + feedback ← same bridge session
       ↓
  inspect / edit / test → follow-up with results
```

The adapter uses the Python standard library and your existing OpenClaw Gateway.
It needs no remote daemon, public endpoint, token broker, package installation on
the OpenClaw host, or hosted Plugin Creator service. Released under the
[MIT license](LICENSE).

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
