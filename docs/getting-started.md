[Home](../README.md) · [Documentation](README.md)

# Install in Codex

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
