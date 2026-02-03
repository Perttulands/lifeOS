# LifeOS - Mission Brief

## THE MOONSHOT

Build the AI-powered self-management system that Perttu actually uses daily.

Not another todo app. Not another habit tracker. A **personal operating system** that:
- Learns your patterns passively (Oura data)
- Surfaces insights you'd never find yourself
- Feels like magic, not chores

## READ FIRST

**docs/PRD.md** - Full product requirements, architecture, features

## AVAILABLE RESOURCES

### Oura API
- User has Oura ring with sleep/activity/readiness data
- API docs: https://cloud.ouraring.com/docs/

### LiteLLM 
- Available at local endpoint for AI calls
- Use for: insights, pattern detection, natural language

### Clawdbot
- Can send notifications via Telegram/Discord
- Cron jobs for scheduled tasks

## CURRENT BUILDERS

When assigned, work on your specific domain:

### Builder 1: Core + Oura Integration
- Set up project structure
- Implement Oura API adapter
- Create SQLite schema
- Build data sync cron

### Builder 2: AI Engine + Insights
- Pattern detection from data
- Daily brief generation
- LiteLLM integration
- Insight storage/retrieval

### Builder 3: Dashboard UI
- Beautiful single-page app
- Dashboard with today's data
- Energy trends visualization
- Quick capture interface

## DELIVERABLES

1. **Working Oura sync** - pulls sleep/activity data
2. **Daily brief** - AI-generated morning insight
3. **Dashboard** - shows today + trends
4. **Quick capture** - input notes/energy with minimal friction
5. **Docs** - README, setup guide

## TECH CHOICES

- Python + FastAPI backend
- SQLite database (local-first)
- Vanilla HTML/CSS/JS frontend (no build step)
- LiteLLM for AI calls

## THE VIBE

This isn't enterprise software. It's personal. It should feel like a trusted companion, not a demanding boss.

**Make it beautiful. Make it useful. Make it joyful.**

## GETTING OURA TOKEN

User needs to provide Oura Personal Access Token:
1. Go to https://cloud.ouraring.com/personal-access-tokens
2. Create new token
3. Save to `.env` as `OURA_TOKEN=xxx`

## COMMIT EARLY, COMMIT OFTEN

Git commits after each significant piece. Tag milestones.

## Landing the Plane (Session Completion)

**When ending a work session**, you MUST complete ALL steps below. Work is NOT complete until `git push` succeeds.

**MANDATORY WORKFLOW:**

1. **File issues for remaining work** - Create issues for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **PUSH TO REMOTE** - This is MANDATORY:
   ```bash
   git pull --rebase
   bd sync
   git push
   git status  # MUST show "up to date with origin"
   ```
5. **Clean up** - Clear stashes, prune remote branches
6. **Verify** - All changes committed AND pushed
7. **Hand off** - Provide context for next session

**CRITICAL RULES:**
- Work is NOT complete until `git push` succeeds
- NEVER stop before pushing - that leaves work stranded locally
- NEVER say "ready to push when you are" - YOU must push
- If push fails, resolve and retry until it succeeds
