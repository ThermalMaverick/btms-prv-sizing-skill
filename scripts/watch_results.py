# Copyright © 2026 Thermal Maverick. See NOTICE at project root.
"""Long-lived watcher: streams every browser-originated last_result.json write.

SKILL.md launches this in the background after starting the relay. Each ▶ Run
click in the GUI triggers one JSON line on stdout, which Claude reads via the
Monitor tool.

The watcher filters by ``__source__ == "browser"`` so that MCP-originated
writes (tagged ``"mcp"`` by SKILL.md Step M4) do not produce a fake "GUI
result" emission.

Usage:
    python watch_results.py <path-to-last_result.json>
"""
from __future__ import annotations

import json
import pathlib
import sys
import time


def main(path_str: str) -> None:
    f = pathlib.Path(path_str)
    last_mtime = f.stat().st_mtime if f.exists() else 0.0
    try:
        while True:
            time.sleep(0.5)
            if not f.exists():
                continue
            mt = f.stat().st_mtime
            if mt <= last_mtime:
                continue
            last_mtime = mt
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if data.get("__source__") == "browser":
                print(json.dumps(data), flush=True)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python watch_results.py <last_result.json>", file=sys.stderr)
        sys.exit(2)
    main(sys.argv[1])
