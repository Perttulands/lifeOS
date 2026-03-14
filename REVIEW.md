# LifeOS — Deep Review
*Reviewed by Hermes, 2026-03-13*

---

## Summary

**LifeOS is further along than its own ROADMAP admits.** The gap between what ROADMAP.md says is done and what's actually in the codebase is significant — almost everything listed as a TODO is already implemented. The code quality is high, the architecture is coherent, and the PRD philosophy is actually followed in implementation. This is rare.

What needs attention is not the code itself but the housekeeping around it: stale docs, a few technical debts worth naming, and clarity on what Phase 2/3 actually looks like from here.

---

## What's Built (Reality vs ROADMAP)

ROADMAP.md lists these as NOT done. They are all done:

| Feature | ROADMAP says | Reality |
|---------|-------------|---------|
| Oura API adapter | ❌ TODO | ✅ `src/integrations/oura.py` — 623 lines, OAuth2 + PAT, sync all 3 data types |
| Google Calendar adapter | ❌ TODO | ✅ `src/integrations/calendar.py` — 742 lines, full OAuth2 flow |
| Historical data backfill | ❌ TODO | ✅ `src/backfill.py` — 469 lines |
| Real pattern detection | ❌ TODO | ✅ `src/pattern_analyzer.py` — Pearson/Spearman correlations, trend detection, day-of-week analysis |
| Energy prediction ML | ❌ TODO | ✅ `src/energy_predictor.py` — linear regression with 6 features, ML vs LLM comparator |
| Personalization layer | ❌ TODO | ✅ `src/personalization.py` — preference learning, weight decay, feedback loops |
| Token cost tracking | ❌ TODO | ✅ `src/token_tracker.py` + model pricing table |
| Morning brief delivery | ❌ TODO | ✅ `src/integrations/notify.py` — 928 lines, Telegram + Discord |
| Voice notes | ❌ TODO | ✅ `src/integrations/voice.py` + `whisper.py` + full router |
| Quick capture (Telegram/Discord) | ❌ TODO | ✅ `src/integrations/capture.py` |
| Docker deployment | ❌ TODO | ✅ `Dockerfile` + `docker-compose.yml` + `docker-compose.production.yml` |
| Backup/restore | ❌ TODO | ✅ `src/jobs/backup.py` + `src/routers/backup.py` |
| Dashboard wired to real API | ❌ TODO | ✅ `ui/js/api.js` — API client, all endpoints |
| Goal tracking | ❌ TODO | ✅ `src/integrations/goals.py` + AI milestone breakdown |
| Onboarding | ❌ TODO | ✅ `src/routers/onboarding.py` — 476 lines |

**Action: ROADMAP.md needs a complete rewrite.** It's actively misleading.

---

## Architecture Assessment

### What's excellent

**Structural separation is clean.** `routers/` only handle HTTP. `*_service.py` layers contain business logic. `integrations/` are isolated adapters. `jobs/` are cron runners. The dependency graph is sensible.

**PRD philosophy is implemented.** The 8 AI principles from docs/PRD.md are not aspirational — they're in the code:
- LLM as translator (deltas pre-computed before prompts ✅)
- Structured In/Out (`InsightResult`, `PatternResult` dataclasses ✅)
- Graceful degradation (every AI call has fallback ✅)
- Model-agnostic via LiteLLM ✅
- Cost tracking per feature ✅

**Pattern detection is real math.** `pattern_analyzer.py` runs actual Pearson/Spearman correlations with p-values, linear regression for trends, and ANOVA for day-of-week patterns. Not just LLM prompting.

**Error handling is thoughtful.** `errors.py` has a `LifeOSException` system with human-readable messages, fix suggestions, and docs links. Good UX discipline.

**Personalization has real mechanics.** Weight decay (0.95/week), explicit vs inferred preference separation, evidence counting. It will actually learn over time.

### What needs attention

**1. CORS is broken in production**
```python
# api.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],    # ← wildcard
    allow_credentials=True, # ← browsers reject wildcard + credentials
    ...
)
```
`allow_origins=["*"]` with `allow_credentials=True` is invalid — browsers will block credentialed requests. Since this is local-first, the real fix is probably `allow_origins=["http://localhost:8080"]` or origin from config.

**2. `datetime.utcnow()` is deprecated**
Used throughout `models.py`, `token_tracker.py`, and others. Python 3.12 deprecates it. Should be `datetime.now(timezone.utc)`. Not breaking yet, but will generate warnings.

**3. Energy predictor / Prediction comparator state is ephemeral**
`_predictor` and `_comparator` singletons live in-memory only. Model weights trained from user data are lost on every restart. The predictor will retrain from scratch each time. The comparator loses all recorded predictions. These need persistence (serialize to DB or file).

