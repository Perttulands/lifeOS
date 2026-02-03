"""
LifeOS API Routers

FastAPI routers split by domain.
"""

from .health import router as health_router
from .insights import router as insights_router
from .data import router as data_router
from .oura import router as oura_router
from .notify import router as notify_router
from .capture import router as capture_router
from .settings import router as settings_router
from .backup import router as backup_router
from .calendar import router as calendar_router
from .stats import router as stats_router
from .preferences import router as preferences_router
from .backfill import router as backfill_router
from .voice import router as voice_router
from .onboarding import router as onboarding_router
from .journal import router as journal_router
from .goals import router as goals_router

__all__ = [
    "health_router",
    "insights_router",
    "data_router",
    "oura_router",
    "notify_router",
    "capture_router",
    "settings_router",
    "backup_router",
    "calendar_router",
    "stats_router",
    "preferences_router",
    "backfill_router",
    "voice_router",
    "onboarding_router",
    "journal_router",
    "goals_router",
]
