# LifeOS Quickstart

> Get up and running in 5 minutes.

## Prerequisites

- Python 3.11+
- An [Oura Ring](https://ouraring.com) (or any Oura data)
- An AI API key (OpenAI, Anthropic, or any LiteLLM-compatible provider)

---

## Step 1: Clone & Setup

```bash
git clone https://github.com/Perttulands/lifeOS.git
cd lifeOS
./setup.sh
```

The setup script will:
- Create a Python virtual environment
- Install all dependencies
- Initialize the database
- Create your `.env` file from the template

---

## Step 2: Get Your Oura Token

1. Go to [cloud.ouraring.com/personal-access-tokens](https://cloud.ouraring.com/personal-access-tokens)
2. Click **Create New Personal Access Token**
3. Copy the token (starts with `OU...`)

---

## Step 3: Get an AI API Key

Choose one:

**OpenAI** (Recommended for beginners)
1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys)
2. Create a new secret key

**Anthropic**
1. Go to [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
2. Create a new API key

---

## Step 4: Configure

Edit your `.env` file:

```bash
nano .env  # or use any text editor
```

Add your tokens:

```env
# Required
OURA_TOKEN=OUxxxxxxxxxxxxxxxxxx
LITELLM_API_KEY=sk-xxxxxxxxxxxxxxxxxx

# Optional: Change the AI model (default: gpt-4o-mini)
# LITELLM_MODEL=gpt-4o-mini
```

---

## Step 5: Launch

```bash
source .venv/bin/activate
python -m uvicorn src.api:app --reload --port 8080
```

Open **http://localhost:8080** in your browser.

---

## Step 6: Import Your Data

On first launch, LifeOS will guide you through:

1. **Verifying your Oura connection** - Checks your token works
2. **Importing historical data** - Backfills 90 days of sleep, activity, and readiness data

You can also trigger this manually via Settings > Data Import.

---

## What's Next?

### Morning Brief

Your daily AI-powered summary based on your sleep and schedule. Appears automatically on the dashboard.

### Notifications (Optional)

Get your daily brief delivered to Telegram or Discord:

```env
# Telegram
TELEGRAM_BOT_TOKEN=123456789:ABCdef...
TELEGRAM_CHAT_ID=123456789

# Or Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

### Google Calendar (Optional)

Connect your calendar to detect meeting patterns:

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
```

Then visit `/api/calendar/auth` to complete OAuth.

---

## Troubleshooting

### "Invalid Oura token"

- Make sure you copied the full token (starts with `OU`)
- Regenerate the token if needed at cloud.ouraring.com

### "AI service not configured"

- Check that `LITELLM_API_KEY` is set in `.env`
- Verify your API key is valid and has credits

### "Database error"

- Run `./setup.sh` again to reinitialize
- Check that `lifeos.db` exists in the project root

### Need Help?

- [GitHub Issues](https://github.com/Perttulands/lifeOS/issues)
- [Full Documentation](README.md)

---

## Commands Reference

```bash
# Start the server
source .venv/bin/activate
python -m uvicorn src.api:app --reload --port 8080

# Import Oura data (90 days)
curl -X POST http://localhost:8080/api/backfill/oura?days=90

# Generate daily brief
python -m src.jobs.daily_brief

# Check health
curl http://localhost:8080/api/health/detailed
```

---

*Welcome to LifeOS. Your data, your insights, your life.*
