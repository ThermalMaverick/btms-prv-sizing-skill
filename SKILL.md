---
name: btms-prv-sizing
description: Size pressure-relief valves (PRVs) for battery packs. Routes to either a browser GUI (interactive Plotly charts, CSV/PDF export) or direct MCP tool calls (zero-friction parameter sweeps), depending on user intent. Backed by a lumped-parameter pack-pressure solver. Use when the user asks about PRV sizing, pressure-relief valve selection, explosion-proof valve selection, burst valve selection, pressure-released device selection, battery pack pressure simulation, thermal-runaway pressure modelling — in English or Chinese (泄压阀选型 / 电池包压力 / 热失控压力仿真 / 防爆阀选型) — or explicitly invokes /btms-prv-sizing.
---

# btms-prv-sizing — Battery Pack PRV Sizing

## Overview

Two execution paths share the same backend API:

- **Browser Path** — local relay serves an HTML GUI; user clicks ▶ Run; results
  auto-stream back to chat. Claude Code only (needs `bash`/`PowerShell` and a
  writeable filesystem). Best for exploring, charting, and exporting reports.
- **MCP Path** — Claude calls `prv_solve` directly via HTTP MCP; results land
  in chat with no relay or browser. Works in any environment with the MCP
  connector configured. Best for "I already know my parameters" and parameter
  sweeps.

Setup, installation, `.mcp.json` configuration, and end-user troubleshooting
live in [README.md](README.md). Detailed step-by-step commands for each path
live in [references/playbook.md](references/playbook.md). Common runtime
gotchas live in [references/troubleshooting.md](references/troubleshooting.md).
This file is the **runtime playbook router** — follow it from top to bottom
every time the skill is invoked.

---

## Step 0 — Environment detection (run once per session)

Before the Route Decision, determine which runtime profile this session is in.
The signal is whether a shell tool is available.

1. Scan the active tool list / system reminder for a `Bash` or `PowerShell`
   tool whose description mentions executing shell commands. If present →
   set `runtime = "code"`.
2. Otherwise → set `runtime = "headless"` (Claude Desktop / claude.ai — no
   relay, no filesystem, no browser). **Only MCP Path is available.**

Remember `runtime` for the rest of the session — do NOT re-detect on every
turn.

---

## Route Decision

Evaluate in order; first match wins.

### Condition 0 — Explicit GUI intent (highest priority)

If the user message contains any of these keywords (English or Chinese):

> `GUI` / `界面` / `browser` / `浏览器` / `网页` / `chart` / `图表` /
> `看图` / `tune` / `调参数` / `try` / `试一下` / `export` / `导出` /
> `PDF` / `interactive` / `交互` / `slider` / `滑条` / `可视化`

→ **Force GUI path**, regardless of MCP availability or whether parameters
were provided.

- `runtime == "code"` → **Browser Path**
- `runtime == "headless"` → GUI unavailable; offer to fall back to MCP:
  > "Interactive charts require Claude Code (shell access). In Claude
  > Desktop / claude.ai I can only run the solver via MCP and return
  > the result as a table. Shall I proceed with MCP?"

### Condition 1 — Auto MCP (zero-friction calculation)

A. The user message contains **at least one identifiable input parameter** —
   one of `v_pack`, `cell_count`, `valve_count`, `p_atm`, `t_max`, `t_const`,
   or a cell/valve description that can be mapped to `cell_db_id` /
   `valve_db_id`.

B. The MCP tool `prv_solve` is available in this session (see check below).

→ A ∧ B → **MCP Path**

### Condition 2 — Default

Anything else → GUI path when `runtime == "code"` → **Browser Path**.
When `runtime == "headless"` (no shell), skip Browser Path — ask the user
for parameters and go to **MCP Path** (Step M1).

> Never ask the user "do you want browser or MCP?" That's an implementation
> detail. Infer from intent.

### MCP Availability Check

1. Scan the most recent `<system-reminder>` for `mcp__btms-prv-sizing__prv_solve`.
2. If present as a **deferred tool** (name only, no schema), load schemas:
   `ToolSearch select:mcp__btms-prv-sizing__prv_databases,mcp__btms-prv-sizing__prv_parameters,mcp__btms-prv-sizing__prv_solve`
3. After ToolSearch succeeds → **available**.
4. If the tool name is absent from system-reminder entirely → **unavailable** →
   `runtime == "code"`: fall back to Browser Path.
   `runtime == "headless"`: tell the user MCP is not configured; see README.

> ⚠️ Do not "probe" availability by blindly calling `prv_solve`. That wastes
> API quota and produces misleading errors.

---

## MCP Path (summary)

Five steps, detailed in [references/playbook.md § MCP Path](references/playbook.md):

1. **M1** — Fetch parameter schema (`prv_parameters`), disambiguate bare
   numbers, fuzzy-match `cell_db_id` / `valve_db_id` from user phrases.
2. **M1.5** — Convert user units (L → m³, °C → K, kPa → Pa, min → s) and
   range-check every converted value.
