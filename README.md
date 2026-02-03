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
- 📱 **Mobile Delivery** - Get briefs via Telegram/Discord at 7 AM
- 💤 **Sleep Insights** - Patterns you'd never notice yourself
- ⚡ **Energy Tracking** - Know when you do your best work
- 📊 **Beautiful Dashboard** - Glanceable, joyful, useful

## Quick Start

```bash
# Clone
git clone https://github.com/Perttulands/lifeOS.git
cd lifeOS

# Run setup script (creates venv, installs deps, inits db)
./setup.sh

# Edit .env with your API tokens
nano .env  # Add OURA_TOKEN and LITELLM_API_KEY

# Activate virtual environment and run
source .venv/bin/activate
python -m uvicorn src.api:app --reload --port 8080
```

Open http://localhost:8080

### Manual Setup

If you prefer manual setup:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env and add your tokens

# Initialize database
python -c "from src.database import init_db; from src.models import *; init_db()"

# Run
python -m uvicorn src.api:app --reload --port 8080
```

## Docker Deployment

The recommended way to run LifeOS in production.

### Quick Start with Docker Compose

```bash
# Clone and setup
git clone https://github.com/Perttulands/lifeOS.git
cd lifeOS

# Create your environment file
cp .env.example .env
# Edit .env and add your OURA_TOKEN, LITELLM_API_KEY

# Build and run
docker compose up -d

# View logs
docker compose logs -f
```

Open http://localhost:8080

### Docker Commands

```bash
# Build the image
docker compose build

# Start in background
docker compose up -d

# Stop
docker compose down

# Stop and remove data volume
docker compose down -v

# View logs
docker compose logs -f lifeos

# Restart
docker compose restart
```

### Data Persistence

SQLite database is stored in a Docker volume (`lifeos-data`). Your data persists across container restarts.

To backup:
```bash
docker compose exec lifeos cp /data/lifeos.db /data/backup.db
docker cp lifeos:/data/backup.db ./backup.db
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OURA_TOKEN` | Yes | - | Oura Personal Access Token |
| `LITELLM_API_KEY` | Yes | - | LiteLLM/OpenAI API key |
| `LITELLM_MODEL` | No | `gpt-4o-mini` | AI model to use |
| `TELEGRAM_BOT_TOKEN` | No | - | Telegram Bot API token (from @BotFather) |
| `TELEGRAM_CHAT_ID` | No | - | Your Telegram chat ID |
| `DISCORD_WEBHOOK_URL` | No | - | Discord channel webhook URL |
| `DATABASE_URL` | No | `sqlite:////data/lifeos.db` | Database connection |
| `PORT` | No | `8080` | Server port |

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
