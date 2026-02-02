# LifeOS - Product Requirements Document

> The AI-powered self-management system that's actually worth using daily.

## Vision

**LifeOS** is your personal operating system for life. It learns your patterns, anticipates your needs, and helps you become the person you want to be - without the friction of traditional productivity apps.

Most self-management tools fail because they demand more than they give. LifeOS inverts this: **passive capture, active insights**.

## The Problem

1. **Data fragmentation** - Sleep in Oura, tasks in Todoist, notes in Obsidian, calendar in Google
2. **Insight paralysis** - Raw data without meaning (who cares about HRV if you don't know what to do with it?)
3. **Willpower tax** - Every manual entry is friction that compounds into abandonment
4. **One-size-fits-none** - Generic advice that ignores *your* patterns

## The Solution

LifeOS connects your data streams, finds the patterns that matter, and surfaces actionable insights at the right moment.

### Core Principles

1. **Zero-friction capture** - If it requires manual entry, it better be worth it
2. **Contextual intelligence** - AI that knows *your* patterns, not generic advice
3. **Proactive, not reactive** - Surface insights before you need to ask
4. **Beautiful by default** - Joy comes from delight, not just utility
5. **Privacy-first** - Your data stays yours (local-first architecture)

## User Personas

### Primary: Perttu (Builder/Founder)
- Technical, data-driven
- Uses Oura for biometrics
- Runs AI agents overnight
- Wants to optimize energy, not just time
- Values: autonomy, insight, efficiency

## Features

### Phase 1: Foundation (MVP)

#### 1. Oura Integration
- Sync sleep, activity, readiness scores
- Surface patterns: "Your deep sleep drops 40% after late screen time"
- Correlate with calendar/work patterns

#### 2. Daily Brief (Morning AI)
- 7 AM personalized briefing
- Based on: sleep quality, calendar, pending tasks, weather
- Format: conversational, actionable
- "You got 6.2h sleep (below your 7h average). Consider pushing the 2pm meeting - your afternoon energy typically crashes on short sleep days."

#### 3. Energy-Aware Scheduling
- Suggest optimal times for deep work vs meetings
- Learn from patterns: when do YOU do your best thinking?
- Integration with calendar for smart blocking

#### 4. Quick Capture
- Voice note → AI categorizes and processes
- "Note: had a great idea about the chaos absorber UI" → creates task/note in right place
- Telegram/Discord integration for frictionless input

#### 5. Weekly Review AI
- Sunday evening summary
- What worked, what didn't
- Pattern insights across the week
- Suggested adjustments

### Phase 2: Intelligence

#### 6. Mood/Energy Journaling
- Simple 1-10 scale, optional note
- AI correlates with sleep, activity, calendar
- Surface triggers: "You report lower energy on days with >4 meetings"

#### 7. Goal Tracking
- Not todo lists - actual goals with progress
- AI breaks down goals into actionable steps
- Adaptive: adjusts timeline based on your actual velocity

#### 8. Context Switching
- Detect context from calendar/time
- "Entering deep work block" - suggest focus mode
- "Meeting in 10min" - surface relevant prep

### Phase 3: Delight

#### 9. Achievements & Streaks
- Celebrate wins (without being annoying)
- "3 weeks of consistent sleep schedule 🎉"
- Gamification that respects intelligence

#### 10. Voice Interface
- "Hey LifeOS, how did I sleep?"
- Natural conversation, not commands
- ElevenLabs TTS for responses

#### 11. Ambient Dashboard
- E-ink display / always-on tablet mode
- Shows: today's energy, next event, focus suggestion
- Beautiful, minimal, glanceable

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         LifeOS Core                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐        │
│  │  Oura    │  │ Calendar │  │  Tasks   │  │  Notes   │        │
│  │ Adapter  │  │ Adapter  │  │ Adapter  │  │ Adapter  │        │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘        │
│       │             │             │             │                │
│       └─────────────┴──────┬──────┴─────────────┘                │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │  Data Store   │                            │
│                    │   (SQLite)    │                            │
│                    └───────┬───────┘                            │
│                            │                                     │
│                    ┌───────▼───────┐                            │
│                    │   AI Engine   │                            │
│                    │  (LiteLLM)    │                            │
│                    └───────┬───────┘                            │
│                            │                                     │
│       ┌────────────────────┼────────────────────┐               │
│       │                    │                    │                │
│  ┌────▼────┐        ┌─────▼─────┐       ┌─────▼─────┐          │
│  │  API    │        │  Cron     │       │   CLI     │          │
│  │ Server  │        │  Jobs     │       │Interface  │          │
│  └────┬────┘        └───────────┘       └───────────┘          │
│       │                                                          │
│  ┌────▼────────────────────────────────────────────┐            │
│  │                  Web UI                          │            │
│  │  • Dashboard    • Journal    • Insights          │            │
│  └──────────────────────────────────────────────────┘            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite (local-first, portable)
- **AI:** LiteLLM (flexible model routing)
- **Frontend:** Single HTML file with vanilla JS (no build step)
- **Integrations:** Oura API, Google Calendar API
- **Notifications:** Telegram/Discord via Clawdbot

### Data Model

```sql
-- Core tables
users (id, name, timezone, preferences)
data_points (id, user_id, source, type, value, timestamp, metadata)
insights (id, user_id, type, content, context, created_at, acted_on)
goals (id, user_id, title, description, target_date, status, progress)
journal_entries (id, user_id, energy, mood, notes, timestamp)
```

## Success Metrics

1. **Daily Active Use** - Do you actually open it every day?
2. **Insight Accuracy** - Are the AI suggestions useful?
3. **Time to Value** - How fast does first useful insight appear?
4. **Capture Friction** - Seconds to log something

## Non-Goals (v1)

- Social features
- Team collaboration
- Mobile native app (web-first)
- Complex integrations beyond Oura/Calendar

## Open Questions

1. How to handle Oura API rate limits?
2. What's the right frequency for AI check-ins?
3. Voice interface priority?

## Milestones

### Week 1: Foundation
- [ ] Project setup, data model
- [ ] Oura API integration
- [ ] Basic dashboard UI
- [ ] Daily brief cron job

### Week 2: Intelligence
- [ ] Pattern detection engine
- [ ] Calendar integration
- [ ] Quick capture via Telegram
- [ ] Weekly review

### Week 3: Polish
- [ ] Beautiful UI overhaul
- [ ] Voice interface
- [ ] Ambient display mode
- [ ] Documentation

---

*"The best interface is no interface. The best productivity system is one that works while you live your life."*
