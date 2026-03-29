# LifeOS Configuration
# Inject with: op inject -i .env.tpl -o .env

# Oura API — Personal Access Token
OURA_TOKEN={{ op://polis-city/oura/personal-access-token }}

# Oura API — OAuth2 (for future token refresh)
OURA_CLIENT_ID={{ op://polis-city/oura/client-id }}
OURA_CLIENT_SECRET={{ op://polis-city/oura/client-secret }}

# AI — use Gemini via LiteLLM
LITELLM_MODEL=gemini/gemini-2.0-flash
GEMINI_API_KEY={{ op://polis-city/gemini-lifeos/api-key }}

# Database
DATABASE_URL=sqlite:///./lifeos.db

# User
USER_TIMEZONE=Europe/Helsinki

# Server
HOST=0.0.0.0
PORT=8080
