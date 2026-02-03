"""
LifeOS Health Monitoring

Tracks system health, uptime, and provides error alerting hooks.
"""

import time
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from sqlalchemy.orm import Session
from sqlalchemy import text

from .config import settings


class ServiceStatus(Enum):
    """Status of a service check."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class ServiceCheck:
    """Result of a service health check."""
    name: str
    status: ServiceStatus
    message: str
    latency_ms: Optional[float] = None
    last_checked: datetime = field(default_factory=datetime.utcnow)


@dataclass
class HealthReport:
    """Complete health report for the system."""
    status: ServiceStatus
    version: str
    uptime_seconds: float
    started_at: str
    timestamp: str
    services: Dict[str, ServiceCheck]
    recent_errors: List[Dict[str, Any]]


class HealthMonitor:
    """
    Monitors system health and tracks errors.

    Features:
    - Database connectivity checks
    - Service status monitoring
    - Uptime tracking
    - Error collection for alerting
    """

    VERSION = "0.1.0"
    MAX_ERRORS = 100  # Keep last 100 errors

    def __init__(self):
        self._start_time = datetime.utcnow()
        self._errors: deque = deque(maxlen=self.MAX_ERRORS)
        self._last_alert_time: Optional[datetime] = None
        self._alert_cooldown = timedelta(minutes=5)

    @property
    def uptime_seconds(self) -> float:
        """Get uptime in seconds."""
        delta = datetime.utcnow() - self._start_time
        return delta.total_seconds()

    @property
    def started_at(self) -> str:
        """Get start time as ISO string."""
        return self._start_time.isoformat()

    def record_error(
        self,
        error_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Record an error for alerting.

        Args:
            error_type: Category of error (e.g., 'database', 'oura', 'ai')
            message: Error message
            context: Additional context
        """
        error = {
            "type": error_type,
            "message": message,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self._errors.append(error)

    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent errors."""
        errors = list(self._errors)
        return errors[-limit:]

    def clear_errors(self):
        """Clear error history."""
        self._errors.clear()

    def should_alert(self) -> bool:
        """Check if we should send an alert (respecting cooldown)."""
        if self._last_alert_time is None:
            return True
        return datetime.utcnow() - self._last_alert_time > self._alert_cooldown

    def mark_alerted(self):
        """Mark that an alert was sent."""
        self._last_alert_time = datetime.utcnow()

    async def check_database(self, db: Session) -> ServiceCheck:
        """Check database connectivity."""
        start = time.perf_counter()
        try:
            # Simple query to verify connection
            result = db.execute(text("SELECT 1"))
            result.fetchone()
            latency = (time.perf_counter() - start) * 1000

            return ServiceCheck(
                name="database",
                status=ServiceStatus.HEALTHY,
                message="Connected",
                latency_ms=round(latency, 2)
            )
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            self.record_error("database", str(e))
            return ServiceCheck(
                name="database",
                status=ServiceStatus.UNHEALTHY,
                message=f"Connection failed: {str(e)[:100]}",
                latency_ms=round(latency, 2)
            )

    def check_oura(self) -> ServiceCheck:
        """Check Oura integration status."""
        if not settings.oura_token:
            return ServiceCheck(
                name="oura",
                status=ServiceStatus.UNKNOWN,
                message="Not configured"
            )

        # Token is configured - assume healthy
        # A deeper check would make an API call, but that's expensive for health checks
        return ServiceCheck(
            name="oura",
            status=ServiceStatus.HEALTHY,
            message="Configured"
        )

    def check_ai(self) -> ServiceCheck:
        """Check AI service status."""
        api_key = settings.get_ai_api_key()
        if not api_key:
            return ServiceCheck(
                name="ai",
                status=ServiceStatus.UNKNOWN,
                message="Not configured"
            )

        return ServiceCheck(
            name="ai",
            status=ServiceStatus.HEALTHY,
            message=f"Configured ({settings.litellm_model})"
        )

    def check_notifications(self) -> ServiceCheck:
        """Check notification service status."""
        telegram_ok = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        discord_ok = bool(settings.discord_webhook_url)

        if telegram_ok or discord_ok:
            channels = []
            if telegram_ok:
                channels.append("telegram")
            if discord_ok:
                channels.append("discord")

            return ServiceCheck(
                name="notifications",
                status=ServiceStatus.HEALTHY,
                message=f"Enabled: {', '.join(channels)}"
            )

        return ServiceCheck(
            name="notifications",
            status=ServiceStatus.UNKNOWN,
            message="Not configured"
        )

    async def get_health_report(self, db: Session) -> HealthReport:
        """
        Generate a complete health report.

        Args:
            db: Database session

        Returns:
            HealthReport with all service statuses
        """
        # Run all checks
        db_check = await self.check_database(db)
        oura_check = self.check_oura()
        ai_check = self.check_ai()
        notify_check = self.check_notifications()

        services = {
            "database": db_check,
            "oura": oura_check,
            "ai": ai_check,
            "notifications": notify_check
        }

        # Determine overall status
        statuses = [check.status for check in services.values()]

        if ServiceStatus.UNHEALTHY in statuses:
            overall = ServiceStatus.UNHEALTHY
        elif ServiceStatus.DEGRADED in statuses:
            overall = ServiceStatus.DEGRADED
        elif all(s in (ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN) for s in statuses):
            # Check if critical services are healthy
            if db_check.status == ServiceStatus.HEALTHY:
                overall = ServiceStatus.HEALTHY
            else:
                overall = ServiceStatus.UNHEALTHY
        else:
            overall = ServiceStatus.DEGRADED

        return HealthReport(
            status=overall,
            version=self.VERSION,
            uptime_seconds=self.uptime_seconds,
            started_at=self.started_at,
            timestamp=datetime.utcnow().isoformat(),
            services=services,
            recent_errors=self.get_recent_errors()
        )

    async def send_error_alert(
        self,
        error_type: str,
        message: str,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Send an error alert via configured notification channels.

        Respects cooldown to avoid alert storms.
        """
        if not self.should_alert():
            return

        try:
            from .integrations.notify import get_notification_service

            notifier = get_notification_service()
            if not notifier.enabled_channels:
                return

            alert_text = f"**LifeOS Alert**\n\n"
            alert_text += f"Type: {error_type}\n"
            alert_text += f"Message: {message}\n"
            if context:
                alert_text += f"Context: {context}\n"
            alert_text += f"\nTime: {datetime.utcnow().isoformat()}"

            # Send to all enabled channels
            for channel in notifier.enabled_channels:
                try:
                    if channel.value == "telegram":
                        await notifier.send_telegram(alert_text)
                    elif channel.value == "discord":
                        await notifier.send_discord(alert_text)
                except Exception as e:
                    # Don't fail if alert fails
                    pass

            self.mark_alerted()
        except Exception:
            # Alert system should never break the app
            pass


# Singleton instance
_monitor: Optional[HealthMonitor] = None


def get_health_monitor() -> HealthMonitor:
    """Get or create the health monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
    return _monitor
