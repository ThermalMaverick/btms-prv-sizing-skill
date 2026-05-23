# Troubleshooting

Most setup-time and end-user troubleshooting lives in [../README.md](../README.md).
The items below are things Claude actually hits **during a session** — keep
them in mind when a step fails.

| Symptom | Likely cause | Fix |
|---|---|---|
| Relay fails with `WinError 10013` | Port is reserved (often 7950–8149 on Hyper-V/WSL2 machines) | Retry with `RELAY_PORT=9080` (Browser Path only) |
| Dropdowns stuck on "Loading…" *(Browser Path)* | API is unreachable | Re-run the Pre-flight `/health` curl; if local, the user probably hasn't started uvicorn yet |
| Watcher never emits new lines | User hasn't clicked ▶ Run, or relay's `/local-results` POST is failing | Ask the user to check the browser DevTools → Network panel |
| MCP `/mcp` shows "Invalid Host header" | API server is missing `MCP_ALLOWED_HOSTS` | The user (or API provider) needs to set it |
| MCP call returns 401 `Missing X-API-Key header` | `?api_key=...` query-string fallback was removed in the security cleanup; header is the only path | Add `X-API-Key` to the `headers` block in `.mcp.json` |
| MCP returns 429 `Rate limit exceeded` | Per-key throttle (default 60 RPM) tripped | Wait 60 s, or set `RATE_LIMIT_RPM` higher in the backend env |
| `/solve` returns 500 `Internal solver error.` | Solver crashed; details intentionally not in response | Ask the API provider to check server logs (the full traceback is logged via `log.exception`) |
| Browser POST to `/local-results` rejected 401 | Relay token mismatch — HTML opened outside the relay (`file://` or wrong port) | Open the page only through the relay URL `http://127.0.0.1:<relay_port>` |
| `last_result.json` is being read but Claude sees stale data | Watcher script process was killed; MCP wrote a result but watcher is no longer running | Restart `watch_results.py` with the original `_RESULT_PATH`. MCP-tagged writes (`__source__: "mcp"`) are filtered out on purpose so you do not see false GUI duplicates |
