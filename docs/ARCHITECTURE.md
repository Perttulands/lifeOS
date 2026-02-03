# LifeOS Architecture

This document describes the system architecture of LifeOS, an AI-powered personal operating system.

---

## Table of Contents

- [Overview](#overview)
- [System Architecture](#system-architecture)
- [Component Details](#component-details)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [AI Engine](#ai-engine)
- [Integration Patterns](#integration-patterns)
- [Background Jobs](#background-jobs)
- [Frontend Architecture](#frontend-architecture)
- [Security Considerations](#security-considerations)
- [Deployment](#deployment)

---

## Overview

LifeOS follows a **local-first** architecture designed for single-user deployment. Key principles:

1. **Local-first**: All data stored locally in SQLite
2. **Model-agnostic AI**: LiteLLM abstraction supports multiple providers
3. **Zero build frontend**: Vanilla HTML/CSS/JS, no bundler required
4. **Passive capture**: Data flows in automatically, insights flow out
5. **Privacy-first**: No cloud telemetry, no data sharing

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              External Services                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│   │  Oura Ring   │   │   Google     │   │   OpenAI/    │   │  Telegram/   │   │
│   │    API v2    │   │  Calendar    │   │  Anthropic   │   │   Discord    │   │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│          │                  │                  │                  │            │
└──────────┼──────────────────┼──────────────────┼──────────────────┼────────────┘
           │                  │                  │                  │
           ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            Integration Layer                                     │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   │
│   │ OuraClient   │   │ CalendarSync │   │   LiteLLM    │   │ NotifyService│   │
│   │ OuraSyncSvc  │   │ CalendarSvc  │   │   LifeOSAI   │   │ TG/Discord   │   │
│   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   └──────┬───────┘   │
│          │                  │                  │                  │            │
│   src/integrations/   src/integrations/   src/ai.py        src/integrations/   │
│   oura.py             calendar.py                          notify.py           │
│                                                                                  │
└──────────┬──────────────────┬──────────────────┬──────────────────┬────────────┘
           │                  │                  │                  │
           ▼                  ▼                  ▼                  ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              Service Layer                                       │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐     │
│   │  InsightsService   │   │  PatternAnalyzer   │   │ PersonalizationSvc │     │
│   │                    │   │                    │   │                    │     │
│   │ • Daily briefs     │   │ • Correlations     │   │ • Learn prefs      │     │
│   │ • Weekly reviews   │   │ • Trends           │   │ • Build prompts    │     │
│   │ • Energy predict   │   │ • Day-of-week      │   │ • Track feedback   │     │
│   │ • Pattern detect   │   │ • Sliding window   │   │ • Decay weights    │     │
│   └─────────┬──────────┘   └─────────┬──────────┘   └─────────┬──────────┘     │
│             │                        │                        │                 │
│   src/insights_service.py    src/pattern_analyzer.py   src/personalization.py  │
│                                                                                  │
│   ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐     │
│   │  EnergyPredictor   │   │   CaptureService   │   │   TokenTracker     │     │
│   │                    │   │                    │   │                    │     │
│   │ • ML regression    │   │ • Text analysis    │   │ • Log usage        │     │
│   │ • LLM comparison   │   │ • Auto-categorize  │   │ • Cost reports     │     │
│   │ • Accuracy track   │   │ • Task/Note/Log    │   │ • Model pricing    │     │
│   └────────────────────┘   └────────────────────┘   └────────────────────┘     │
│                                                                                  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                              API Layer (FastAPI)                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   src/api.py - Main application                                                  │
│                                                                                  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│   │  health  │ │ insights │ │   data   │ │   oura   │ │ calendar │            │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │
│   │  notify  │ │ capture  │ │  voice   │ │ settings │ │  backup  │            │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘            │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                          │
│   │  stats   │ │ prefs    │ │ backfill │ │onboarding│                          │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘                          │
│                                                                                  │
│   src/routers/*.py (15 router modules)                                          │
│                                                                                  │
└──────────────────────────────────────┬──────────────────────────────────────────┘
                                       │
              ┌────────────────────────┼────────────────────────┐
              │                        │                        │
              ▼                        ▼                        ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│      SQLite DB       │  │    Background Jobs   │  │    Web Frontend      │
│                      │  │                      │  │                      │
│   lifeos.db          │  │   src/jobs/          │  │   ui/                │
│                      │  │   • daily_brief.py   │  │   • index.html       │
│   Tables:            │  │   • weekly_review.py │  │   • css/             │
│   • users            │  │   • oura_sync.py     │  │   • js/              │
│   • data_points      │  │   • calendar_sync.py │  │                      │
│   • insights         │  │   • pattern_detect.py│  │   Vanilla JS SPA     │
│   • patterns         │  │   • backup.py        │  │   No build step      │
│   • journal_entries  │  │                      │  │                      │
│   • tasks            │  │   Cron scheduled     │  │                      │
│   • notes            │  │                      │  │                      │
│   • voice_notes      │  │                      │  │                      │
│   • oauth_tokens     │  │                      │  │                      │
│   • calendar_events  │  │                      │  │                      │
│   • user_preferences │  │                      │  │                      │
│   • insight_feedback │  │                      │  │                      │
│   • token_usage      │  │                      │  │                      │
│   • goals            │  │                      │  │                      │
│                      │  │                      │  │                      │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘
```

---

## Component Details

### Core Modules

| Module | File | Purpose |
|--------|------|---------|
| **API** | `src/api.py` | FastAPI application, router mounting, CORS, static files |
| **Config** | `src/config.py` | Pydantic settings from environment variables |
| **Database** | `src/database.py` | SQLAlchemy engine, session factory, initialization |
| **Models** | `src/models.py` | SQLAlchemy ORM models for all tables |
| **Schemas** | `src/schemas.py` | Pydantic models for API request/response validation |
| **Errors** | `src/errors.py` | Custom exceptions with helpful error messages |
| **Health** | `src/health.py` | System health monitoring, error tracking |

### Service Layer

| Service | File | Purpose |
|---------|------|---------|
| **InsightsService** | `src/insights_service.py` | Orchestrates brief/pattern generation |
| **LifeOSAI** | `src/ai.py` | LLM calls, prompt management, personalization |
| **PatternAnalyzer** | `src/pattern_analyzer.py` | Statistical analysis (scipy-based) |
| **EnergyPredictor** | `src/energy_predictor.py` | ML regression model for energy |
| **PersonalizationService** | `src/personalization.py` | User preference learning |
| **TokenTracker** | `src/token_tracker.py` | AI usage and cost tracking |

### Integration Layer

| Integration | File | Purpose |
|-------------|------|---------|
| **OuraClient** | `src/integrations/oura.py` | Oura API v2 client |
| **CalendarService** | `src/integrations/calendar.py` | Google Calendar OAuth2 |
| **NotificationService** | `src/integrations/notify.py` | Telegram/Discord delivery |
| **CaptureService** | `src/integrations/capture.py` | AI text categorization |
| **VoiceService** | `src/integrations/voice.py` | Voice note processing |
| **WhisperService** | `src/integrations/whisper.py` | OpenAI Whisper transcription |

---

## Data Flow

### Morning Brief Generation

```
1. Cron triggers daily_brief.py at 7 AM
                    │
                    ▼
2. InsightsService.generate_daily_brief(date)
                    │
   ┌────────────────┼────────────────┐
   ▼                ▼                ▼
3. Get sleep data   Get calendar     Get preferences
   from DataPoint   from CalendarEvent from UserPreference
                    │
                    ▼
4. Build DayContext + history (7 days)
                    │
                    ▼
5. PersonalizationService.build_personalization_prompt()
                    │
                    ▼
6. LifeOSAI.generate_daily_brief()
   ├── Build personalized system prompt
   ├── Format user prompt with context
   ├── Call LiteLLM
   └── Parse response
                    │
                    ▼
7. Store Insight in database
                    │
                    ▼
8. NotificationService.send_telegram/discord()
```

### Pattern Detection Pipeline

```
1. POST /api/insights/detect-patterns
                    │
                    ▼
2. InsightsService.detect_patterns()
                    │
   ┌────────────────┴────────────────┐
   │                                  │
   ▼                                  ▼
3. PatternAnalyzer                   (optional)
   ├── _find_correlations()          LifeOSAI.analyze_patterns()
   ├── _find_trends()                └── LLM-based pattern discovery
   ├── _find_day_patterns()
   └── analyze_sliding_window()
                    │
                    ▼
4. Deduplicate and merge results
                    │
                    ▼
5. Deactivate old patterns
                    │
                    ▼
6. Store new Pattern records
```

### Voice Note Processing

```
1. POST /api/voice/upload (multipart file)
                    │
                    ▼
2. Save audio file to uploads/
                    │
                    ▼
3. VoiceService.process()
   ├── Extract metadata (duration, format)
   └── Create VoiceNote record
                    │
                    ▼
4. WhisperService.transcribe()
   ├── Call OpenAI Whisper API
   └── Update VoiceNote.transcription
                    │
                    ▼
5. CaptureService.categorize()
   ├── AI determines type: task/note/energy
   └── Create Task, Note, or JournalEntry
                    │
                    ▼
6. Update VoiceNote with categorization result
```

---

## Database Schema

### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     users       │       │   data_points   │       │    insights     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ name            │◄──────│ user_id (FK)    │       │ user_id (FK)    │──────►
│ timezone        │       │ source          │       │ type            │
│ preferences     │       │ type            │       │ date            │
│ created_at      │       │ date            │       │ content         │
│ updated_at      │       │ value           │       │ context (JSON)  │
└─────────────────┘       │ metadata (JSON) │       │ confidence      │
                          │ timestamp       │       │ acted_on        │
                          └─────────────────┘       │ created_at      │
                                                    └─────────────────┘
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    patterns     │       │ journal_entries │       │     tasks       │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ user_id (FK)    │       │ user_id (FK)    │       │ user_id (FK)    │
│ name            │       │ date            │       │ title           │
│ description     │       │ time            │       │ description     │
│ pattern_type    │       │ energy          │       │ status          │
│ variables (JSON)│       │ mood            │       │ priority        │
│ strength        │       │ notes           │       │ due_date        │
│ confidence      │       │ tags (JSON)     │       │ tags (JSON)     │
│ sample_size     │       │ created_at      │       │ source          │
│ actionable      │       └─────────────────┘       │ raw_input       │
│ active          │                                 │ metadata (JSON) │
│ discovered_at   │                                 │ created_at      │
└─────────────────┘                                 └─────────────────┘

┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│     notes       │       │  voice_notes    │       │  oauth_tokens   │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ user_id (FK)    │       │ user_id (FK)    │       │ user_id (FK)    │
│ content         │       │ filename        │       │ provider        │
│ title           │       │ file_path       │       │ access_token    │
│ tags (JSON)     │       │ file_size       │       │ refresh_token   │
│ source          │       │ duration_seconds│       │ token_type      │
│ raw_input       │       │ mime_type       │       │ expires_at      │
│ metadata (JSON) │       │ transcription   │       │ scope           │
│ created_at      │       │ trans_status    │       │ metadata (JSON) │
└─────────────────┘       │ trans_language  │       │ created_at      │
                          │ categorized_type│       │ updated_at      │
                          │ categorized_id  │       └─────────────────┘
                          │ source          │
                          │ created_at      │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ calendar_events │       │user_preferences │       │insight_feedback │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ user_id (FK)    │       │ user_id (FK)    │       │ user_id (FK)    │
│ event_id        │       │ category        │       │ insight_id (FK) │
│ calendar_id     │       │ key             │       │ feedback_type   │
│ summary         │       │ value (JSON)    │       │ context (JSON)  │
│ description     │       │ weight          │       │ created_at      │
│ location        │       │ source          │       └─────────────────┘
│ start_time      │       │ evidence_count  │
│ end_time        │       │ last_reinforced │       ┌─────────────────┐
│ all_day         │       │ created_at      │       │  token_usage    │
│ status          │       │ updated_at      │       ├─────────────────┤
│ organizer       │       └─────────────────┘       │ id (PK)         │
│ attendees_count │                                 │ timestamp       │
│ is_recurring    │       ┌─────────────────┐       │ feature         │
│ recurring_id    │       │     goals       │       │ model           │
│ metadata (JSON) │       ├─────────────────┤       │ input_tokens    │
│ synced_at       │       │ id (PK)         │       │ output_tokens   │
└─────────────────┘       │ user_id (FK)    │       │ total_tokens    │
                          │ title           │       │ cost_usd        │
                          │ description     │       └─────────────────┘
                          │ target_date     │
                          │ status          │
                          │ progress        │
                          │ metadata (JSON) │
                          │ created_at      │
                          │ updated_at      │
                          └─────────────────┘
```

### Key Indexes

```sql
-- data_points
CREATE INDEX idx_datapoint_date_type ON data_points(date, type);
CREATE INDEX idx_datapoint_source ON data_points(source);

-- insights
CREATE INDEX idx_insight_date_type ON insights(date, type);

-- patterns
CREATE INDEX idx_pattern_type ON patterns(pattern_type);

-- journal_entries
CREATE INDEX idx_journal_date ON journal_entries(date);

-- tasks
CREATE INDEX idx_task_status ON tasks(status);
CREATE INDEX idx_task_created ON tasks(created_at);

-- notes
CREATE INDEX idx_note_created ON notes(created_at);

-- oauth_tokens
CREATE INDEX idx_oauth_provider_user ON oauth_tokens(provider, user_id);

-- calendar_events
CREATE INDEX idx_calendar_event_id ON calendar_events(event_id);
CREATE INDEX idx_calendar_start_time ON calendar_events(start_time);
CREATE INDEX idx_calendar_date ON calendar_events(start_time, end_time);

-- user_preferences
CREATE INDEX idx_preference_user_category ON user_preferences(user_id, category);
CREATE INDEX idx_preference_key ON user_preferences(key);

-- insight_feedback
CREATE INDEX idx_feedback_insight ON insight_feedback(insight_id);
CREATE INDEX idx_feedback_type ON insight_feedback(feedback_type);

-- voice_notes
CREATE INDEX idx_voice_note_status ON voice_notes(transcription_status);
CREATE INDEX idx_voice_note_created ON voice_notes(created_at);

-- token_usage
CREATE INDEX idx_token_timestamp ON token_usage(timestamp);
CREATE INDEX idx_token_feature ON token_usage(feature);
```

---

## AI Engine

### Philosophy

The AI engine follows these principles from the PRD:

1. **LLM as Translator, Not Oracle**: Pre-compute insights, use LLM for language
2. **Prompts Are Product**: Each AI function has a distinct persona
3. **Context Beats Capability**: Rich context > powerful model
4. **Structured In, Structured Out**: Typed boundaries around LLM calls
5. **Graceful Degradation**: Always have fallbacks
6. **Model-Agnostic**: LiteLLM abstraction, no vendor lock-in
7. **Cost-Aware**: Tiered model selection based on task
8. **Memory, Not Magic**: Cite evidence, show confidence

### Prompt Architecture

```python
# System prompts are persona-driven
SYSTEM_PROMPT_BRIEF = """You are LifeOS, a personal AI assistant...
Focus on:
1. Sleep quality assessment
2. Energy prediction
3. One actionable suggestion
Keep it under 150 words. Be specific with numbers."""

SYSTEM_PROMPT_PATTERN = """You are LifeOS pattern analyzer...
Good patterns are: specific, actionable, based on data."""

SYSTEM_PROMPT_WEEKLY = """You are LifeOS weekly reviewer...
Tone: Supportive coach, not demanding boss."""
```

### Personalization Pipeline

```
1. User interacts with insight (helpful/not_helpful/acted_on)
                    │
                    ▼
2. PersonalizationService.record_feedback()
   ├── Store InsightFeedback
   └── _learn_from_feedback()
       ├── Analyze insight content
       ├── Reinforce focus areas
       └── Adjust length preferences
                    │
                    ▼
3. On next brief generation:
   PersonalizationService.build_personalization_prompt()
   ├── Get tone preference
   ├── Get focus areas
   ├── Get length preference
   ├── Get active patterns
   └── Check schedule preferences
                    │
                    ▼
4. Inject into system prompt:
   LifeOSAI.build_personalized_brief_prompt()
```

### Token Cost Tracking

```python
# Model pricing (per 1M tokens)
MODEL_PRICING = {
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
}

# Every AI call logs usage
TokenUsage(
    feature="daily_brief",
    model="gpt-4o-mini",
    input_tokens=500,
    output_tokens=200,
    cost_usd=0.00019
)
```

---

## Integration Patterns

### Oura Integration

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Oura Cloud  │────▶│ OuraClient  │────▶│  DataPoint  │
│    API      │     │             │     │   (sleep)   │
│             │     │ • PAT auth  │     │  (activity) │
│ /v2/user... │     │ • OAuth2    │     │ (readiness) │
└─────────────┘     │ • Refresh   │     └─────────────┘
                    └─────────────┘
```

**Data Types Synced:**
- `daily_sleep`: Duration, deep/REM/light, efficiency, score
- `daily_activity`: Steps, calories, activity levels
- `daily_readiness`: HRV, temperature, recovery

### Google Calendar Integration

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Google Cal  │────▶│ CalendarSvc │────▶│CalendarEvent│
│    API      │     │             │     │             │
│             │     │ • OAuth2    │     │ • summary   │
│ events.list │     │ • Refresh   │     │ • times     │
│ events.get  │     │ • Sync      │     │ • attendees │
└─────────────┘     └─────────────┘     └─────────────┘
```

**OAuth2 Flow:**
1. User visits `/api/calendar/auth`
2. Redirect to Google consent screen
3. Callback to `/api/calendar/callback`
4. Store tokens in `oauth_tokens` table
5. Auto-refresh before expiry

### Notification Integration

```
┌─────────────────────────────────────────────┐
│             NotificationService              │
├─────────────────────────────────────────────┤
│                                              │
│  ┌──────────────┐    ┌──────────────┐       │
│  │   Telegram   │    │   Discord    │       │
│  │              │    │              │       │
│  │ Bot API      │    │ Webhook      │       │
│  │ sendMessage  │    │ POST         │       │
│  └──────────────┘    └──────────────┘       │
│                                              │
│  Features:                                   │
│  • Quiet hours (23:00-08:00)                │
│  • Markdown formatting                       │
│  • Chunked messages (>4096 chars)           │
│  • Retry with exponential backoff           │
│                                              │
└─────────────────────────────────────────────┘
```

---

## Background Jobs

### Job Schedule

| Job | Schedule | Description |
|-----|----------|-------------|
| `daily_brief.py` | 7:00 AM | Generate and deliver morning brief |
| `weekly_review.py` | Sunday 7:00 PM | Generate and deliver weekly review |
| `oura_sync.py` | Every 6 hours | Sync latest Oura data |
| `calendar_sync.py` | Every 2 hours | Sync calendar events |
| `pattern_detection.py` | Daily 3:00 AM | Run pattern analysis |
| `backup.py` | Daily 2:00 AM | Create database backup |

### Cron Configuration Example

```cron
# LifeOS cron jobs
0 7 * * * cd /app && python -m src.jobs.daily_brief
0 19 * * 0 cd /app && python -m src.jobs.weekly_review
0 */6 * * * cd /app && python -m src.jobs.oura_sync
0 */2 * * * cd /app && python -m src.jobs.calendar_sync
0 3 * * * cd /app && python -m src.jobs.pattern_detection
0 2 * * * cd /app && python -m src.jobs.backup
```

---

## Frontend Architecture

### Structure

```
ui/
├── index.html          # Single-page application entry
├── css/
│   ├── main.css        # Core styles
│   ├── dashboard.css   # Dashboard components
│   ├── cards.css       # Card layouts
│   └── themes.css      # Dark/light themes
└── js/
    ├── app.js          # Application entry
    ├── api.js          # API client
    ├── components/
    │   ├── brief.js    # Morning brief component
    │   ├── charts.js   # Trend visualizations
    │   ├── capture.js  # Quick capture
    │   └── settings.js # Settings panel
    └── utils/
        ├── date.js     # Date formatting
        └── format.js   # Number formatting
```

### Design Principles

1. **No Build Step**: Pure vanilla JS, load directly in browser
2. **Component-Based**: Modular JS files, not a framework
3. **API-First**: All data via REST API calls
4. **Dark Theme**: Warm dark colors, easy on eyes
5. **Mobile-Responsive**: Works on phone screens

### SPA Routing

FastAPI serves `index.html` for all non-API routes:

```python
@app.get("/{path:path}")
async def serve_static(path: str):
    file_path = _ui_dir / path
    if file_path.exists() and file_path.is_file():
        return FileResponse(str(file_path))
    return FileResponse(str(_ui_dir / "index.html"))  # SPA fallback
```

---

## Security Considerations

### Local-First Security Model

LifeOS is designed for local, single-user deployment:

1. **No Authentication**: Single user, no login required
2. **No Network Exposure**: Run on localhost by default
3. **No Telemetry**: Zero data sent to external services (except configured APIs)
4. **Encrypted Storage**: Use OS-level encryption for database file

### API Security

If exposing externally:

1. **Add Authentication**: Implement API keys or OAuth
2. **Use HTTPS**: Put behind reverse proxy (nginx, Caddy)
3. **Rate Limiting**: Add request throttling
4. **Input Validation**: Pydantic handles this

### Secrets Management

```bash
# .env file (never commit!)
OURA_TOKEN=xxx
OPENAI_API_KEY=sk-xxx
TELEGRAM_BOT_TOKEN=123:ABC
GOOGLE_CLIENT_SECRET=xxx
```

---

## Deployment

### Local Development

```bash
# Setup
./setup.sh
source .venv/bin/activate

# Run
python -m uvicorn src.api:app --reload --port 8080
```

### Docker

```yaml
# docker-compose.yml
version: '3.8'
services:
  lifeos:
    build: .
    ports:
      - "8080:8080"
    volumes:
      - ./lifeos.db:/app/lifeos.db
      - ./backups:/app/backups
    env_file:
      - .env
```

### Production Checklist

- [ ] Configure all API keys in `.env`
- [ ] Set up reverse proxy (nginx/Caddy) with HTTPS
- [ ] Enable database backups (automated or manual)
- [ ] Configure cron jobs for background tasks
- [ ] Set appropriate quiet hours for notifications
- [ ] Test Oura sync with backfill
- [ ] Verify notification delivery

---

## Performance Considerations

### Database

- SQLite handles single-user workloads well
- Indexes on frequently queried columns
- WAL mode enabled for concurrent reads
- Consider vacuuming periodically

### API

- FastAPI async handlers
- Lazy initialization of services
- Connection pooling via SQLAlchemy
- Response caching for static data

### AI

- Default to cheapest effective model (gpt-4o-mini)
- Cache daily briefs (regenerate only on request)
- Batch pattern detection (run overnight)
- Track token usage for cost awareness

---

## Extending LifeOS

### Adding a New Integration

1. Create `src/integrations/myservice.py`
2. Implement client class with auth handling
3. Create data transformation functions
4. Add to `src/routers/myservice.py`
5. Register router in `src/api.py`
6. Add config to `src/config.py`
7. Document in API.md

### Adding a New Insight Type

1. Add prompt constant to `src/ai.py`
2. Implement generation method in `LifeOSAI`
3. Add storage logic to `InsightsService`
4. Create API endpoint in `src/routers/insights.py`
5. Update background job if needed

### Adding a New Data Source

1. Define data model in `src/models.py`
2. Create Pydantic schema in `src/schemas.py`
3. Implement sync service in `src/integrations/`
4. Add router endpoints
5. Update pattern analyzer if relevant
