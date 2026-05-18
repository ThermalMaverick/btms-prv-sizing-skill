---
name: btms-prv-sizing
description: Size pressure-relief valves (PRVs) for battery packs. Routes to either a browser GUI (interactive Plotly charts, CSV/PDF export) or direct MCP tool calls (zero-friction parameter sweeps), depending on user intent. Backed by a FastAPI lumped-parameter BDF ODE solver.
when_to_use: User asks about PRV sizing, pressure-relief valve selection, battery pack pressure simulation, thermal-runaway pressure modelling — in English or Chinese (泄压阀选型 / 电池包压力 / 热失控仿真) — or explicitly invokes /btms-prv-sizing.
---

# btms-prv-sizing — Battery Pack PRV Sizing

## Overview

Two execution paths share the same backend API:

- **Browser Path** — local relay serves an HTML GUI; user clicks ▶ Run; results
  auto-stream back to chat. Best for exploring, charting, and exporting reports.
- **MCP Path** — Claude calls `prv_solve` directly via HTTP MCP; results land
  in chat with no relay or browser. Best for "I already know my parameters"
  and parameter sweeps.

Setup, installation, `.mcp.json` configuration, and end-user troubleshooting
live in [README.md](README.md). This file is the **runtime playbook** —
follow it from top to bottom every time the skill is invoked.

---

## Route Decision

Before doing anything else, pick an execution path. Evaluate the conditions
in order — the first match wins.

### Condition 0 — Explicit GUI intent (highest priority)

If the user message contains any of these keywords (English or Chinese):

> `GUI` / `界面` / `browser` / `浏览器` / `网页` / `chart` / `图表` /
> `看图` / `tune` / `调参数` / `try` / `试一下` / `export` / `导出` /
> `PDF` / `interactive` / `交互` / `slider` / `滑条` / `可视化`

→ **Force Browser Path**, regardless of MCP availability or whether
parameters were provided.

### Condition 1 — Auto MCP (zero-friction calculation)

A. The user message contains **at least one identifiable input parameter** —
   one of `v_pack`, `cell_count`, `valve_count`, `p_atm`, `t_max`, `t_const`,
   or a cell/valve description that can be mapped to `cell_db_id` /
   `valve_db_id`.

B. The MCP tool `prv_solve` is available in this session (see check below).

→ A ∧ B → **MCP Path**

### Condition 2 — Default

Anything else → **Browser Path**.

> Never ask the user "do you want browser or MCP?" That's an implementation
> detail. Infer from intent.

### MCP Availability Check

Determine availability of `prv_solve` in this order:

1. Scan the most recent `<system-reminder>` for `mcp__btms-prv-sizing__prv_solve`.
2. If present as a **deferred tool** (name only, no schema), load schemas:
   `ToolSearch select:mcp__btms-prv-sizing__prv_databases,mcp__btms-prv-sizing__prv_parameters,mcp__btms-prv-sizing__prv_solve`
3. After ToolSearch succeeds → **available**.
4. If the tool name is absent from system-reminder entirely → **unavailable** →
   fall back to Browser Path.

> ⚠️ Do not "probe" availability by blindly calling `prv_solve`. That wastes
> API quota and produces misleading errors.

---

## MCP Path

Do **not** start the relay or open a browser. Execute these five steps in order.

### Step M1 — Fetch schema, disambiguate, map DB IDs

1. Call `prv_parameters` (once per session) to get default values and ranges
   for every input field.
2. **Ambiguity guard.** If the user offered a bare number with no field name
   (e.g. "算一下 30 的", "100 的电芯"), ask a clarifying question before
   continuing — avoid misreading "100Ah cell" as `cell_count = 100`:
   > "你说的 100 是电芯数量、容量 (Ah)、还是其他？"
3. **DB-ID mapping.** Users describe cells by model/brand
   (e.g. "NCM523", "宁德某型"), not by `cell_db_id` string:
   - Call `prv_databases`, fuzzy-match the description.
   - **Match found** → adopt it; mark "matched from: \<user phrase\>" in the
     Step M2 table.
   - **No match** → present the available IDs and ask the user to pick. Do
     **not** silently substitute a default ID.
   - Same procedure for `valve_db_id`.

### Step M1.5 — Unit conversion (mandatory)

Users speak in everyday units; the API requires strict SI. Convert per the
table below before building the confirmation table:

| User wrote                   | API field   | API unit | Conversion       |
|------------------------------|-------------|----------|------------------|
| `30L` / `30 升`              | `v_pack`    | m³       | ÷ 1000           |
| `1 atm`                      | `p_atm`     | Pa       | × 101325         |
| `101 kPa` / `100 kPa`        | `p_atm`     | Pa       | × 1000           |
| `60°C` / `60 度`             | `t_const`   | K        | + 273.15         |
| `333 K`                      | `t_const`   | K        | as-is            |
| `5 分钟` / `5 min`           | `t_max`     | s        | × 60             |
| `300 秒` / `300 s`           | `t_max`     | s        | as-is            |

