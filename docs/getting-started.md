[Home](../README.md) · [Documentation](README.md)

# Install in Codex

Already running OpenClaw? Your first conversation takes four steps.
This guide connects an existing Gateway; it does not install or provision OpenClaw.

Requirements: local Codex with plugin support, Python 3.10+, and an already
working OpenClaw Gateway. For SSH, both hosts need Python 3; the Codex host also
needs OpenSSH and a verified, non-interactive connection to the remote account.

## 1. Get the plugin

```sh
git clone https://github.com/pdurlej/codex-openclaw.git
cd codex-openclaw
```

## 2. Connect your agent

Choose **one** connection setup. Replace `main` if your agent uses another ID.
For SSH, replace `my-openclaw` with your existing host alias.

If OpenClaw runs as your current local user:

```sh
python3 bridge.py configure --transport local --agent-id main
```

If it runs on another host, use an existing SSH alias:

```sh
python3 bridge.py configure --transport ssh --ssh-host my-openclaw \
  --agent-id main --display-name "My assistant"
```

Configuration stays outside the repository. If you have already configured the
bridge, keep that configuration; `configure` will refuse to overwrite it.
For service accounts or a missing CLI executable, see [advanced connection options](#advanced-connection-options).

## 3. Check and install

```sh
python3 bridge.py status
```

Continue when the result includes `connected: true` and `agent_available: true`.
If either check fails, resolve the connection first using the [configuration reference](reference.md#configuration).

```sh
codex plugin marketplace add .
codex plugin add openclaw-bridge@codex-openclaw
```

## 4. Ask your first question

Open a **new local Codex chat**, select **OpenClaw Bridge**, and ask:

> Ask my OpenClaw agent to introduce itself in one sentence.

Expected: an answer attributed to your configured OpenClaw agent, in Codex.
Then try a follow-up:

> Ask it to expand on its last answer.

The reply should continue the same bridge conversation. Codex sends your question
and selected context; it does not automatically synchronize your full chat.

---

## Advanced connection options

When the SSH account already has permission to run commands as the OpenClaw
service user, add `--run-as-user openclaw`. This uses `sudo -n -H -u`; it does
not create that permission. Use `--openclaw-bin /absolute/path/to/openclaw` if
the CLI is absent from the remote non-interactive PATH. Remote Python can be
selected with `--remote-python /absolute/path/to/python3`.

## Alternative: track the GitHub marketplace

To install from the public GitHub marketplace after configuration:

```sh
codex plugin marketplace add https://github.com/pdurlej/codex-openclaw.git
codex plugin add openclaw-bridge@codex-openclaw
```

Use either this Git-backed catalog or the local checkout catalog above.
The public [plugin package](../plugins/openclaw-bridge/) is distributed through
this repository; it does not currently have a separate public Codex Directory listing.
See [OpenAI’s marketplace documentation](https://developers.openai.com/plugins/build/plugins#add-a-marketplace-from-the-cli) for the supported distribution mechanism.
The plugin package includes portable Agent Plugins 1.0 manifests and a Codex
compatibility manifest; both describe the same version and tools.


Next: [try a workflow](workflows.md) or [adjust the configuration](reference.md#configuration).
