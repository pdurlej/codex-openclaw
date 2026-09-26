#!/usr/bin/env python3
"""Convenience CLI for a source checkout; installed plugins use their own entrypoint."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "plugins" / "openclaw-bridge" / "scripts"))
from openclaw_bridge import main

if __name__ == "__main__":
    raise SystemExit(main())
