# LifeOS API Reference

Complete REST API documentation for LifeOS. All endpoints are available at `http://localhost:8080/api/`.

> **Interactive Docs**: Visit `/docs` (Swagger UI) or `/redoc` (ReDoc) for interactive API exploration.

---

## Table of Contents

- [Authentication](#authentication)
- [Health & Status](#health--status)
- [Insights](#insights)
- [Data & Journal](#data--journal)
- [Oura Integration](#oura-integration)
- [Google Calendar](#google-calendar)
- [Voice Notes](#voice-notes)
- [Capture](#capture)
- [Notifications](#notifications)
- [Preferences](#preferences)
- [Statistics](#statistics)
- [Backup & Restore](#backup--restore)
- [Settings](#settings)
- [Onboarding](#onboarding)
- [Error Handling](#error-handling)

---

## Authentication

LifeOS is designed for single-user, local deployment. No API authentication is required by default.

For external integrations, API keys are configured via environment variables:

| Integration | Environment Variable |
|-------------|---------------------|
| Oura | `OURA_TOKEN` |
| OpenAI/LiteLLM | `OPENAI_API_KEY` or `LITELLM_API_KEY` |
| Google Calendar | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Discord | `DISCORD_WEBHOOK_URL` |

---

## Health & Status

### GET /api/health

Basic health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "timestamp": "2026-02-03T12:00:00Z"
}
```

### GET /api/health/detailed

Detailed health report with service status.

**Response:**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "uptime_seconds": 3600.5,
  "started_at": "2026-02-03T11:00:00Z",
  "timestamp": "2026-02-03T12:00:00Z",
  "services": {
    "database": {
      "name": "database",
      "status": "healthy",
      "message": "Connected",
      "latency_ms": 1.23
    },
    "oura": {
      "name": "oura",
      "status": "healthy",
      "message": "Configured"
    },
    "ai": {
      "name": "ai",
      "status": "healthy",
      "message": "Configured (gpt-4o-mini)"
    },
    "notifications": {
      "name": "notifications",
      "status": "healthy",
      "message": "Enabled: telegram, discord"
    }
  },
  "recent_errors": []
}
```

---

## Insights

### GET /api/insights/brief

Get the daily morning brief.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | today | Date in YYYY-MM-DD format |
| `generate` | boolean | false | Generate if not exists |

**Response:**
```json
{
  "id": 42,
  "type": "daily_brief",
  "date": "2026-02-03",
  "content": "Last night you got 7h 12m of sleep with 1h 45m deep sleep—that's 15% above your average...",
  "confidence": 0.85,
  "created_at": "2026-02-03T07:00:00Z"
}
```

### GET /api/insights/weekly

Get weekly review summary.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `week_ending` | string | today | Last day of week (YYYY-MM-DD) |
| `generate` | boolean | false | Generate if not exists |

**Response:**
```json
{
  "id": 15,
  "type": "weekly_review",
  "date": "2026-02-02",
  "content": "This week your average sleep was 7.2 hours...",
  "confidence": 0.75,
  "created_at": "2026-02-02T19:00:00Z"
}
```

### GET /api/insights/patterns

Get detected patterns from historical data.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `active_only` | boolean | true | Only return active patterns |

**Response:**
```json
[
  {
    "id": 1,
    "name": "Strong positive correlation: deep sleep → readiness score",
    "description": "Higher deep sleep correlates with higher readiness score (r=0.72, p=0.003, n=14)",
    "pattern_type": "correlation",
    "variables": ["deep_sleep", "readiness"],
    "strength": 0.72,
    "confidence": 0.95,
    "sample_size": 14,
    "actionable": true
  }
]
```

### POST /api/insights/detect-patterns

Run pattern detection analysis.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Days of history (7-90) |
| `force` | boolean | false | Force re-detection |

**Response:** Same as `GET /api/insights/patterns`

### POST /api/insights/generate

Force generate/regenerate an insight.

**Request Body:**
```json
{
  "insight_type": "daily_brief",
  "date": "2026-02-03"
}
```

**Valid insight_type values:** `daily_brief`, `weekly_review`, `energy_prediction`

**Response:** InsightResponse object

### GET /api/insights/recent

Get recent insights.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Days to look back (1-30) |
| `types` | string | null | Comma-separated types filter |

**Response:** Array of InsightResponse objects

### GET /api/predictions/energy

Get energy prediction for a date.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `date` | string | today | Date in YYYY-MM-DD format |

**Response:**
```json
{
  "overall": 7,
  "peak_hours": ["9:00-11:00", "15:00-16:00"],
  "low_hours": ["14:00-15:00"],
  "suggestion": "Your deep sleep was above average—capitalize on morning focus before your 2 PM meeting."
}
```

---

## Data & Journal

### POST /api/log

Quick log energy and mood.

**Request Body:**
```json
{
  "energy": 4,
  "mood": 4,
  "notes": "Feeling great after morning walk"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `energy` | integer | yes | Energy level 1-5 |
| `mood` | integer | no | Mood level 1-5 |
| `notes` | string | no | Optional notes |

**Response:**
```json
{
  "id": 123,
  "date": "2026-02-03",
  "time": "14:30",
  "energy": 4,
  "mood": 4,
  "notes": "Feeling great after morning walk",
  "created_at": "2026-02-03T14:30:00Z"
}
```

### GET /api/data

Query data points.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | string | 7 days ago | Start date (YYYY-MM-DD) |
| `end_date` | string | today | End date (YYYY-MM-DD) |
| `types` | string | null | Comma-separated types: sleep,activity,readiness,energy,mood |
| `source` | string | null | Filter by source: oura,manual,calendar |

**Response:**
```json
[
  {
    "id": 1,
    "source": "oura",
    "type": "sleep",
    "date": "2026-02-03",
    "value": 85.0,
    "metadata": {
      "total_sleep_duration": 26100,
      "deep_sleep_duration": 6300
    }
  }
]
```

### GET /api/data/summary

Get data summary for a date range.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | string | 7 days ago | Start date |
| `end_date` | string | today | End date |

**Response:**
```json
{
  "days": 7,
  "sleep": {
    "avg_score": 82.5,
    "avg_duration_hours": 7.2,
    "avg_deep_sleep_hours": 1.5
  },
  "readiness": {
    "avg_score": 78.0
  },
  "activity": {
    "avg_score": 65.0
  },
  "energy_logs": 5
}
```

### GET /api/journal

Get journal entries.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 7 | Days to look back |
| `limit` | integer | 50 | Max entries to return |

**Response:**
```json
[
  {
    "id": 1,
    "date": "2026-02-03",
    "time": "14:30",
    "energy": 4,
    "mood": 4,
    "notes": "Great day!",
    "tags": ["productive"],
    "created_at": "2026-02-03T14:30:00Z"
  }
]
```

---

## Oura Integration

### GET /api/oura/status

Check Oura integration status.

**Response:**
```json
{
  "configured": true,
  "base_url": "https://api.ouraring.com/v2"
}
```

### POST /api/oura/sync

Sync Oura data for a date range.

**Request Body:**
```json
{
  "start_date": "2026-02-01",
  "end_date": "2026-02-03"
}
```

**Response:**
```json
{
  "results": [
    {
      "success": true,
      "data_type": "sleep",
      "records_synced": 3,
      "date_range": ["2026-02-01", "2026-02-03"],
      "errors": []
    },
    {
      "success": true,
      "data_type": "activity",
      "records_synced": 3,
      "date_range": ["2026-02-01", "2026-02-03"],
      "errors": []
    },
    {
      "success": true,
      "data_type": "readiness",
      "records_synced": 3,
      "date_range": ["2026-02-01", "2026-02-03"],
      "errors": []
    }
  ],
  "total_synced": 9
}
```

### POST /api/oura/backfill

Backfill historical Oura data.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Days to backfill |

**Response:** Same as `/api/oura/sync`

---

## Google Calendar

### GET /api/calendar/status

Check Google Calendar integration status.

**Response:**
```json
{
  "configured": true,
  "connected": true,
  "last_sync": "2026-02-03T06:00:00Z",
  "calendars": [
    {"id": "primary", "name": "Main Calendar"}
  ]
}
```

### GET /api/calendar/auth

Get OAuth authorization URL.

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?...",
  "configured": true
}
```

### GET /api/calendar/callback

OAuth callback endpoint (handles redirect from Google).

### POST /api/calendar/sync

Sync calendar events.

**Request Body:**
```json
{
  "days_back": 7,
  "days_forward": 14,
  "calendar_id": "primary"
}
```

**Response:**
```json
{
  "status": "success",
  "events_synced": 25,
  "events_updated": 3,
  "events_deleted": 1,
  "date_range": ["2026-01-27", "2026-02-17"],
  "errors": []
}
```

### GET /api/calendar/events

Get synced calendar events.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `start_date` | string | today | Start date |
| `end_date` | string | today | End date |

**Response:**
```json
[
  {
    "id": 1,
    "event_id": "abc123",
    "summary": "Team Standup",
    "start_time": "2026-02-03T09:00:00Z",
    "end_time": "2026-02-03T09:30:00Z",
    "all_day": false,
    "status": "confirmed",
    "attendees_count": 5
  }
]
```

### GET /api/calendar/meetings/today

Get meeting stats for today.

**Response:**
```json
{
  "date": "2026-02-03",
  "meeting_count": 4,
  "total_hours": 3.5,
  "back_to_back_count": 1,
  "early_meetings": 0,
  "late_meetings": 1,
  "events": [...]
}
```

---

## Voice Notes

### GET /api/voice/status

Check voice note service status.

**Response:**
```json
{
  "whisper_configured": true,
  "supported_formats": ["mp3", "wav", "m4a", "webm", "ogg"],
  "max_file_size_mb": 25
}
```

### POST /api/voice/upload

Upload and process a voice note.

**Request:** Multipart form with `file` field.

```bash
curl -X POST http://localhost:8080/api/voice/upload \
  -F "file=@note.mp3"
```

**Response:**
```json
{
  "id": 1,
  "filename": "note.mp3",
  "transcription": "Remember to call mom about Sunday dinner",
  "transcription_status": "completed",
  "transcription_language": "en",
  "categorized_type": "task",
  "categorized_id": 15,
  "success": true,
  "message": "Voice note uploaded. Transcribed: 47 chars. Categorized as: task"
}
```

### GET /api/voice/notes

List voice notes.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 20 | Max notes to return |
| `status` | string | null | Filter by status: pending,completed,failed |

**Response:** Array of VoiceNoteResponse objects

### GET /api/voice/notes/{id}

Get a specific voice note.

**Response:** VoiceNoteResponse object

---

## Capture

### POST /api/capture

AI-powered text capture that auto-categorizes into task, note, or energy log.

**Request Body:**
```json
{
  "text": "Remember to buy groceries tomorrow",
  "source": "manual"
}
```

**Response:**
```json
{
  "type": "task",
  "success": true,
  "message": "Created task: Buy groceries tomorrow",
  "data": {
    "id": 42,
    "title": "Buy groceries tomorrow",
    "priority": "normal"
  }
}
```

### POST /api/capture/webhook

Webhook endpoint for external integrations (Telegram, Discord).

**Request Body:**
```json
{
  "text": "Energy level 4, feeling good",
  "source": "telegram",
  "user_id": "123456",
  "chat_id": "789",
  "message_id": "456"
}
```

**Response:** Same as `/api/capture`

### GET /api/capture/tasks

Get captured tasks.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `status` | string | null | Filter: pending,in_progress,completed |
| `limit` | integer | 50 | Max tasks to return |

**Response:** Array of TaskResponse objects

### GET /api/capture/notes

Get captured notes.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `limit` | integer | 50 | Max notes to return |

**Response:** Array of NoteResponse objects

---

## Notifications

### GET /api/notify/status

Check notification service status.

**Response:**
```json
{
  "telegram_enabled": true,
  "discord_enabled": true,
  "enabled_channels": ["telegram", "discord"]
}
```

### POST /api/brief/deliver

Deliver morning brief to notification channels.

**Request Body:**
```json
{
  "date": "2026-02-03",
  "channels": ["telegram", "discord"],
  "regenerate": false
}
```

**Response:**
```json
{
  "brief_date": "2026-02-03",
  "brief_content": "Good morning! Last night you got 7h 12m of sleep...",
  "notifications": [
    {
      "success": true,
      "channel": "telegram",
      "message_id": "123"
    },
    {
      "success": true,
      "channel": "discord",
      "message_id": null
    }
  ],
  "all_successful": true
}
```

### POST /api/weekly/deliver

Deliver weekly review to notification channels.

**Request Body:**
```json
{
  "week_ending": "2026-02-02",
  "channels": ["telegram"],
  "regenerate": false
}
```

**Response:**
```json
{
  "week_ending": "2026-02-02",
  "review_content": "This week your average sleep was 7.2 hours...",
  "patterns": [
    {"name": "Sleep-readiness correlation", "description": "..."}
  ],
  "avg_sleep_hours": 7.2,
  "avg_readiness": 78,
  "notifications": [...],
  "all_successful": true
}
```

### POST /api/notify/test

Send a test notification.

**Request Body:**
```json
{
  "channel": "telegram",
  "message": "Test notification from LifeOS"
}
```

**Response:**
```json
{
  "success": true,
  "channel": "telegram",
  "message_id": "456"
}
```

---

## Preferences

### GET /api/preferences

Get all user preferences.

**Response:**
```json
{
  "tone": {"style": "casual"},
  "focus": {"areas": ["sleep", "energy"], "show_comparisons": true},
  "content": {"insight_length": "medium"},
  "schedule": {"is_morning_person": true}
}
```

### GET /api/preferences/context

Get preference context for AI prompts.

**Response:**
```json
{
  "tone_style": "casual",
  "focus_areas": ["sleep", "energy"],
  "include_comparisons": true,
  "include_predictions": true,
  "preferred_insight_length": "medium",
  "active_patterns": ["Sleep-readiness correlation"]
}
```

### POST /api/preferences

Set a preference.

**Request Body:**
```json
{
  "category": "tone",
  "key": "style",
  "value": {"style": "professional"}
}
```

**Response:** PreferenceResponse object

### POST /api/preferences/feedback

Submit feedback on an insight.

**Request Body:**
```json
{
  "insight_id": 42,
  "feedback_type": "helpful",
  "context": {}
}
```

**Valid feedback_type values:** `helpful`, `not_helpful`, `acted_on`, `dismissed`

**Response:**
```json
{
  "id": 1,
  "insight_id": 42,
  "feedback_type": "helpful",
  "created_at": "2026-02-03T14:30:00Z"
}
```

---

## Statistics

### GET /api/stats/costs

Get AI token usage and cost report.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `days` | integer | 30 | Days to include |

**Response:**
```json
{
  "cost_report": {
    "period_start": "2026-01-04",
    "period_end": "2026-02-03",
    "total_calls": 150,
    "total_tokens": 125000,
    "total_cost_usd": 0.1875,
    "by_feature": [
      {
        "feature": "daily_brief",
        "total_calls": 30,
        "total_tokens": 45000,
        "total_cost_usd": 0.0675,
        "avg_tokens_per_call": 1500,
        "avg_cost_per_call": 0.00225
      }
    ],
    "by_day": {
      "2026-02-03": 0.0075,
      "2026-02-02": 0.0068
    },
    "model_used": "gpt-4o-mini"
  },
  "recent_usage": [...]
}
```

### GET /api/stats/trends

Get data trends.

**Query Parameters:**
| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `metric` | string | sleep | Metric: sleep,readiness,activity,energy |
| `days` | integer | 30 | Days of history |

**Response:**
```json
{
  "metric": "sleep",
  "days": 30,
  "trend": "improving",
  "change_percent": 8.5,
  "data_points": [...]
}
```

---

## Backup & Restore

### GET /api/backup/list

List available backups.

**Response:**
```json
{
  "backups": [
    {
      "id": "20260203_120000",
      "filename": "lifeos_backup_20260203_120000.db",
      "timestamp": "2026-02-03T12:00:00Z",
      "size_mb": 2.5
    }
  ],
  "backup_dir": "/app/backups"
}
```

### POST /api/backup/create

Create a new backup.

**Response:**
```json
{
  "success": true,
  "message": "Backup created successfully",
  "backup_id": "20260203_143000"
}
```

### POST /api/backup/restore

Restore from a backup.

**Request Body:**
```json
{
  "backup_id": "20260203_120000"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Database restored from backup 20260203_120000"
}
```

---

## Settings

### GET /api/settings

Get current settings.

**Response:**
```json
{
  "user_name": "User",
  "timezone": "UTC",
  "notifications": {
    "telegram_enabled": true,
    "discord_enabled": true,
    "quiet_hours_enabled": true,
    "quiet_hours_start": "23:00",
    "quiet_hours_end": "08:00"
  },
  "integrations": {
    "oura_configured": true,
    "ai_configured": true,
    "telegram_configured": true,
    "discord_configured": true
  },
  "ai_model": "gpt-4o-mini"
}
```

### PATCH /api/settings

Update settings.

**Request Body:**
```json
{
  "user_name": "Perttu",
  "timezone": "Europe/Helsinki",
  "quiet_hours_start": "22:00"
}
```

**Response:** Updated SettingsResponse object

---

## Onboarding

### GET /api/onboarding/status

Get onboarding progress.

**Response:**
```json
{
  "completed": false,
  "steps": {
    "oura_connected": true,
    "ai_configured": true,
    "data_synced": true,
    "brief_generated": false,
    "notifications_setup": false
  },
  "next_step": "generate_brief"
}
```

### POST /api/onboarding/step/{step}

Complete an onboarding step.

**Valid steps:** `oura`, `ai`, `sync`, `brief`, `notifications`

**Response:**
```json
{
  "step": "brief",
  "success": true,
  "message": "First brief generated successfully"
}
```

---

## Error Handling

All errors return a structured response:

```json
{
  "error": "oura_not_configured",
  "message": "Oura Ring is not configured",
  "category": "configuration",
  "suggestions": [
    "Get your Personal Access Token from cloud.ouraring.com/personal-access-tokens",
    "Add OURA_TOKEN=your_token to your .env file",
    "Restart the server after updating .env"
  ],
  "docs_url": "https://cloud.ouraring.com/personal-access-tokens"
}
```

### Error Categories

| Category | HTTP Status | Description |
|----------|-------------|-------------|
| `configuration` | 503 | Service not configured |
| `authentication` | 401 | Invalid credentials |
| `rate_limit` | 429 | Rate limit exceeded |
| `connection` | 503 | Connection failed |
| `validation` | 400 | Invalid input |
| `not_found` | 404 | Resource not found |
| `internal` | 500 | Server error |

### Common Errors

| Error Code | Description | Fix |
|------------|-------------|-----|
| `oura_not_configured` | Oura token missing | Add `OURA_TOKEN` to `.env` |
| `ai_not_configured` | AI API key missing | Add `OPENAI_API_KEY` to `.env` |
| `calendar_not_configured` | Google Calendar not set up | Add Google OAuth credentials |
| `invalid_date_range` | Invalid date format | Use YYYY-MM-DD format |
| `no_data_for_date` | No data available | Sync data first |

---

## Rate Limits

| Service | Limit | Notes |
|---------|-------|-------|
| Oura API | ~5000/month | Personal Access Token |
| OpenAI | Varies by plan | Check your quota |
| Google Calendar | 1M/day | OAuth quotas |

---

## Webhooks

LifeOS can receive webhooks from external services.

### Telegram Bot Webhook

Configure your Telegram bot to POST to `/api/capture/webhook`:

```json
{
  "text": "/log 4",
  "source": "telegram",
  "chat_id": "123456789",
  "message_id": "456"
}
```

### Discord Webhook (Outbound)

LifeOS sends to your Discord webhook URL for notifications. No inbound webhooks supported yet.

---

## SDK Examples

### Python

```python
import httpx

client = httpx.Client(base_url="http://localhost:8080")

# Get morning brief
brief = client.get("/api/insights/brief", params={"generate": True}).json()
print(brief["content"])

# Log energy
client.post("/api/log", json={"energy": 4, "mood": 4, "notes": "Great day!"})

# Sync Oura data
client.post("/api/oura/sync", json={"start_date": "2026-02-01"})
```

### JavaScript

```javascript
// Get morning brief
const brief = await fetch('/api/insights/brief?generate=true').then(r => r.json());
console.log(brief.content);

// Log energy
await fetch('/api/log', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({energy: 4, mood: 4})
});
```

### cURL

```bash
# Get brief
curl http://localhost:8080/api/insights/brief?generate=true

# Log energy
curl -X POST http://localhost:8080/api/log \
  -H "Content-Type: application/json" \
  -d '{"energy": 4, "mood": 4}'

# Upload voice note
curl -X POST http://localhost:8080/api/voice/upload -F "file=@note.mp3"
```

---

## OpenAPI Specification

The full OpenAPI 3.0 specification is available at:

- **JSON**: `http://localhost:8080/openapi.json`
- **Swagger UI**: `http://localhost:8080/docs`
- **ReDoc**: `http://localhost:8080/redoc`