**Range check** — if any converted value falls outside its valid range,
**tell the user immediately and stop**; do not submit out-of-range values:

- `v_pack ∈ (0, 10] m³`
- `p_atm ∈ [50000, 200000] Pa`
- `t_max ∈ (0, 600] s`
- `t_const ∈ [233.15, 473.15] K`
- `cell_count ∈ [1, 500]`
- `valve_count ∈ [1, 50]`

### Step M2 — Build the parameter confirmation table

Merge user-supplied values (post-conversion) with schema defaults. Show the
**full parameter list** with both the user's original phrasing and the SI
value, so the user can spot conversion errors at a glance:

```
| Field        | User input  | SI value       | Source         | Range              |
|--------------|-------------|----------------|----------------|--------------------|
| v_pack       | 30L         | 0.030 m³       | user           | (0, 10] m³         |
| cell_count   | 100         | 100            | user           | [1, 500]           |
| valve_count  | —           | 2              | default        | [1, 50]            |
| p_atm        | —           | 101325 Pa      | default        | [50000, 200000] Pa |
| t_max        | —           | 300 s          | default        | (0, 600] s         |
| t_const      | 60°C        | 333.15 K       | user (converted)| [233.15, 473.15] K|
| cell_db_id   | NCM523      | "cell_ncm523"  | user (matched) | —                  |
| valve_db_id  | —           | "valve_001"    | default        | —                  |
```

Then prompt:
> "Here is the full parameter set — your values converted to SI, defaults
> filled in for the rest. Confirm to run, or tell me what to change."

**Single-parameter re-run shortcut.** When only one field differs from the
previous run, use a diff-style summary to avoid confirmation fatigue:

```
Changing: valve_count: 2 → 4
All other parameters unchanged from last run (v_pack=0.030 m³, cell_count=100, …).
Confirm to run.
```

### Step M3 — Wait for confirmation

- User confirms (e.g. "OK", "确认", "go", "算", "没问题") → proceed to Step M4.
- User corrects a value → return to **Step M1.5** (re-convert + re-range-check)
  → redraw the table → wait again.
- **Never call `prv_solve` before explicit confirmation.**

### Step M4 — Solve, report, persist

Call `prv_solve({...})` with the confirmed parameters.

**On success:**

1. Format the result using the **Analysis template** at the bottom of this
   file.
2. **Write `last_result.json`** at
   `~/.claude/skills/btms-prv-sizing/scripts/last_result.json`, using the
   `/local-result-schema` field layout (identical to what the browser writes).
   This lets the user later open the GUI with the form pre-filled, and gives
   the HTTP-fallback re-run path something to read.
3. Close with:
   > "To re-run with different parameters, just tell me the new values.
   > To see interactive charts, export a PDF, or tune with sliders, say
   > 'open the GUI'."

**On failure:**

- **API returned non-2xx** (e.g. validation error, 4xx, 5xx) → parse the error
  body, tell the user exactly which parameter is wrong, and return to Step M2.
- **MCP call itself raised** (network / auth / MCP server down) → tell the
  user and offer a fallback:
  > "MCP call failed: \<reason\>. Options:
  > (1) retry,
  > (2) switch to the browser path so you can fill the form manually."
  
  If the user picks (2), jump to **Browser Path → Pre-flight** below.

---

## Browser Path

### Pre-flight

Ask the user for three values (or reuse what they already gave):

1. **API endpoint** — e.g. `https://btms-prv-sizing.up.railway.app` (production)
   or `http://127.0.0.1:9000` (local dev).
2. **API key** — the `X-API-Key` value.
3. **Relay port** — default **9080** on Windows; ports 7950–8149 are often
   reserved by Hyper-V/WSL2. On macOS/Linux **8080** is fine unless taken.

Verify the API is reachable before touching the relay:

```powershell
# Windows
curl.exe <api_endpoint>/health
```

```bash
# macOS / Linux
curl -s <api_endpoint>/health
```

Expect `{"status":"ok"}`. If `/health` fails:

- **Production** — service is likely down; ask the user to check the provider's
  status page.
- **Local** — instruct the user to start the backend in a **separate terminal
  outside Claude Code** and confirm back:
  ```
  uv run uvicorn api.main:app --host 127.0.0.1 --port <api_port> --reload --env-file .env
  ```

> Do not proceed until `/health` returns 200. The API's CORS rule auto-allows
> any `localhost` / `127.0.0.1` origin on any port, so no extra CORS config is
> needed.

### Step B1 — Start the relay (background)

Run with `run_in_background: true`. On Windows always set `RELAY_PORT` and
bind to `127.0.0.1` — using `"localhost"` on Windows 11 can fail with
`WinError 10013` because it resolves to `::1` IPv6.

```powershell
# Windows
$env:RELAY_PORT = "<relay_port>"
python "$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\local_relay.py"
```

