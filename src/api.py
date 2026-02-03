"""
LifeOS API Server

FastAPI application with modular routers.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from .config import settings
from .database import init_db
from .routers import (
    health_router,
    insights_router,
    data_router,
    oura_router,
    notify_router,
    capture_router,
    settings_router,
    backup_router,
    calendar_router,
    stats_router,
    preferences_router,
    backfill_router,
    voice_router,
    onboarding_router,
    journal_router,
    goals_router,
)


# === FastAPI App ===

DESCRIPTION = """
# LifeOS API

AI-powered personal operating system that transforms your biometric data into actionable insights.

## Features

* **Morning Briefs**: AI-generated daily summaries based on sleep, calendar, and patterns
* **Pattern Detection**: Statistical + LLM analysis discovers correlations in your data
* **Voice Capture**: Whisper-powered transcription with auto-categorization
* **Energy Tracking**: Log energy levels and discover your peak hours
* **Integrations**: Oura Ring, Google Calendar, Telegram, Discord

## Quick Start

1. Configure API keys in `.env`
2. Sync Oura data: `POST /api/oura/sync`
3. Generate brief: `GET /api/insights/brief?generate=true`

## Documentation

- [API Reference](/docs/API.md)
- [Architecture Guide](/docs/ARCHITECTURE.md)
- [Product Requirements](/docs/PRD.md)
"""

TAGS_METADATA = [
    {
        "name": "health",
        "description": "System health checks and monitoring",
    },
    {
        "name": "insights",
        "description": "AI-generated briefs, patterns, and predictions",
    },
    {
        "name": "data",
        "description": "Query and manage data points",
    },
    {
        "name": "journal",
        "description": "Energy and mood logging",
    },
    {
        "name": "oura",
        "description": "Oura Ring integration and data sync",
    },
    {
        "name": "calendar",
        "description": "Google Calendar integration",
    },
    {
        "name": "voice",
        "description": "Voice note upload and transcription",
    },
    {
        "name": "capture",
        "description": "AI-powered text categorization",
    },
    {
        "name": "notifications",
        "description": "Telegram and Discord delivery",
    },
    {
        "name": "preferences",
        "description": "User preferences and personalization",
    },
    {
        "name": "stats",
        "description": "Usage statistics and cost tracking",
    },
    {
        "name": "backup",
        "description": "Database backup and restore",
    },
    {
        "name": "settings",
        "description": "Application configuration",
    },
    {
        "name": "onboarding",
        "description": "Setup wizard and initial configuration",
    },
    {
        "name": "goals",
        "description": "Goal tracking and progress",
    },
]

app = FastAPI(
    title="LifeOS",
    description=DESCRIPTION,
    version="0.1.0",
    openapi_tags=TAGS_METADATA,
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    contact={
        "name": "LifeOS",
        "url": "https://github.com/yourusername/lifeOS",
    },
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include routers
app.include_router(health_router)
app.include_router(insights_router)
app.include_router(data_router)
app.include_router(oura_router)
app.include_router(notify_router)
app.include_router(capture_router)
app.include_router(settings_router)
app.include_router(backup_router)
app.include_router(calendar_router)
app.include_router(stats_router)
app.include_router(preferences_router)
app.include_router(backfill_router)
app.include_router(voice_router)
app.include_router(onboarding_router)
app.include_router(journal_router)
app.include_router(goals_router)


# === Startup ===

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


# === Static Files & Frontend ===

# Determine UI directory (works in both local dev and Docker)
_ui_dir = Path(__file__).parent.parent / "ui"
if not _ui_dir.exists():
    _ui_dir = Path("/app/ui")

if _ui_dir.exists():
    # Serve static assets (CSS, JS)
    app.mount("/static", StaticFiles(directory=str(_ui_dir)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the main dashboard."""
        return FileResponse(str(_ui_dir / "index.html"))

    @app.get("/{path:path}")
    async def serve_static(path: str):
        """Serve static files or fallback to index for SPA routing."""
        file_path = _ui_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_ui_dir / "index.html"))


# === Run Server ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
