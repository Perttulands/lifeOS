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

app = FastAPI(
    title="LifeOS",
    description="AI-powered personal operating system. Passive capture, active insights.",
    version="0.1.0"
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