```bash
# macOS / Linux
RELAY_PORT=<relay_port> python ~/.claude/skills/btms-prv-sizing/scripts/local_relay.py
```

Wait ~1 second, then verify the relay responds:

```powershell
# Windows
curl.exe http://127.0.0.1:<relay_port>/
```

```bash
# macOS / Linux
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:<relay_port>/
```

Expect HTTP 200. If connection refused, the port may be in the Windows
excluded range (`netsh interface ipv4 show excludedportrange protocol=tcp`)
— retry with a different port.

### Step B2 — Open the browser

Always use `127.0.0.1` (not `localhost`) to dodge DNS/IPv6 issues.

```powershell
# Windows
Start-Process "http://127.0.0.1:<relay_port>"
```

```bash
# macOS
open http://127.0.0.1:<relay_port>
```

```bash
# Linux
xdg-open http://127.0.0.1:<relay_port>
```

Tell the user:
> "The PRV Sizing Tool is open at http://127.0.0.1:\<relay_port\>. Your API
> endpoint and key should be pre-filled from last time. If the dropdowns are
> stuck on 'Loading…', the API is unreachable — re-run Pre-flight. Once
> databases load, set your parameters and click ▶ Run."

### Step B3 — Watch for results (background)

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

### Step B4 — Report

When the watcher emits the JSON, format it with the **Analysis template**.
Do not ask the user to paste anything.

---

## Re-run handling

When the user asks to modify a parameter and recompute, **do not restart the
relay**. Re-evaluate Route Decision instead:

```
Re-run requested
  ├─ Explicit GUI intent ("change it in the GUI") → Browser Path
  │      (if the relay is still running, just tell the user to tweak the
  │      form and click ▶ Run — no relaunch needed)
  ├─ MCP available                                → MCP Path
  │      (Step M1.5 conversion + Step M2 table + Step M3 confirm still apply,
  │      including for single-field tweaks)
  └─ MCP unavailable + last_result.json exists    → HTTP Fallback below
```

> Even for a single-field change, both MCP Path and HTTP Fallback **must**
> show the confirmation table before calling the API. Use Step M2's
> diff-style shortcut to avoid fatigue.

### HTTP Fallback (MCP unavailable + `last_result.json` present)

1. Read `last_result.json` to recover the previous inputs.
2. Apply the user's edit.
3. Re-convert + range-check exactly as in **Step M1.5**.
4. Show the confirmation table exactly as in **Step M2**.
5. **Only after the user confirms**, POST to `<api_endpoint>/solve`:

```powershell
# Windows PowerShell — run only after user confirms
$r = Get-Content "$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\last_result.json" `
     -Encoding utf8 | ConvertFrom-Json

$body = [ordered]@{
    v_pack      = $r.v_pack_L / 1000      # L  → m³
    p_atm       = $r.p_atm_kpa * 1000     # kPa → Pa
    t_max       = $r.t_max_s
    t_const     = $r.t_const_k
    cell_count  = $r.cell_count
    valve_count = <new value>             # user's edit
    cell_db_id  = $r.cell_db_id
    valve_db_id = $r.valve_db_id
} | ConvertTo-Json

Invoke-RestMethod -Uri "<api_endpoint>/solve" -Method POST `
    -Headers @{"X-API-Key" = "<api_key>"} -ContentType "application/json" `
    -Body $body -UseBasicParsing
```

```bash
# macOS / Linux (jq + curl) — run only after user confirms
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

After the response arrives, format with the Analysis template. Optionally
overwrite `last_result.json` so the GUI form stays in sync on next launch.

### Last-resort path (MCP unavailable + no `last_result.json`)

Tell the user:
> "No MCP tool is available and there is no prior result on disk. I can
> either (1) start the browser path so you can fill the form manually, or
> (2) you can configure HTTP MCP in `.mcp.json` (see README)."

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

Follow the table with **2–4 sentences** of engineering commentary covering:

- Whether the peak pressure is within typical structural limits.
- Whether the valve timing looks reasonable relative to the venting duration.
- Whether more valves or a different opening pressure might improve the result.
- A concrete suggestion for the next design iteration.

---

## Runtime hints

Most setup-time and end-user troubleshooting lives in [README.md](README.md).
The handful of items below are things Claude actually hits **during a
session** — keep them in mind:

- **Relay fails with `WinError 10013`** → port is reserved (often 7950–8149
  on Hyper-V/WSL2 machines). Retry with `RELAY_PORT=9080`.
- **Dropdowns stuck on "Loading…"** → the API is unreachable. Re-run the
  Pre-flight `/health` curl; if local, the user probably hasn't started
  uvicorn yet.
- **Watcher never completes** → user hasn't clicked ▶ Run, or the relay
  `/local-results` POST is failing. Ask the user to check the browser
  DevTools → Network panel.
- **MCP `/mcp` shows "Invalid Host header"** → the API server is missing
  `MCP_ALLOWED_HOSTS`; the user (or API provider) needs to set it.
