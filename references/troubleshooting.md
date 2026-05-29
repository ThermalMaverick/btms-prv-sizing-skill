# Troubleshooting

Most setup-time and end-user troubleshooting lives in [../README.md](../README.md).
The items below are things Claude actually hits **during a session** — keep
them in mind when a step fails.

| Symptom | Likely cause | Fix |
|---|---|---|
| Relay fails with `WinError 10013` | Port is reserved (often 7950–8149 on Hyper-V/WSL2 machines) | Retry with `RELAY_PORT=9080` (Browser Path only) |
| Dropdowns stuck on "Loading…" *(Browser Path)* | API is unreachable | Re-run the Pre-flight `/health` curl; if local, the user probably hasn't started their local backend yet |
| Watcher runs but never streams results to chat | Launched with `run_in_background` instead of the **Monitor tool** — a backgrounded process only notifies on exit, and the watcher never exits | Relaunch `watch_results.py` via the **Monitor tool** with `persistent: true` (Browser Path Step B2) |
| Watcher never emits new lines | User hasn't clicked ▶ Run, or relay's `/local-results` POST is failing | Ask the user to check the browser DevTools → Network panel |
| MCP `/mcp` shows "Invalid Host header" | API server is missing `MCP_ALLOWED_HOSTS` | The user (or API provider) needs to set it |
| MCP tool call raised `socket connection was closed unexpectedly` | Transient Streamable-HTTP transport blip, often from dispatching MCP calls concurrently on first contact | Retry the same call **once, sequentially**. Don't curl `/health` (it tests REST, not the MCP transport) or abandon MCP — a prior successful MCP tool this session means the layer is up |
| MCP call returns 401 (missing key) | No key reached the server. Three auth paths are accepted — `X-API-Key` header, `Authorization: Bearer <key>`, and a `?api_key=<key>` query-string — but none was present | Add `X-API-Key` to the `headers` block in `.mcp.json` (preferred), or append `?api_key=<key>` to the URL (the claude.ai Connector dialog has no header field, so it uses the query-string path) |
| MCP returns 429 `Rate limit exceeded` | Per-key throttle (default 60 RPM) tripped | Wait 60 s, or set `RATE_LIMIT_RPM` higher in the backend env |
| `/solve` returns 500 `Internal solver error.` | Solver crashed; details intentionally not in response | Ask the API provider to check server logs (the full traceback is logged via `log.exception`) |
| Browser POST to `/local-results` rejected 401 | Relay token mismatch — HTML opened outside the relay (`file://` or wrong port) | Open the page only through the relay URL `http://127.0.0.1:<relay_port>` |
| `last_result.json` is being read but Claude sees stale data | Watcher script process was killed; MCP wrote a result but watcher is no longer running | Restart `watch_results.py` via the **Monitor tool** (`persistent: true`) with the original `_RESULT_PATH`. MCP-tagged writes (`__source__: "mcp"`) are filtered out on purpose so you do not see false GUI duplicates |
