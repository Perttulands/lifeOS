# PRD: LifeOS — Agent-First Personal Life Coach

**Status:** Approved  
**Author:** PRD-Agent (revised by Hermes after critique)  
**Date:** 2026-03-13 | **Revised:** 2026-03-14  
**Critique verdict:** BUILD MINIMAL (Sonnet) / RETHINK (Opus) → synthesized: BUILD MINIMAL, Sprint 1 = 2 commands + wiring

---

## Overview

LifeOS becomes a CLI tool that AI agents invoke programmatically to coach Perttu. Instead of a browser dashboard, Hermes calls `lifeos brief` at 7am and delivers the result to Discord via cron. Capture happens through conversation — Perttu tells Hermes, Hermes calls `lifeos log`. The existing FastAPI backend, SQLite database, AI engine, and integrations (Oura, Google Calendar) stay untouched. What changes is the interface layer: a `lifeos` binary with a stable agent-native contract (stdout/stderr split, exit codes, `--format json`), built as thin wrappers over the already-decoupled service layer. The web dashboard remains as an optional admin view and receives no new investment.

**Critical finding from critique:** The service layer (`InsightsService`, `PersonalizationService`, all integrations) already accepts plain SQLAlchemy Sessions with no FastAPI coupling. The earlier PRD draft's concern about "service layer refactoring" was unfounded. The adaptation to CLI is ~10 lines.

---

## Goals

| # | Goal | Measure |
|---|------|---------|
| G1 | Perttu receives a morning brief via Discord every day without opening a browser | ≥6 briefs delivered per week within 14 days of Sprint 1 deploy |
| G2 | Conversational capture replaces manual data entry | ≥80% of journal/energy entries arrive via `lifeos log` (not web UI) within 60 days |
| G4 | Non-AI CLI commands return in <2s | p95 latency <2s for `lifeos status`, `lifeos log` — measured on landmass |
| G5 | Zero new infrastructure dependencies | Only `click` added to requirements.txt |

> **G3 removed:** "Goal coaching happens proactively" is Hermes's logic, not LifeOS's responsibility. LifeOS provides `lifeos goal review` output; when and how Hermes acts on it is out of scope for this PRD.

---

## Users & Use Cases

**User 1: Hermes (AI agent — primary user)**

| Use Case | Scenario | Expected Outcome |
|----------|----------|-----------------|
| UC-1 | 7am cron: sync data, generate brief, deliver to Discord | Brief in Discord before Perttu wakes up |
| UC-2 | Perttu says "energy is a 3 today" in Discord | Hermes runs `lifeos log energy 3`, confirms back |
| UC-3 | Perttu says "add goal: finish the nursery by April" | Hermes runs `lifeos goal add "finish the nursery" --target-date 2026-04-30` |
| UC-4 | Hermes wants current status for a coaching response | `lifeos status --format json` → parse and respond |

**User 2: Perttu (human — receives output via Discord)**
- Morning brief arrives, reads it, occasionally replies
- Asks questions that Hermes answers using `lifeos` output
- Rarely touches web dashboard or CLI directly

---

## CLI Design

The `lifeos` binary talks directly to SQLite and instantiates service classes in-process. FastAPI is not a dependency for CLI operations. This is possible today with no refactoring:

```python
db = SessionLocal()
svc = InsightsService(db)
```

FastAPI's `Depends(get_db)` is a thin wrapper around `SessionLocal()` — the CLI bypasses the wrapper and calls it directly.

**Strict rule:** CLI commands are thin wrappers. No business logic in CLI layer. If logic exists, it goes in the service layer where both the CLI and the API router can use it. No divergence.

### Sprint 1 commands (ship these, nothing else)

```
lifeos sync [oura|calendar|all]
```
Trigger data sync from external sources. Returns record count.
- Exit 0: success, prints `Synced N records`
- Exit 2: API error (bad token, network), prints error to stderr

```
lifeos brief [--date DATE] [--format json|text]
```
Generate the daily brief. Default: today.
- `--format text` (default): Discord-ready markdown
- `--format json`: `{"status": "ok", "data": {"content": "...", "date": "...", "confidence": 0.8}, "generated_at": "...", "tokens_used": 412}`
- Exit 0: success; Exit 2: AI call failed (fallback text returned, not an error exit)

### Sprint 2 commands (only after G1 verified live for 2 weeks)

```
lifeos log energy <1-5> [--note "..."] [--date DATE]
lifeos log mood <1-5> [--note "..."] [--date DATE]
lifeos log note "free text" [--tag TAG]
lifeos status [--format json|text]
```

### Sprint 3 commands (only after G2 running)

```
lifeos goal list [--status active|all] [--format json|text]
lifeos goal add "title" [--target-date DATE]
lifeos goal update <id> --progress <0-100>
lifeos goal review [--format json|text]
lifeos pattern [--days 30] [--format json|text]
lifeos weekly [--format json|text]
```

### Output contract (all commands)

- Stdout: data only (text or JSON)
- Stderr: errors, warnings, progress messages
- Exit codes: 0 = success, 1 = user error (bad args), 2 = system error (DB/API failure)
- `--format json` schema: always `{status, data, generated_at}`, feature-specific fields inside `data`

---

## Agentic Flows

### Hermes's 7am Morning Routine (the thing that proves G1)

**Hermes IS the delivery mechanism.** No Discord webhook, no bash script, no intermediaries.

