# LifeOS 🌙

> Your personal operating system for life.

LifeOS connects your biometric data (Oura), calendar, and daily inputs to surface AI-powered insights that actually help you live better.

## Why?

Most self-management tools demand more than they give. LifeOS inverts this:

- **Passive capture** - Oura syncs automatically, AI does the work
- **Active insights** - "Your deep sleep drops 40% after late meetings"
- **Zero friction** - If it takes effort, it better be worth it

## Features

- 🌅 **Daily Brief** - Morning AI summary based on sleep, calendar, energy
- 💤 **Sleep Insights** - Patterns you'd never notice yourself
- ⚡ **Energy Tracking** - Know when you do your best work
- 📊 **Beautiful Dashboard** - Glanceable, joyful, useful

## Quick Start

```bash
# Clone
git clone https://github.com/Perttulands/lifeOS.git
cd lifeOS

# Setup
cp .env.example .env
# Add your OURA_TOKEN to .env

# Install
pip install -r requirements.txt

# Run
python -m uvicorn src.api:app --reload --port 8080
```

Open http://localhost:8080

## Stack

- **Backend:** Python + FastAPI
- **Database:** SQLite (your data stays yours)
- **AI:** LiteLLM (flexible model routing)
- **Frontend:** Vanilla HTML/CSS/JS

## Configuration

Create `.env`:
```
OURA_TOKEN=your_personal_access_token
LITELLM_API_KEY=your_api_key
LITELLM_MODEL=gpt-4o-mini
```

## Documentation

- [Product Requirements](docs/PRD.md)
- [Architecture](docs/architecture.md)
- [API Reference](docs/api.md)

## License

MIT

---

*Built with 🌙 for humans who want to live better, not just track more.*
