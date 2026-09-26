"""Private connection configuration, separate from the distributable plugin."""
from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path
import re


@dataclass(frozen=True)
class Config:
    transport: str = "local"
    agent_id: str = "main"
    display_name: str = "OpenClaw"
    openclaw_bin: str = "openclaw"
    ssh_host: str = ""
    run_as_user: str = ""
    remote_python: str = "python3"
    turn_timeout_seconds: int = 180

    def validate(self):
        if self.transport not in ("local", "ssh"):
            raise ValueError("transport must be local or ssh")
        if not isinstance(self.agent_id, str) or not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", self.agent_id):
            raise ValueError("agent_id must contain only letters, digits, underscores, or hyphens")
        if not isinstance(self.display_name, str) or not 1 <= len(self.display_name.strip()) <= 80:
            raise ValueError("display_name must contain 1–80 characters")
        for key in ("openclaw_bin", "remote_python"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value or value.startswith("-") or any(c in value for c in "\n\r\x00"):
                raise ValueError(key + " must name an executable, not shell code or flags")
        if not isinstance(self.ssh_host, str) or (self.ssh_host and not re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.@:\[\]-]{0,254}", self.ssh_host)):
            raise ValueError("ssh_host must be an SSH alias or hostname, optionally user@host")
        if self.transport == "ssh" and not self.ssh_host:
            raise ValueError("ssh_host is required for SSH transport")
        if not isinstance(self.run_as_user, str) or (self.run_as_user and not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_-]{0,63}", self.run_as_user)):
            raise ValueError("run_as_user must be a system account name")
        if self.transport == "local" and (self.ssh_host or self.run_as_user):
            raise ValueError("ssh_host and run_as_user apply only to SSH transport")
        if type(self.turn_timeout_seconds) is not int or not 10 <= self.turn_timeout_seconds <= 1800:
            raise ValueError("turn_timeout_seconds must be an integer between 10 and 1800")
        return self

    @property
    def connection_id(self):
        routing = asdict(self)
        routing.pop("display_name")
        routing.pop("turn_timeout_seconds")
        return hashlib.sha256(json.dumps(routing, sort_keys=True).encode()).hexdigest()


def config_path():
    override = os.environ.get("OPENCLAW_BRIDGE_CONFIG")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return base / "codex-openclaw" / "config.json"


def state_path():
    override = os.environ.get("OPENCLAW_BRIDGE_DATA")
    if override:
        return Path(override).expanduser().resolve()
    base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state")))
    return base / "codex-openclaw"


def load_config():
    path = config_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError("Connection is not configured. Run openclaw_bridge.py configure; see the plugin README.") from None
    except (OSError, ValueError):
        raise ValueError("Cannot read the private connection configuration; check its path and JSON syntax.") from None
    if not isinstance(payload, dict) or set(payload) - set(Config.__dataclass_fields__):
        raise ValueError("Configuration contains unsupported fields. Credentials belong to the existing OpenClaw/SSH setup.")
    return Config(**payload).validate()


def save_config(config):
    config.validate()
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    # Exclusive creation: existing private configuration is never overwritten.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as stream:
        json.dump(asdict(config), stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return path
