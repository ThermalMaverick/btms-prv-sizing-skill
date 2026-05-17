---
name: btms-prv-sizing
description: Battery pack pressure-relief-valve (PRV) sizing tool. Launches a local HTML GUI that calls a remote FastAPI solver to simulate thermal-runaway pressure rise (lumped-parameter BDF ODE) and recommend PRV configuration. Results are auto-piped back to chat — no copy-paste.
when_to_use: User asks about PRV sizing, pressure-relief valve selection, battery pack pressure, pack pressure simulation, thermal-runaway pressure modelling, 泄压阀选型, 电池包压力, 热失控仿真, or explicitly invokes /btms-prv-sizing.
---

# btms-prv-sizing — Battery Pack PRV Sizing Tool

## What this skill does
Launches a local HTML GUI that calls a remote FastAPI solver (BDF ODE). After
the user clicks ▶ Run, results are auto-posted back to Claude — no copy-paste.

Two complementary paths are supported:
- **Browser GUI** (this skill) — interactive Plotly charts, CSV/PDF export.
- **HTTP MCP** (optional, recommended for agentic re-runs) — Claude calls
  `prv_solve` directly without opening the browser. Configured in the user's
  `.mcp.json` or Claude Code `settings.json`; see [Optional: HTTP MCP] below.

---

## Pre-flight check

Ask the user for:

1. **API Endpoint** — e.g. `https://btms-prv-sizing.up.railway.app` (production)
   or `http://127.0.0.1:9000` (local FastAPI for development)
2. **API Key** — their `X-API-Key` value
3. **Relay port** — default **9080** on Windows (ports 7950–8149 are often
   reserved by Hyper-V/WSL2); use 8080 on Mac/Linux unless taken

**Before touching the relay or browser, verify the API server is reachable.**

```powershell
# Windows
curl.exe <api_endpoint>/health
```

```bash
# Mac / Linux
curl -s <api_endpoint>/health
```

Expected: `{"status":"ok"}`. If the call fails:
- **Production endpoint** — service may be down; check the API provider's
  status page or contact support.
- **Local endpoint** — tell the user to start the backend in a **separate
  terminal** (outside Claude Code), then confirm back:

  ```powershell
  # Windows / Mac / Linux — uses a .env with API_KEYS set
  uv run uvicorn api.main:app --host 127.0.0.1 --port <api_port> --reload --env-file .env
  ```

> Do NOT proceed to Step 1 until `/health` returns 200. The API's CORS rule
> automatically allows any `localhost` / `127.0.0.1` origin on any port for
> local development; no extra CORS config is required for the relay path.

---

## Execution steps

### Step 1 — Start the relay server (background)

Run with `run_in_background: true`. On Windows always set `RELAY_PORT` and bind
to `127.0.0.1` (using `"localhost"` on Windows 11 can fail with WinError 10013
because it resolves to `::1` IPv6).

```powershell
# Windows
$env:RELAY_PORT = "<relay_port>"
python "$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\local_relay.py"
```
```bash
# Mac / Linux
RELAY_PORT=<relay_port> python ~/.claude/skills/btms-prv-sizing/scripts/local_relay.py
```

After starting, verify the relay is listening (wait ~1 s then run):

```powershell
# Windows
curl.exe http://127.0.0.1:<relay_port>/
```
```bash
# Mac / Linux
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<relay_port>/
```

Expected: HTTP 200. If connection refused, the relay failed to start — check
that `<relay_port>` is not in the Windows excluded range
(`netsh interface ipv4 show excludedportrange protocol=tcp`) and retry with a
different port.

### Step 2 — Open the browser

Always use `127.0.0.1` (not `localhost`) to avoid DNS/IPv6 resolution issues.

```powershell
# Windows
Start-Process "http://127.0.0.1:<relay_port>"
```
```bash
# Mac
open http://127.0.0.1:<relay_port>
```
```bash
# Linux
xdg-open http://127.0.0.1:<relay_port>
```