**4. OAuth tokens stored plaintext**
`OAuthToken` model stores `access_token` and `refresh_token` as `Text` in SQLite. For a personal local app this is acceptable risk, but worth noting — anyone with file access owns the tokens.

**5. No schema migrations**
`init_db()` calls `create_all()`. Adding a column later means manual schema surgery or dropping the DB. Alembic would solve this. Not urgent for personal use, important if you ever migrate between versions.

**6. Bare `except:` in AI parsing**
`ai.py` `predict_energy()` and `analyze_patterns()` both have bare `except: pass` on JSON parsing. Should be at minimum `except (json.JSONDecodeError, ValueError):` to avoid silently swallowing unexpected errors.

**7. `@app.on_event("startup")` is deprecated**
FastAPI moved to lifespan context managers. Non-breaking but will show deprecation warnings on startup:
```python
# Old
@app.on_event("startup")
async def startup():
    init_db()

# New
from contextlib import asynccontextmanager
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield
app = FastAPI(lifespan=lifespan, ...)
```

**8. AI singleton has no thread safety**
```python
_ai_instance: Optional[LifeOSAI] = None

def get_ai() -> LifeOSAI:
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = LifeOSAI()
    return _ai_instance
```
FastAPI with multiple workers could race here. A lock or proper DI would fix it. Low risk with single uvicorn worker, relevant if you run gunicorn with multiple processes.

---

## Test Coverage

The test suite exists and is structured. What's covered:
- `tests/unit/test_ai.py` — AI engine
- `tests/unit/test_insights_service.py` — InsightsService
- `tests/unit/test_personalization_service.py` — PersonalizationService
- `tests/api/test_capture_routes.py`, `test_data_routes.py`, etc.
- `tests/test_energy_predictor.py`, `test_pattern_analyzer.py`, `test_oura.py`

**Gaps:** No tests for `voice`, `goals`, `calendar`, `notify` routers. The integrations with external APIs (Oura, Google Calendar, Telegram) appear untested or lightly mocked. This is expected for a personal project but worth knowing before you depend on them.

---

## What's Actually Missing (Phase 2/3 candidates)

Things genuinely not in the codebase yet, distinct from the stale ROADMAP:

1. **Model persistence for EnergyPredictor** — needs to serialize/load from DB
2. **Real Whisper integration** — `whisper.py` exists but may need credentials config validation
3. **Alembic migrations** — needed for any schema evolution
4. **E-ink / ambient display mode** — not started
5. **Achievements / streaks** — not started
6. **ElevenLabs TTS voice interface** — not started
7. **Context switching detection** — "entering deep work block" logic not implemented
8. **Tiered model selection** — PRD describes fast/balanced/deep model tiers; current code uses single `LITELLM_MODEL` setting

---

## Setup Notes

**Minimum viable `.env`** to run locally:
```
OURA_TOKEN=<your PAT from cloud.ouraring.com>
OPENAI_API_KEY=<or ANTHROPIC_API_KEY>
LITELLM_MODEL=gpt-4o-mini
USER_TIMEZONE=Europe/Helsinki
```

Optional but recommended: `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` for morning briefs.

**Run:**
```bash
cd /home/polis/projects/lifeOS
./setup.sh
source .venv/bin/activate
uvicorn src.api:app --port 8080 --reload
```

---

## Priority Action Items

| # | What | Impact | Effort |
|---|------|--------|--------|
| 1 | Rewrite ROADMAP.md to reflect reality | High (clarity) | Low |
| 2 | Fix CORS: replace `allow_origins=["*"]` + remove `allow_credentials=True` or lock to localhost | Medium (correctness) | Trivial |
| 3 | Persist EnergyPredictor model weights to DB | Medium (functionality) | Medium |
| 4 | Replace `datetime.utcnow()` with `datetime.now(timezone.utc)` | Low (future-proofing) | Low |
| 5 | Replace bare `except: pass` with specific exception types | Low (debuggability) | Low |
| 6 | Migrate `@app.on_event("startup")` to lifespan | Low (warnings) | Low |
| 7 | Add Alembic for schema migrations | Medium (maintainability) | Medium |

---

## Overall Verdict

**This is production-quality personal software.** The architecture is clean, the AI philosophy is actually implemented (not just in the doc), and the feature set is genuinely impressive for what appears to be a builder-sprint output. The data model is thoughtful, the error handling is user-friendly, and the statistical pattern detection is real math.

The main risk is the stale ROADMAP creating confusion about project state. Fix that first.

The bigger opportunity: the energy predictor trains on each restart but never persists its weights. Once you have a few weeks of real data, persistence will matter — the model will actually become personalized over time.

Ready to wire to real data and run.

---

*Review complete. Issues filed in beads.*
