<div align="center">

```
   ▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄▄
   █                                                           █
   █     ██╗     ██╗███████╗███████╗ ██████╗ ███████╗          █
   █     ██║     ██║██╔════╝██╔════╝██╔═══██╗██╔════╝          █
   █     ██║     ██║█████╗  █████╗  ██║   ██║███████╗          █
   █     ██║     ██║██╔══╝  ██╔══╝  ██║   ██║╚════██║          █
   █     ███████╗██║██║     ███████╗╚██████╔╝███████║          █
   █     ╚══════╝╚═╝╚═╝     ╚══════╝ ╚═════╝ ╚══════╝          █
   █                                                           █
   █              Your Personal Operating System               █
   █                                                           █
   ▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀▀
```

### *Stop tracking. Start living.*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-00a393.svg)](https://fastapi.tiangolo.com)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

[Features](#-features) • [Quick Start](#-quick-start) • [Demo](#-demo) • [Architecture](#-architecture) • [API](#-api-overview) • [Contributing](#-contributing)

</div>

---

## 🌙 What is LifeOS?

**LifeOS** is an AI-powered personal operating system that transforms your biometric data into actionable insights. It passively collects data from your Oura ring, calendar, and voice notes—then uses AI to surface patterns you'd never find yourself.

> *"Your deep sleep drops 40% after days with more than 4 hours of meetings."*

Most self-tracking tools demand more than they give. LifeOS inverts this equation:

| Traditional Apps | LifeOS |
|-----------------|--------|
| Manual logging required | Passive data collection |
| Dashboard overwhelm | AI-curated daily brief |
| You find the patterns | Patterns find you |
| Another todo app | A thinking partner |

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🌅 Morning Brief
Wake up to an AI-generated summary of your sleep, energy prediction, and one actionable suggestion for the day.

### 🧠 Pattern Detection
Statistical analysis + LLM intelligence discovers correlations in your data that you'd never notice manually.

### 🎤 Voice Capture
Record voice notes on the go. Whisper transcribes, AI categorizes as task/note/energy log automatically.

</td>
<td width="50%">

### 📊 Beautiful Dashboard
A joyful, warm dark theme that's easy on the eyes and delightful to use every morning.

### 📱 Mobile Delivery
Get briefs via Telegram or Discord at 7 AM. No app required.

### 🔒 Local-First
SQLite database means your data stays on your machine. No cloud dependency.

</td>
</tr>
</table>

### Full Feature List

| Feature | Description |
|---------|-------------|
| 💤 **Oura Integration** | Auto-sync sleep, readiness, and activity scores |
| 📅 **Google Calendar** | Meeting patterns affect energy prediction |
| 🎙️ **Voice Notes** | Whisper-powered transcription + auto-categorization |
| ⚡ **Energy Tracking** | Log energy levels, discover your peak hours |
| 📈 **Trend Analysis** | 7-day, 30-day, 90-day trend visualization |
| 🤖 **Personalization** | AI learns your preferences over time |
| 💾 **Automated Backups** | Daily backups with one-click restore |
| 🔔 **Smart Notifications** | Quiet hours respected, no spam |

---

## 🎬 Demo

<div align="center">

<!-- Replace with actual GIF/screenshot -->
```
┌─────────────────────────────────────────────────────────────────┐
│  🌙 LifeOS                                   Good morning! ☀️   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ╭──────────────────────────────────────────────────────────╮  │
│  │  📝 Your Morning Brief                                   │  │
│  │                                                          │  │
│  │  Last night you got 7h 12m of sleep with 1h 45m deep    │  │
│  │  sleep—that's 15% above your average. Your readiness    │  │
│  │  score of 85 suggests today's a great day for focused   │  │
│  │  work. With 3 meetings totaling 2 hours, you'll have    │  │
│  │  solid blocks for deep work. Consider tackling your     │  │
│  │  most challenging task before 11 AM when you typically  │  │
│  │  peak.                                                   │  │
│  ╰──────────────────────────────────────────────────────────╯  │
│                                                                 │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐                           │
│  │ 💤 85   │ │ ⚡ 78   │ │ 🏃 62   │                           │
│  │ Sleep   │ │ Ready   │ │Activity │                           │
│  └─────────┘ └─────────┘ └─────────┘                           │
│                                                                 │
│  📈 Energy Trend (7 days)                                       │
│  ▁▂▄▆█▇▅                                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

*[Add your own screenshot: `docs/images/dashboard.png`]*

</div>

---

## 🚀 Quick Start

Get running in **3 commands**:

```bash
git clone https://github.com/yourusername/lifeOS.git && cd lifeOS
./setup.sh                    # Creates venv, installs deps, inits DB
nano .env                     # Add your OURA_TOKEN and OPENAI_API_KEY
```

Then:
```bash
source .venv/bin/activate && python -m uvicorn src.api:app --port 8080
```

Open **http://localhost:8080** 🎉

### 🐳 Docker (Recommended for Production)

```bash
cp .env.example .env          # Configure your tokens
docker compose up -d          # That's it!
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LifeOS Architecture                            │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
    │  Oura Ring   │     │   Calendar   │     │ Voice Notes  │
    │   (Sleep)    │     │  (Meetings)  │     │  (Whisper)   │
    └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
           │                    │                    │
           └────────────────────┼────────────────────┘
                                │
                                ▼
    ┌─────────────────────────────────────────────────────────────┐
    │                      FastAPI Backend                         │
    │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
    │  │   Routers   │  │  Services   │  │   Integrations      │  │
    │  │ /api/...    │  │  Insights   │  │  • Oura API         │  │
    │  │             │  │  Patterns   │  │  • Google Calendar  │  │
    │  │             │  │  Capture    │  │  • Whisper API      │  │
    │  │             │  │  Personal.  │  │  • Telegram/Discord │  │
    │  └─────────────┘  └─────────────┘  └─────────────────────┘  │
    └─────────────────────────────┬───────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              │                   │                   │
              ▼                   ▼                   ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │   SQLite     │    │   LiteLLM    │    │   Frontend   │
    │  (Local DB)  │    │    (AI)      │    │  (Vanilla)   │
    └──────────────┘    └──────────────┘    └──────────────┘

```

### Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| **Backend** | Python + FastAPI | Fast, modern, async-ready |
| **Database** | SQLite | Local-first, zero config |
| **AI** | LiteLLM | Model-agnostic (OpenAI, Anthropic, local) |
| **Frontend** | Vanilla HTML/CSS/JS | No build step, instant reload |
| **Transcription** | OpenAI Whisper | Best-in-class speech-to-text |

---

## 📡 API Overview

LifeOS exposes a comprehensive REST API:

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/insights/brief` | GET | Get today's morning brief |
| `/api/insights/patterns` | GET | Get detected patterns |
| `/api/predictions/energy` | GET | Get energy prediction |
| `/api/log` | POST | Quick log energy/mood |
| `/api/capture` | POST | AI-categorized capture |
| `/api/voice/upload` | POST | Upload voice note |

### Integrations

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/oura/sync` | POST | Sync Oura data |
| `/api/calendar/sync` | POST | Sync Google Calendar |
| `/api/brief/deliver` | POST | Send brief to Telegram/Discord |

### Full API Documentation

Once running, visit **http://localhost:8080/docs** for interactive Swagger documentation.

<details>
<summary>📋 Example: Get Morning Brief</summary>

```bash
curl http://localhost:8080/api/insights/brief?generate=true
```

Response:
```json
{
  "id": 42,
  "type": "daily_brief",
  "date": "2026-02-03",
  "content": "Last night you got 7h 12m of sleep with 1h 45m deep sleep...",
  "confidence": 0.85,
  "created_at": "2026-02-03T07:00:00"
}
```
</details>

<details>
<summary>🎤 Example: Upload Voice Note</summary>

```bash
curl -X POST http://localhost:8080/api/voice/upload \
  -F "file=@note.mp3"
```

Response:
```json
{
  "id": 1,
  "filename": "note.mp3",
  "transcription": "Remember to call mom about Sunday dinner",
  "transcription_status": "completed",
  "categorized_type": "task",
  "categorized_id": 15,
  "success": true,
  "message": "Voice note uploaded. Transcribed: 47 chars. Categorized as: task"
}
```
</details>

---

## ⚙️ Configuration

Create a `.env` file:

```bash
# Required
OURA_TOKEN=your_oura_personal_access_token
OPENAI_API_KEY=your_openai_api_key

# Optional - AI Model
LITELLM_MODEL=gpt-4o-mini          # or claude-3-haiku, etc.

# Optional - Notifications
TELEGRAM_BOT_TOKEN=123456:ABC...
TELEGRAM_CHAT_ID=123456789
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...

# Optional - Google Calendar
GOOGLE_CLIENT_ID=xxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=xxx
```

### Getting API Keys

| Service | How to Get |
|---------|------------|
| **Oura** | [cloud.ouraring.com/personal-access-tokens](https://cloud.ouraring.com/personal-access-tokens) |
| **OpenAI** | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| **Telegram** | Message [@BotFather](https://t.me/BotFather) on Telegram |
| **Google Calendar** | [console.cloud.google.com](https://console.cloud.google.com/apis/credentials) |

---

## 📸 Screenshots

<div align="center">

| Dashboard | Morning Brief | Trends |
|:---------:|:-------------:|:------:|
| *Add screenshot* | *Add screenshot* | *Add screenshot* |

| Settings | Voice Notes | Mobile (Telegram) |
|:--------:|:-----------:|:-----------------:|
| *Add screenshot* | *Add screenshot* | *Add screenshot* |

</div>

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

### Development Setup

```bash
# Fork and clone
git clone https://github.com/yourusername/lifeOS.git
cd lifeOS

# Create branch
git checkout -b feature/amazing-feature

# Setup environment
./setup.sh
source .venv/bin/activate

# Run in development mode
python -m uvicorn src.api:app --reload --port 8080
```

### Project Structure

```
lifeOS/
├── src/
│   ├── api.py              # FastAPI application
│   ├── models.py           # SQLAlchemy models
│   ├── ai.py               # LiteLLM integration
│   ├── insights_service.py # Brief & pattern generation
│   ├── routers/            # API endpoints
│   ├── integrations/       # Oura, Calendar, Whisper
│   └── jobs/               # Cron job scripts
├── ui/
│   ├── index.html          # Dashboard
│   ├── css/                # Styles (modular)
│   └── js/                 # Scripts
├── docs/                   # Documentation
├── tests/                  # Test suite
└── docker-compose.yml      # Docker deployment
```

### Guidelines

- **Commit early, commit often** - Small, focused commits
- **Test your changes** - Run `pytest` before pushing
- **Follow the style** - Black formatting, type hints
- **Document APIs** - Update docstrings and README

---

## 📄 License

MIT License - do whatever you want, just don't blame us.

```
MIT License

Copyright (c) 2026 LifeOS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

<div align="center">

### 🌙

**Built for humans who want to live better, not just track more.**

[⬆ Back to top](#)

</div>
