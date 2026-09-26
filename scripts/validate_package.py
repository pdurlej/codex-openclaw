#!/usr/bin/env python3
"""Offline checks for the distributable plugin and marketplace."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "openclaw-bridge"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    portable = read(PLUGIN / "plugin.json")
    legacy = read(PLUGIN / ".codex-plugin/plugin.json")
    assert portable["$schema"] == "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
    for key in ("name", "version", "description", "author", "license", "repository"):
        assert portable[key] == legacy[key], key
    assert portable["name"] == PLUGIN.name
    assert portable["license"] == "MIT"
    assert portable["extensions"]["com.openai"]["interface"] == legacy["interface"]
    mcp = read(PLUGIN / "mcp.json")
    assert mcp["$schema"] == "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
    assert mcp["mcpServers"] == read(PLUGIN / ".mcp.json")["mcpServers"]
    server = mcp["mcpServers"]["openclaw-bridge"]
    assert server["command"] == "python3" and server["type"] == "stdio"
    assert server["args"] == ["${PLUGIN_ROOT}/scripts/openclaw_bridge.py"]
    assert (PLUGIN / "scripts/openclaw_bridge.py").is_file()
    assert (PLUGIN / "README.md").is_file()
    assert (PLUGIN / "LICENSE").read_text() == (ROOT / "LICENSE").read_text()
    marketplace = read(ROOT / ".agents/plugins/marketplace.json")
    assert marketplace["name"] == "codex-openclaw"
    entry, = marketplace["plugins"]
    assert entry["name"] == portable["name"]
    assert entry["source"] == {"source": "local", "path": "./plugins/openclaw-bridge"}
    assert entry["policy"]["installation"] == "AVAILABLE"
    skill = (PLUGIN / "skills/ask-openclaw/SKILL.md").read_text()
    assert skill.startswith("---\nname: ask-openclaw\n")
    print("PASS: manifests, marketplace, MCP entrypoint, skill, docs, and MIT license")


if __name__ == "__main__":
    main()