Inform the user:
> "The PRV Sizing Tool is open at http://127.0.0.1:<relay_port>.
> Your API Endpoint and Key should be pre-filled from last time. If the
> dropdowns show 'Loading…', the API server may be unreachable — re-run the
> Pre-flight check. Once databases load, set your parameters and click ▶ Run."

### Step 3 — Watch for results (background)

Run with `run_in_background: true`:

```bash
python -c "
import pathlib, time, sys
f = pathlib.Path.home() / '.claude' / 'skills' / 'btms-prv-sizing' / 'scripts' / 'last_result.json'
init_mtime = f.stat().st_mtime if f.exists() else 0.0
while True:
    time.sleep(0.5)
    if f.exists():
        mt = f.stat().st_mtime
        if mt > init_mtime:
            print(f.read_text(encoding='utf-8'), flush=True)
            sys.exit(0)
"
```

### Step 4 — Report results in chat

When the watcher completes, produce an engineering analysis using the
**Analysis template** below. Do NOT ask the user to paste anything.

### Step 5 — Agent re-run (without re-opening the browser)

When the user asks to modify a parameter and recompute, pick a path in this
order:

```
Priority 1 — HTTP MCP tool is available (prv_solve appears in /mcp tool list)
  → Direct tool call: prv_solve({...})
  → Works on Claude Code, Claude Desktop, claude.ai Pro+

Priority 2 — MCP not available, but last_result.json exists
  → Read file → modify field → Invoke-RestMethod / curl to /solve
  → Requires the user to have run at least one browser simulation this session
    or a previous one (file persists between sessions)

Priority 3 — Neither available
  → Tell the user: "Either click ▶ Run in the browser first, or configure
    HTTP MCP in .mcp.json (see the public skill repo's README)."
```

