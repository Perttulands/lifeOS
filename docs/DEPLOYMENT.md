# LifeOS Deployment Guide

Production deployment for single-machine, local-first setup.

## Quick Start

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env with your Oura token and other settings

# 2. Deploy
./deploy/deploy.sh

# 3. Access
open http://localhost
```

## Architecture

```
                    ┌──────────────────┐
    Internet ──────►│     Nginx        │ :80 (rate limiting, compression)
                    │  (reverse proxy) │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │     LifeOS       │ :8080 (internal)
                    │ (gunicorn+uvicorn)│
                    │   2 workers      │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │     SQLite       │ /data/lifeos.db
                    │   (persistent)   │
                    └──────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build, production-ready |
| `docker-compose.yml` | Development setup |
| `docker-compose.production.yml` | Production with nginx |
| `deploy/deploy.sh` | Deployment automation |
| `deploy/nginx.conf` | Nginx configuration |
| `Makefile` | Command shortcuts |

## Make Commands

```bash
# Development
make dev           # Run locally (no Docker)
make dev-docker    # Run with Docker
make test          # Run tests

# Deployment
make deploy        # Full deployment (build + start)
make deploy-up     # Start containers
make deploy-down   # Stop containers
make deploy-pull   # Pull updates and redeploy

# Monitoring
make status        # Container status
make health        # Health check
make logs          # View logs

# Database
make backup        # Backup database
make restore BACKUP=backups/lifeos-xxx.db  # Restore backup
make db-shell      # SQLite CLI
```

## Configuration

### Environment Variables

Required:
- `OURA_TOKEN` - Oura API personal access token

Optional:
- `LITELLM_API_KEY` - API key for AI features
- `LITELLM_MODEL` - Model to use (default: gpt-4o-mini)
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` - Telegram notifications
- `DISCORD_WEBHOOK_URL` - Discord notifications

Server:
- `GUNICORN_WORKERS` - Worker processes (default: 2)
- `GUNICORN_THREADS` - Threads per worker (default: 4)
- `GUNICORN_TIMEOUT` - Request timeout in seconds (default: 120)

### Tuning Workers

Rule of thumb: `(2 x CPU cores) + 1`

| Machine | GUNICORN_WORKERS |
|---------|------------------|
| 1 core  | 2                |
| 2 cores | 4                |
| 4 cores | 8                |

For local-first single-user, 2 workers is usually sufficient.

## Health Endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Basic health (load balancers) |
| `GET /api/health/ready` | Readiness probe (checks DB) |
| `GET /api/health/live` | Liveness probe (process alive) |
| `GET /api/health/detailed` | Full diagnostics |
| `GET /api/health/uptime` | Uptime info |

## Deployment Workflow

### First Deploy

```bash
# 1. Clone and configure
git clone <repo>
cd lifeOS
make setup          # Creates .env from template
nano .env           # Add your tokens

# 2. Deploy
./deploy/deploy.sh

# 3. Verify
make health
```

### Updates

```bash
# Option 1: Full redeploy
make deploy-pull

# Option 2: Manual
git pull
make build-prod
make deploy-restart
```

### Rollback

If deployment fails, the script automatically rolls back to the last backup.

Manual rollback:
```bash
make restore BACKUP=backups/lifeos-20240101-120000.db
```

## Security

### Production Checklist

- [ ] Change default ports if exposed to internet
- [ ] Configure HTTPS (uncomment in nginx.conf, add certificates)
- [ ] Review rate limits in nginx.conf
- [ ] Restrict allowed origins in CORS (src/api.py)
- [ ] Keep Docker and dependencies updated

### HTTPS Setup

1. Obtain certificates (Let's Encrypt recommended)
2. Place in `deploy/certs/`:
   - `fullchain.pem`
   - `privkey.pem`
3. Uncomment HTTPS server block in `deploy/nginx.conf`
4. Redeploy: `make deploy-restart`

## Troubleshooting

### Container won't start

```bash
# Check logs
make logs

# Check container status
docker ps -a --filter "name=lifeos"

# Inspect container
docker inspect lifeos
```

### Database issues

```bash
# Check if database exists
docker exec lifeos ls -la /data/

# Open SQLite shell
make db-shell

# Restore from backup
make restore BACKUP=backups/lifeos-xxx.db
```

### Health check failing

```bash
# Check detailed health
curl http://localhost:8080/api/health/detailed | jq

# Check container health
docker inspect lifeos --format='{{.State.Health.Status}}'
```

## Backup Strategy

Backups are created automatically before each deployment.

Manual backup:
```bash
make backup
# Saved to: backups/lifeos-YYYYMMDD-HHMMSS.db
```

The last 5 backups are kept automatically.

For additional safety, consider:
- Copying backups to external storage
- Setting up automated daily backups via cron
- Testing restore periodically

## Resource Usage

Typical memory usage for single-user:
- LifeOS container: ~100-300MB
- Nginx container: ~10MB

CPU is minimal except during AI calls (LiteLLM).

Container limits are set in docker-compose.production.yml:
- Memory limit: 512MB
- Memory reservation: 128MB