OpenClaw cron fires an isolated agentTurn at 07:00 Europe/Helsinki daily:
1. Hermes runs `lifeos sync oura` to pull fresh Oura data
2. Hermes runs `lifeos brief --format text` to generate the brief
3. Hermes sends the brief to Perttu via the Discord message tool

Cron ID: `lifeos-morning-brief`. This is the simplest possible architecture: cron → Hermes → Discord.

### Conversational Capture (Sprint 2)

```
Perttu (Discord): "energy is like a 3 today, bad sleep"
    → Hermes parses intent
    → lifeos log energy 3 --note "bad sleep"
    → Hermes confirms: "Logged ✓. 3 days below 4 this week — want me to check what's driving it?"
    → If yes: lifeos pattern --days 7 --format text → Hermes delivers
```

Hermes owns the conversation. LifeOS owns the data. Clean boundary. LifeOS never listens on Discord.

---

## Architecture

### What stays (untouched)
- SQLite database and all models
- AI engine (`LifeOSAI`, `PatternAnalyzer`, `EnergyPredictor`)
- FastAPI backend and all routers
- Oura and Google Calendar integrations
- LiteLLM abstraction and cost tracking
- Personalization layer
- Web dashboard (functional, no new investment)

### What's new
- `cli/__init__.py`
- `cli/main.py` — Click entry point, command registration
- `cli/formatters.py` — JSON and text output formatters
- `scripts/morning_brief.sh` — wrapper for cron
- Entry point in `pyproject.toml` or `setup.cfg`: `lifeos = cli.main:cli`

### What's cut from scope
- Onboarding flow (Perttu is the only user, `.env` is config)
- Telegram capture superseded by Discord-via-Hermes
- E-ink display, ElevenLabs TTS, achievements — future, not Phase 1

---

## Requirements

### Functional

| ID | Requirement | Acceptance Test |
|----|-------------|-----------------|
| F1 | `lifeos brief` generates a daily brief using sleep, calendar, and historical data | Brief contains sleep score, calendar summary, and ≥1 actionable suggestion |
| F2 | `lifeos brief --format json` returns valid parseable JSON | `lifeos brief --format json \| python3 -c "import sys,json; json.load(sys.stdin)"` exits 0 |
| F3 | `lifeos sync oura` fetches and stores new Oura data | New records appear in DB; command prints "Synced N records" to stdout |
| F4 | CLI works without FastAPI server running | Kill FastAPI, run `lifeos brief` — succeeds |
| F5 | Morning cron runs at 7am Helsinki time, delivers brief to Discord | Discord message received before 7:05am |
| F6 | EnergyPredictor weights persisted across restarts | Train on Day 1, restart, `lifeos brief` on Day 2 uses trained model |

### Non-Functional

| ID | Requirement | Test |
|----|-------------|------|
| NF1 | `lifeos` binary installed via `pip install -e .` | `which lifeos` resolves after install |
| NF2 | Only `click` added to requirements.txt | Diff before/after |
| NF3 | Errors to stderr, never to stdout | `lifeos sync oura 2>/dev/null` prints nothing if no error |
| NF4 | DB path configurable via `LIFEOS_DB_PATH` env var | Set var, verify correct DB |

---

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|-------------|
| Morning brief delivery rate | ≥6/7 days/week | Count Discord messages per week |
| CLI invocations by Hermes | ≥10/day within 30 days | Cron/shell logs |
| `lifeos brief` cold-start time | <5s (non-AI) + AI latency | `time lifeos brief` |
| Error rate | <1% | stderr output count / total invocations |

---

## Risks & Dependencies

| Risk | Impact | Mitigation |
|------|--------|------------|
| EnergyPredictor state lost per cold start | Degraded brief quality (predictor never learns) | **Fix before Sprint 1 ships** — persist model weights to DB |
| CLI and API routers diverge over time | Two interfaces with subtly different behavior | Strict rule: zero logic in CLI layer. All logic in service layer. PR check. |
| Cron not configured = G1 never ships | Sprint 1 worthless | Cron entry is a **Sprint 1 acceptance criterion**, not a follow-on |
| Morning brief AI latency >30s | Perttu gets brief late | Cache: run sync at 6:30am, brief generation at 6:45am, delivery at 7:00am |
| DISCORD_WEBHOOK_URL or OURA_TOKEN not in `.env` | Nothing works | Verify in Sprint 1 onboarding checklist |

**Dependencies:**
- `OURA_TOKEN` in `.env` (Oura Personal Access Token)
- `DISCORD_WEBHOOK_URL` in `.env` or Hermes's relay integration
- OpenClaw cron access (for morning routine scheduling)
- `click` added to `requirements.txt`

---

## Sprint Plan

### Sprint 1: Wire it (target: 2 days)
1. Fix EnergyPredictor persistence (existing bug pol-69ed)
2. Add `click` to requirements.txt
3. Build `cli/main.py` with `brief` and `sync` commands
4. Build `cli/formatters.py` (json + text formatters)
5. Add `lifeos` entry point to setup
6. Configure OpenClaw cron for 7am routine
7. Verify OURA_TOKEN + DISCORD_WEBHOOK_URL in .env
8. **Acceptance:** Brief delivered to Discord for 3 consecutive days

### Sprint 2: Capture (only after Sprint 1 stable for 2 weeks)
- `lifeos log energy|mood|note`
- `lifeos status`

### Sprint 3: Intelligence (only after Sprint 2 in use)
- `lifeos goal` commands
- `lifeos pattern`
- `lifeos weekly`
