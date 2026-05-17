# btms-prv-sizing — Battery Pack PRV Sizing

Browser GUI + Claude Code Skill for **battery pack pressure-relief-valve (PRV)
sizing**. Models internal pack pressure rise during thermal-runaway events
using a lumped-parameter BDF ODE solver, then helps you pick a PRV that keeps
peak pressure below safe limits.

The compute lives on a private FastAPI service. This repo only ships the
**thin client**: an HTML front-end and a small local relay that wires it into
Claude Code.

> ⚠️ **DEMO data only — not for real engineering design.** The cell and valve
> entries returned by the API are fabricated for demonstration. Benchmark
> against physical experiments before any real design decision.

---

## Three ways to use it

| You are… | Use… | Need… |
|---|---|---|
| Just want to run a sim in a browser | The hosted **GitHub Pages** site below | An API key |
| Claude Code user, want the full chat-in-the-loop experience | Install this repo as a **Claude Code skill** | Claude Code + an API key |
| Claude Code / Desktop / claude.ai Pro+ user, want Claude to drive the solver directly | Configure **HTTP MCP** in your client | An API key |

All three paths talk to the same backend API. You need an API key for any of them.

---

## 1) Browser GUI (zero install)

Hosted on GitHub Pages:

**https://thermalmaverick.github.io/btms-prv-sizing-skill/**

Open the page, paste:
- **API Endpoint**: e.g. `https://btms-prv-sizing.up.railway.app`
- **X-API-Key**: your key

Pick a cell and valve from the dropdowns, set parameters, click ▶ Run. Get
Plotly charts of pressure / temperature / gas / flow, plus CSV and PDF export.

Your endpoint + key are stored in `localStorage` and pre-filled next time.

---

## 2) Claude Code Skill

The full experience: Claude opens the browser, watches for results, and writes
an engineering analysis directly in chat — no copy-paste.

**Install:**

```bash
# Linux / macOS
git clone https://github.com/ThermalMaverick/btms-prv-sizing-skill \
          ~/.claude/skills/btms-prv-sizing
```

```powershell
# Windows
git clone https://github.com/ThermalMaverick/btms-prv-sizing-skill `
          "$env:USERPROFILE\.claude\skills\btms-prv-sizing"
```

**Trigger it in Claude Code:**

```
/btms-prv-sizing
```

Claude will ask for your API endpoint, key, and relay port; start a local
relay process; open the browser; wait for you to click ▶ Run; then auto-pipe
the result back into the conversation.

---

## 3) HTTP MCP (agentic re-run, no browser)

Lets Claude call the solver as a native tool — perfect for parameter sweeps
and "re-run with X changed" follow-ups.

**Claude Code** — create `.mcp.json` in your project root, or edit
`~/.claude.json` for a global config:

```json
{
  "mcpServers": {
    "btms-prv-sizing": {
      "type": "http",
      "url": "https://btms-prv-sizing.up.railway.app/mcp/",
      "headers": { "X-API-Key": "YOUR-KEY" }
    }
  }
}
```

> The **trailing slash on `/mcp/`** is required — without it the server
> returns a 307 redirect that some MCP clients don't follow.

Restart Claude Code, run `/mcp`, and confirm three tools appear:

| Tool | What it does |
|---|---|
| `prv_solve` | Run the BDF ODE simulation; returns KPI + full timeseries |
| `prv_databases` | List available cell and valve entries |
| `prv_parameters` | Get input parameter ranges and units |

**Claude Desktop / claude.ai Pro+** — paste the same URL and header value
into the remote MCP section of Settings → Integrations.

---

## Getting an API key

API keys are issued via RapidAPI subscription. **[Subscribe link to be added]**

For local development you can run your own copy of the backend (private repo,
not included here) and use whatever key you set in its `API_KEYS` env var.

---

## What's in this repo

```
btms-prv-sizing-skill/
├── README.md             ← you are here
├── LICENSE               ← PolyForm Noncommercial 1.0.0 (commercial use prohibited)
├── SKILL.md              ← instructions Claude follows when /btms-prv-sizing is invoked
├── index.html            ← redirect to scripts/btms_prv_sizing_app.html (for GitHub Pages)
└── scripts/
    ├── btms_prv_sizing_app.html   ← the actual GUI (Plotly, vanilla JS, single file)
    └── local_relay.py             ← localhost HTTP server that serves the HTML
                                     and writes last_result.json on POST
```

The HTML is a **single static file** — no build step, no dependencies beyond
the Plotly CDN. Anything you can do with the Pages-hosted site you can also
do by opening `scripts/btms_prv_sizing_app.html` from disk in any browser
(though some CORS-strict browsers may need it served by `local_relay.py`).

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Page loads but dropdowns stuck on "Loading…" | Wrong API endpoint, or backend is down | Check the URL; `curl <endpoint>/health` should return 200 |
| `403 Invalid API key` | Key mismatch or trailing whitespace | Re-copy the key carefully; no surrounding quotes |
| Claude Code `/mcp` shows "Invalid Host header" | API server's `MCP_ALLOWED_HOSTS` env var missing your hostname | Talk to the API provider, or set it on your own backend |
| Local relay reports `WinError 10013` | Windows reserved port range | Set `RELAY_PORT=9080` (or any port outside 7950–8149) before starting |
| Skill doesn't appear in Claude Code | Wrong install path | Layout must be `~/.claude/skills/btms-prv-sizing/SKILL.md` — one level, no nested folder |

More detail in `SKILL.md` (Troubleshooting section).

---

## License

[PolyForm Noncommercial 1.0.0](LICENSE) — free to use for personal, research,
academic, and evaluation purposes. **Commercial use requires a separate
license** from the copyright holder. See `LICENSE` for the full text.

Copyright © 2026 Thermal Maverick (maverick.thermal@gmail.com). The compute
core (`core/solver.py`, cell/valve databases, PDF reporting) lives in a
separate **private** repository and is not redistributed here.

---

## Contributing

This repo is a published artefact, not a development upstream. Issues are
welcome (bug reports for the HTML, SKILL.md, or relay); pull requests are
considered case-by-case. Please open an issue describing the change before
spending time on a PR.
