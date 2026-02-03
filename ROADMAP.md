# LifeOS Roadmap

## Current State (Built by Builders)
- ✅ Core infrastructure (config, database, models)
- ✅ AI Engine with LiteLLM (ai.py - 17KB)
- ✅ Insights Service layer (insights_service.py - 11KB)
- ✅ FastAPI with 12+ endpoints (api.py - 14KB)
- ✅ Cron jobs (daily_brief, weekly_review, pattern_detection)
- ✅ Dashboard UI (HTML/CSS/JS with time-of-day themes)
- ✅ PRD with AI Philosophy

## Gap to Vision

### Epic: Data Integration
- [ ] Oura API adapter (OAuth2 flow, sync sleep/activity/readiness)
- [ ] Google Calendar adapter (read events, detect patterns)
- [ ] Data backfill (historical import on first connect)

### Epic: AI Intelligence
- [ ] Real pattern detection (not just prompts - actual correlation analysis)
- [ ] Energy prediction with ML (compare to LLM predictions)
- [ ] Personalization layer (learn user preferences over time)
- [ ] Cost tracking dashboard (tokens spent per feature)

### Epic: Capture & Input
- [ ] Quick capture via Telegram/Discord
- [ ] Voice notes with transcription
- [ ] Manual energy/mood logging (UI exists, needs backend wire-up)

### Epic: Notifications & Delivery
- [ ] Morning brief delivery (Telegram/Discord/email)
- [ ] Weekly review delivery
- [ ] Smart notification timing (don't ping during sleep)

### Epic: UI Polish
- [ ] Wire dashboard to real API (currently demo data)
- [ ] Trend charts with real data
- [ ] Settings page (API keys, notification prefs)
- [ ] Mobile responsiveness audit

### Epic: Infrastructure
- [ ] Docker deployment
- [ ] Environment setup script
- [ ] Health monitoring
- [ ] Backup/restore for SQLite

### Epic: Delight (Phase 3)
- [ ] Voice interface with ElevenLabs TTS
- [ ] Ambient display mode
- [ ] Achievements/streaks
- [ ] E-ink dashboard support
