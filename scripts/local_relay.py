# Copyright © 2026 Thermal Maverick. See NOTICE at project root.
"""
Local relay server for the btms-prv-sizing Skill.

Serves btms_prv_sizing_app.html on http://127.0.0.1:<RELAY_PORT> and accepts
POST /local-results from the browser, writing the KPI summary to
last_result.json so Claude can read it automatically via the Monitor tool.

Security:
- CORS is restricted to the relay's own origin (no wildcard `*`); other
  websites in the user's browser cannot POST to /local-results.
- A random one-shot token is generated at startup and injected into the
  served HTML; every POST to /local-results must include an `X-Relay-Token`
  header matching that token. Override with the RELAY_TOKEN env var if you
  need a deterministic value (e.g. for testing).

Usage (started by the Skill):
    python local_relay.py

Override port (if 8080 is reserved by Windows/Hyper-V/WSL2):
    $env:RELAY_PORT = "9080"; python local_relay.py   # PowerShell
    RELAY_PORT=9080 python local_relay.py              # bash
"""
from __future__ import annotations

import json
import os
import pathlib
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

_HERE        = pathlib.Path(__file__).parent
_HTML_FILE   = _HERE / "btms_prv_sizing_app.html"
_RESULT_FILE = _HERE / "last_result.json"
_PORT        = int(os.environ.get("RELAY_PORT", "8080"))
_TOKEN       = os.environ.get("RELAY_TOKEN") or secrets.token_urlsafe(24)
_MAX_BODY    = 1_048_576  # 1 MB — guards against runaway local POSTs
# Allow both 127.0.0.1 and localhost so the browser's POST to /local-results
# succeeds regardless of which form the user typed in the address bar.
_ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{_PORT}",
    f"http://localhost:{_PORT}",
}

# Placeholder the HTML may contain so we can inject the live token at serve time.
_TOKEN_PLACEHOLDER = "__RELAY_TOKEN__"


class _RelayHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):  # suppress default access log
        pass

    def _cors(self):
        # Echo back the request origin if it is one of the two allowed forms
        # (127.0.0.1 or localhost on the relay port); fall back to 127.0.0.1.
        req_origin = self.headers.get("Origin", "")
        origin = req_origin if req_origin in _ALLOWED_ORIGINS else f"http://127.0.0.1:{_PORT}"
        self.send_header("Access-Control-Allow-Origin", origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Relay-Token")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path in ("/", "/index.html", "/btms_prv_sizing_app.html"):
            try:
                raw = _HTML_FILE.read_text(encoding="utf-8")
            except FileNotFoundError:
                self._404()
                return
            # Inject the live relay token so the browser's JS can echo it back
            # in the X-Relay-Token header.
            content = raw.replace(_TOKEN_PLACEHOLDER, _TOKEN).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self._cors()
            self.end_headers()
            self.wfile.write(content)
        else:
            self._404()

    def do_POST(self):
        if self.path != "/local-results":
            self._404()
            return

        # Token check — fail closed before reading the body.
        supplied = self.headers.get("X-Relay-Token", "")
        if not supplied or not secrets.compare_digest(supplied, _TOKEN):
            self.send_response(401)
            self._cors()
            self.end_headers()
            self.wfile.write(b"missing or invalid X-Relay-Token")
            return

        length = int(self.headers.get("Content-Length", 0))
        if length > _MAX_BODY:
            self.send_response(413)
            self._cors()
            self.end_headers()
            self.wfile.write(b"Payload too large (> 1 MB)")
            return
        body = self.rfile.read(length)
        try:
            data = json.loads(body)
            # Tag the write so the Skill's watcher can distinguish
            # browser-originated results from MCP-originated writes. The
            # watcher only emits new chat updates when __source__ == "browser".
            data["__source__"] = "browser"
            data["__written_at__"] = time.time()
            _RESULT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
            self.send_response(200)
            self._cors()
            self.end_headers()
        except Exception as exc:
            self.send_response(400)
            self._cors()
            self.end_headers()
            self.wfile.write(str(exc).encode())

    def _404(self):
        self.send_response(404)
        self.end_headers()


if __name__ == "__main__":
    # Bind to 127.0.0.1 (IPv4) explicitly — "localhost" on Windows 11 may
    # resolve to ::1 (IPv6) which can trigger WinError 10013 even when
    # the port is not in the Hyper-V/WSL2 excluded range.
    server = HTTPServer(("127.0.0.1", _PORT), _RelayHandler)
    print(f"PRV Sizing relay server running at {_ORIGIN}", flush=True)
    print(f"Results will be written to: {_RESULT_FILE}", flush=True)
    print(f"Relay token (auto-generated, posted in X-Relay-Token): {_TOKEN}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.", flush=True)
        sys.exit(0)
