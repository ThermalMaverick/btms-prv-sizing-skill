# Playbook — MCP Path, Browser Path, HTTP Fallback, Analysis template

Detailed commands and decision rules for the steps summarised in
[../SKILL.md](../SKILL.md). Reference this file when you are actually
executing a step — `SKILL.md` is the router, this is the procedures manual.

---

## MCP Path

Do **not** start the relay or open a browser. Execute the steps in order.

### Step M1 — Fetch schema, disambiguate, map DB IDs

> ⚠️ Call MCP tools **sequentially**, never in one parallel batch — await
> `prv_parameters` before calling `prv_databases`. Concurrent calls during the
> first-contact session setup can drop a connection (see the transient-error
> handling under Step M4).

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
- `t_const ∈ [233.15, 1273.15] K`
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
| t_const      | 60°C        | 333.15 K       | user (converted)| [233.15, 1273.15] K|
| cell_db_id   | NCM 40Ah    | "01" (Demo-NCM-40Ah) | user (matched) | —            |
| valve_db_id  | —           | "01" (S001, Spring)  | default        | —            |
```

> ℹ️ `valve_count = N` means N **identical** valves in parallel (same type,
> same P-Q curve). To model mixed valves, run multiple simulations.

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

1. Format the result using the **Analysis template** below.
2. **Write `last_result.json`** — only when `runtime == "code"`. Path:
   use **`_RESULT_PATH`** captured in Step B1 if the relay was started this
   session; otherwise fall back to
   `~/.claude/skills/btms-prv-sizing/scripts/last_result.json`
   (Windows: `$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\last_result.json`).
   Use the `/local-result-schema` field layout (identical to what the browser
   writes), **plus two marker fields**:
   ```json
   { "...standard fields...": "...",
     "__source__":     "mcp",
     "__written_at__": <unix_seconds> }
   ```
   The `__source__` tag is critical — without it, the long-lived Step B2
   watcher would mistake this MCP write for a GUI ▶ Run click and emit a
   duplicate result. The relay tags its own writes as `"browser"`; the
   watcher only emits when `__source__ == "browser"`.

   This file is used for: (1) pre-filling the GUI form if the user later
   says "open the GUI", and (2) the HTTP-fallback re-run path.

   When `runtime == "headless"` there is no filesystem — skip this step.
3. Close with:
   > "To re-run with different parameters, just tell me the new values."

   When `runtime == "code"`, also offer:
   > "To see interactive charts, export a PDF, or tune with sliders, say
   > 'open the GUI'."

**On failure:**

- **API returned non-2xx** (e.g. validation error, 4xx, 5xx) → parse the error
  body, tell the user exactly which parameter is wrong, and return to Step M2.
- **Transient transport error** — `socket connection was closed unexpectedly`,
  connection reset, or a timeout (the call *raised* instead of returning an HTTP
  status) → almost always a one-off, not an outage. **Retry the same call once,
  sequentially.** Do **not** curl `/health` or `/ready` to "check MCP": those
  exercise the REST stack, not the Streamable-HTTP transport, so they prove
  nothing about a failed tool call. If any MCP tool has already succeeded this
  session, the layer is up — treat a single failure as transient and retry it
  rather than abandoning MCP for the browser.
- **Auth (401/403), rate limit (429), or genuine outage** (the retry above also
  failed) → tell the user and offer a fallback:
  > "MCP call failed: \<reason\>. Options:
  > (1) retry,
  > (2) switch to the browser path so you can fill the form manually."

  If the user picks (2) and `runtime == "code"`, jump to **Browser Path → Pre-flight** below.

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

After starting the relay, immediately **Monitor** it for up to 3 seconds to capture
its startup output. Find the line beginning `Results will be written to: ` and extract
the full path that follows — store it as **`_RESULT_PATH`** for use in Steps B2 and M4.

Example startup output:
```
PRV Sizing relay server running at http://127.0.0.1:9080
Results will be written to: C:\Users\you\.claude\skills\btms-prv-sizing\scripts\last_result.json
Relay token (auto-generated, posted in X-Relay-Token): abc123...
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

### Step B2 — Arm the result stream (Monitor tool, long-lived)

Launch the watcher **before** opening the browser, so the user's first ▶ Run
click cannot be missed. Use the **Monitor tool** with `persistent: true` —
**not** `run_in_background`. A `run_in_background` process only notifies you
when it *exits*; the watcher loops forever and never exits, so its per-click
output would never surface in chat. The Monitor tool turns each stdout line
into a chat event — exactly the per-click stream we want.

It is the dedicated `scripts/watch_results.py` script, called with the
`_RESULT_PATH` captured in Step B1:

```powershell
# Windows
python "$env:USERPROFILE\.claude\skills\btms-prv-sizing\scripts\watch_results.py" "<_RESULT_PATH>"
```

```bash
# macOS / Linux
python ~/.claude/skills/btms-prv-sizing/scripts/watch_results.py "<_RESULT_PATH>"
```

The watcher must stay alive for the entire session (`persistent: true`) so
multiple ▶ Run clicks all get streamed back to chat — do **not** exit after
the first hit. Each JSON line on its stdout is one ▶ Run click from the
browser. There is no need (and no way) to re-launch it between clicks.

### Step B3 — Open the browser

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

### Step B4 — Report

When the watcher emits the JSON, format it with the **Analysis template**.
Do not ask the user to paste anything.

---

## HTTP Fallback (MCP unavailable + `last_result.json` present)

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

When `runtime == "code"`, tell the user:
> "No MCP tool is available and there is no prior result on disk. I can
> either (1) start the browser path so you can fill the form manually, or
> (2) you can configure HTTP MCP in `.mcp.json` (see README)."

When `runtime == "headless"`, tell the user:
> "No MCP connector is available in this session and there is no GUI
> path in Claude Desktop / claude.ai. Please configure HTTP MCP in
> Settings → Integrations (see README) and restart the conversation."

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

**Downloads** (link valid ~1 hour):
- [📊 CSV — full timeseries]({csv_url})
- [📄 PDF report — with charts]({pdf_url})
```

The MCP `prv_solve` response carries `csv_url` and `pdf_url` — render them as
the clickable links above. The pressure/temperature curves are **in the PDF**.

> ⛔ Do NOT plot or reconstruct the pressure curve in chat. The MCP response
> deliberately omits the raw timeseries; any chart you draw would be fabricated.
> Point the user at the PDF/CSV instead.

Follow the table with **2–4 sentences** of engineering commentary covering:

- Whether the peak pressure is within typical structural limits.
- Whether the valve timing looks reasonable relative to the venting duration.
- Whether more valves or a different opening pressure might improve the result.
- A concrete suggestion for the next design iteration.
