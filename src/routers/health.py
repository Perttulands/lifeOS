"""
Health check endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    HealthResponse,
    DetailedHealthResponse,
    ServiceCheckResponse,
)

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("", response_model=HealthResponse)
async def health():
    """
    Basic health check endpoint.

    Returns minimal health info for load balancers and uptime monitors.
    Use /api/health/detailed for full diagnostics.
    """
    from ..health import get_health_monitor

    monitor = get_health_monitor()
    return HealthResponse(
        status="healthy",
        version=monitor.VERSION,
        timestamp=datetime.utcnow().isoformat()
    )


@router.get("/detailed", response_model=DetailedHealthResponse)
async def health_detailed(db: Session = Depends(get_db)):
    """
    Detailed health check with service status.

    Checks:
    - Database connectivity
    - Oura integration status
    - AI service status
    - Notification service status

    Also returns uptime and recent errors.
    """
    from ..health import get_health_monitor

    monitor = get_health_monitor()
    report = await monitor.get_health_report(db)

    # Convert ServiceCheck objects to dicts
    services = {}
    for name, check in report.services.items():
        services[name] = ServiceCheckResponse(
            name=check.name,
            status=check.status.value,
            message=check.message,
            latency_ms=check.latency_ms
        )

    return DetailedHealthResponse(
        status=report.status.value,
        version=report.version,
        uptime_seconds=report.uptime_seconds,
        started_at=report.started_at,
        timestamp=report.timestamp,
        services=services,
        recent_errors=report.recent_errors
    )


@router.post("/errors/clear")
async def clear_errors():
    """Clear the error history."""
    from ..health import get_health_monitor

    monitor = get_health_monitor()
    monitor.clear_errors()
    return {"success": True, "message": "Error history cleared"}


@router.get("/uptime")
async def get_uptime():
    """Get system uptime information."""
    from ..health import get_health_monitor

    monitor = get_health_monitor()

    uptime_secs = monitor.uptime_seconds
    days = int(uptime_secs // 86400)
    hours = int((uptime_secs % 86400) // 3600)
    minutes = int((uptime_secs % 3600) // 60)

    return {
        "uptime_seconds": uptime_secs,
        "uptime_formatted": f"{days}d {hours}h {minutes}m",
        "started_at": monitor.started_at
    }