Field names follow the [`/local-result-schema`](#) contract — the API's
single source of truth.

**Path 1: HTTP MCP tool (recommended)**

```
prv_solve({
    v_pack:      <m³, 0 < v ≤ 10>,
    p_atm:       <Pa, 50000-200000>,
    t_max:       <s, 0 < t ≤ 600>,
    t_const:     <K, 233.15-473.15>,
    cell_count:  <n, 1-500>,
    valve_count: <new value>,                ← changed per user request
    cell_db_id:  "<id>",
    valve_db_id: "<id>"
})
```

If the user hasn't told you the parameter ranges, call `prv_parameters` first;
if cell/valve IDs are unknown, call `prv_databases` first.

**Path 2: HTTP fallback (when MCP is unavailable)**

```powershell
# Windows PowerShell
$r = Get-Content "$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\last_result.json" `
     -Encoding utf8 | ConvertFrom-Json

# Numeric fields are JSON numbers (per /local-result-schema), no casting needed.
$body = [ordered]@{
    v_pack      = $r.v_pack_L / 1000      # L  → m³
    p_atm       = $r.p_atm_kpa * 1000     # kPa → Pa
    t_max       = $r.t_max_s
    t_const     = $r.t_const_k            # K
    cell_count  = $r.cell_count
    valve_count = <new value>             # ← changed per user request
    cell_db_id  = $r.cell_db_id
    valve_db_id = $r.valve_db_id
} | ConvertTo-Json

Invoke-RestMethod -Uri "<api_endpoint>/solve" -Method POST `
    -Headers @{"X-API-Key" = "<api_key>"} -ContentType "application/json" `
    -Body $body -UseBasicParsing
```

```bash
# Mac / Linux (jq + curl)
F=~/.claude/skills/btms-prv-sizing/scripts/last_result.json
body=$(jq -n --argjson r "$(cat $F)" --argjson valve_count <new value> '{
  v_pack:      ($r.v_pack_L  / 1000),
  p_atm:       ($r.p_atm_kpa * 1000),
  t_max:        $r.t_max_s,
  t_const:      $r.t_const_k,
  cell_count:   $r.cell_count,
  valve_count:  $valve_count,
  cell_db_id:   $r.cell_db_id,
  valve_db_id:  $r.valve_db_id
}')
curl -s -X POST <api_endpoint>/solve \
     -H "X-API-Key: <api_key>" -H "Content-Type: application/json" \
     -d "$body"
```

Format the result with the **Analysis template** below. No need to rewrite
`last_result.json`, restart the relay, or reopen the browser.

---

## Analysis template

```
## PRV Sizing Result

| Parameter         | Value                                  |
|-------------------|----------------------------------------|
| Peak Pressure     | {peak_pressure_kpa:.2f} kPa (absolute) |
| Relative Peak     | {relative_peak_pressure_kpa:.2f} kPa   |
| Valve Opened      | {Yes/No}                               |
| First Open Time   | {first_open_time_s:.2f} s              |
| Pack Volume       | {v_pack_L} L                           |
| Cell Count        | {cell_count}                           |
| Valve Count       | {valve_count}                          |
| Ambient Pressure  | {p_atm_kpa} kPa                        |
| Simulation Time   | {t_max_s} s                            |
```

Then provide 2–4 sentences of engineering commentary:
- Whether the peak pressure is within typical structural limits
- Whether the valve timing looks reasonable relative to the venting duration
- Whether increasing valve count or opening pressure might improve the result
- Any recommendation for the next design iteration

---

## Optional: HTTP MCP (for power users)

To let Claude run `prv_solve` directly — useful for parameter sweeps and
"re-run with X changed" follow-ups — configure HTTP MCP in your client.

**Claude Code (`.mcp.json` in the project root, or `~/.claude.json` globally):**

```json
{
  "mcpServers": {
    "btms-prv-sizing": {
      "type": "http",
      "url": "https://your-api-endpoint.example.com/mcp/",
      "headers": { "X-API-Key": "your-key-here" }
    }
  }
}
```

Note the **trailing slash on `/mcp/`** — without it the server returns a
307 redirect that some MCP clients don't follow.

After saving, restart Claude Code and run `/mcp` to confirm the three tools
appear: `prv_solve`, `prv_databases`, `prv_parameters`.

**Claude Desktop and claude.ai Pro+** support remote HTTP MCP servers through
their respective Settings → Integrations panels; paste the same URL +
`X-API-Key` header value.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Relay WinError 10013 on port 8080 | Port reserved by Windows (7950–8149 on Hyper-V/WSL2 machines). Use `RELAY_PORT=9080` |
| Relay WinError 10013 even after port change | `"localhost"` resolved to IPv6. `local_relay.py` already binds `127.0.0.1`; re-copy from the skill repo if you're on an older copy |
| Dropdowns stuck on "Loading…" | API server unreachable or wrong endpoint URL. Re-run Pre-flight `curl /health` |
| `/mcp` shows "Invalid Host header" | Production API needs `MCP_ALLOWED_HOSTS=<your-host>` set on the server. Talk to the API provider if the URL is hosted, or set it yourself if you run the API |
| Watcher never completes | User hasn't clicked Run, or `/local-results` POST failed (check browser DevTools → Network) |
| Port 8080 / 9080 already in use | `netstat -ano \| findstr :<port>` → `taskkill /PID <PID> /F` (Windows) |
| PDF download fails | The `/report` endpoint requires matplotlib + reportlab on the API server |

---

## Installation (for users)

The skill is a **directory**, not a single file:

```bash
# Option A — git clone (recommended; pulls updates with git pull)
git clone https://github.com/ThermalMaverick/btms-prv-sizing-skill ~/.claude/skills/btms-prv-sizing

# Option B — copy from a local checkout
cp -r btms-prv-sizing-skill ~/.claude/skills/btms-prv-sizing   # Mac/Linux
```
```powershell
# Option B — Windows PowerShell
Copy-Item -Recurse btms-prv-sizing-skill "$env:USERPROFILE\.claude\skills\btms-prv-sizing"
```

Expected layout after install:
```
~/.claude/skills/btms-prv-sizing/
├── SKILL.md
├── index.html              ← redirect for GitHub Pages users; harmless locally
└── scripts/
    ├── btms_prv_sizing_app.html
    └── local_relay.py
```

Then in Claude Code, type `/btms-prv-sizing` to trigger the skill.