3. **M2** — Build the full parameter confirmation table (user input + SI value
   + source + range). List rows in the **fixed order** defined in
   [references/playbook.md § Step M2](references/playbook.md): Void Volume →
   Ambient Pressure → Gas Temperature → Cell Model → Cell Count → Valve Model
   → Valve Type → Valve Count → Valve Opening Pressure → Simulation Time.
4. **M3** — Wait for explicit confirmation. **Never call `prv_solve` before
   the user confirms.**
5. **M4** — Call `prv_solve`, format with the Analysis template
   ([references/playbook.md § Analysis template](references/playbook.md)), and
   when `runtime == "code"` write `last_result.json` with the marker fields
   `__source__: "mcp"` + `__written_at__`.

> ⚠️ **Call MCP tools one at a time — never in the same parallel tool batch.**
> The Streamable-HTTP session is established on the **first** call; dispatching
> `prv_parameters` / `prv_databases` / `prv_solve` concurrently during that
> setup can get one connection dropped (`socket connection was closed
> unexpectedly`). Await each call's result before issuing the next.

> ⛔ **MCP result presentation.** `prv_solve` returns a KPI summary plus
> `csv_url` / `pdf_url` download links — **not** the raw timeseries. Present
> the KPI table and surface the two links. **Never plot or reconstruct the
> pressure/temperature curve in chat** — there is no series to plot and any
> chart would be fabricated. The curves live in the PDF.

---

## Browser Path (summary)

Pre-flight plus four steps (B1–B4), detailed in [references/playbook.md § Browser Path](references/playbook.md):

1. **Pre-flight** — collect API endpoint, key, relay port; verify `/health`.
2. **B1** — Start `local_relay.py` in the background (Windows: bind to
   `127.0.0.1`, set `RELAY_PORT`); capture `_RESULT_PATH` from its banner.
3. **B2** — Arm the result stream **before opening the browser**: launch the
   long-lived watcher on `_RESULT_PATH` with the **Monitor tool**
   (`persistent: true`). See the command below.
4. **B3** — Open the browser at `http://127.0.0.1:<relay_port>`, then tell the
   user to set parameters and click ▶ Run. Each click streams one JSON line
   from the watcher into chat.
5. **B4** — Format each streamed result with the Analysis template.

> ⚠️ **Launch the watcher with the Monitor tool, not `run_in_background`, and
> do it in B2 — before B3.** A `run_in_background` process only notifies you
> when it *exits*; the watcher loops forever and never exits, so its per-click
> output would never reach chat and results would silently fail to stream.
> Arming it before the browser opens also guarantees the user's first ▶ Run
> click is captured.

The watcher is a single dedicated script — invoke it (Monitor tool,
`persistent: true`) with the result path captured in B1:

```bash
python "<path-to>/skill/scripts/watch_results.py" "<_RESULT_PATH>"
```

It stays alive for the entire session; every ▶ Run click emits a new JSON
line. There is no need to relaunch it between clicks.

---

## Re-run handling

When the user asks to modify a parameter and recompute, **do not restart the
relay**. Re-evaluate Route Decision:

```
Re-run requested
  ├─ Explicit GUI intent ("change it in the GUI") → GUI path
  │      runtime == "code"      → Browser Path (tell user to tweak form +
  │                                click ▶ Run; relay is already running)
  │      runtime == "headless"  → GUI unavailable; offer MCP path instead
  ├─ MCP available                                → MCP Path
  │      (Step M1.5 + M2 + M3 still apply, even for single-field tweaks)
  └─ MCP unavailable
         runtime == "code"      + last_result.json exists → HTTP Fallback
         (see references/playbook.md § HTTP Fallback)
```

> Even for a single-field change, both MCP Path and HTTP Fallback **must**
> show the confirmation table before calling the API. Use the diff-style
> shortcut in M2 to avoid fatigue.

---

## Runtime gotchas (quick reference)

Full troubleshooting matrix lives in
[references/troubleshooting.md](references/troubleshooting.md). The handful of
items Claude actually hits **during a session**:

- **Relay fails with `WinError 10013`** → port is reserved. Retry with
  `RELAY_PORT=9080`.
- **Dropdowns stuck on "Loading…"** → API is unreachable. Re-run Pre-flight
  `/health` curl.
- **Watcher never streams results to chat** → most often it was launched with
  `run_in_background` instead of the **Monitor tool** (a backgrounded process
  only notifies on exit; the watcher never exits) — relaunch via Monitor with
  `persistent: true`. Otherwise the user hasn't clicked ▶ Run, or the relay
  `/local-results` POST is failing.
- **MCP call raised `socket connection was closed unexpectedly`** → transient
  transport blip, often from dispatching MCP calls concurrently. Retry the same
  call **once, sequentially**; don't abandon MCP or curl `/health` (it tests the
  REST stack, not the MCP transport). A prior successful MCP tool this session
  proves the layer is up.
- **MCP `/mcp` shows "Invalid Host header"** → API server needs
  `MCP_ALLOWED_HOSTS` set.
