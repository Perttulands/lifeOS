"""
LifeOS Historical Data Backfill

Handles importing 30-90 days of historical data on first connect.
Supports Oura and Google Calendar with progress tracking.
"""
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum
import time

from sqlalchemy.orm import Session

from .models import DataPoint, CalendarEvent
from .integrations.oura import OuraSyncService, OuraDataType
from .integrations.calendar import CalendarSyncService, CalendarSyncStatus


class BackfillSource(str, Enum):
    """Data sources that support backfill."""
    OURA = "oura"
    CALENDAR = "calendar"


class BackfillStatus(str, Enum):
    """Status of a backfill operation."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class BackfillProgress:
    """Progress tracking for backfill operations."""
    source: BackfillSource
    status: BackfillStatus
    total_days: int
    completed_days: int
    records_synced: int
    current_date: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

    @property
    def percent_complete(self) -> float:
        """Calculate percentage complete."""
        if self.total_days == 0:
            return 0.0
        return round((self.completed_days / self.total_days) * 100, 1)

    @property
    def elapsed_seconds(self) -> float:
        """Get elapsed time in seconds."""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at or datetime.utcnow()
        return (end_time - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "source": self.source.value,
            "status": self.status.value,
            "total_days": self.total_days,
            "completed_days": self.completed_days,
            "records_synced": self.records_synced,
            "percent_complete": self.percent_complete,
            "current_date": self.current_date,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_seconds": self.elapsed_seconds,
            "errors": self.errors
        }


@dataclass
class BackfillResult:
    """Result of a complete backfill operation."""
    oura: Optional[BackfillProgress] = None
    calendar: Optional[BackfillProgress] = None

    @property
    def total_records(self) -> int:
        """Get total records synced across all sources."""
        total = 0
        if self.oura:
            total += self.oura.records_synced
        if self.calendar:
            total += self.calendar.records_synced
        return total

    @property
    def all_completed(self) -> bool:
        """Check if all backfills completed successfully."""
        statuses = []
        if self.oura:
            statuses.append(self.oura.status in (BackfillStatus.COMPLETED, BackfillStatus.PARTIAL))
        if self.calendar:
            statuses.append(self.calendar.status in (BackfillStatus.COMPLETED, BackfillStatus.PARTIAL))
        return all(statuses) if statuses else False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "oura": self.oura.to_dict() if self.oura else None,
            "calendar": self.calendar.to_dict() if self.calendar else None,
            "total_records": self.total_records,
            "all_completed": self.all_completed
        }


# Global progress state for async tracking
_current_progress: Dict[str, BackfillProgress] = {}


def get_current_progress(source: BackfillSource) -> Optional[BackfillProgress]:
    """Get current progress for a backfill operation."""
    return _current_progress.get(source.value)


def clear_progress(source: BackfillSource):
    """Clear progress tracking for a source."""
    if source.value in _current_progress:
        del _current_progress[source.value]


class OuraBackfillService:
    """
    Service for backfilling Oura historical data.

    Syncs data in batches with progress tracking.
    """

    # Maximum days Oura API allows in one request
    MAX_BATCH_DAYS = 30

    def __init__(
        self,
        db: Session,
        progress_callback: Optional[Callable[[BackfillProgress], None]] = None
    ):
        """
        Initialize Oura backfill service.

        Args:
            db: Database session
            progress_callback: Optional callback for progress updates
        """
        self.db = db
        self.sync_service = OuraSyncService(db)
        self.progress_callback = progress_callback

    def backfill(
        self,
        days: int = 90,
        batch_size: int = 7
    ) -> BackfillProgress:
        """
        Backfill Oura data for the specified number of days.

        Args:
            days: Number of days to backfill (default 90, max 365)
            batch_size: Days per batch to avoid API limits

        Returns:
            BackfillProgress with results
        """
        days = min(days, 365)  # Cap at 1 year

        progress = BackfillProgress(
            source=BackfillSource.OURA,
            status=BackfillStatus.IN_PROGRESS,
            total_days=days,
            completed_days=0,
            records_synced=0,
            started_at=datetime.utcnow()
        )
        _current_progress[BackfillSource.OURA.value] = progress

        try:
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            # Process in batches
            current_start = start_date
            while current_start < end_date:
                current_end = min(current_start + timedelta(days=batch_size - 1), end_date)

                progress.current_date = current_start.isoformat()
                self._update_progress(progress)

                # Sync all data types for this batch
                results = self.sync_service.sync_all(
                    start_date=current_start.isoformat(),
                    end_date=current_end.isoformat()
                )

                # Count records
                for result in results:
                    progress.records_synced += result.records_synced
                    if result.errors:
                        progress.errors.extend(result.errors)

                # Update progress
                batch_days = (current_end - current_start).days + 1
                progress.completed_days += batch_days
                self._update_progress(progress)

                # Move to next batch
                current_start = current_end + timedelta(days=1)

                # Small delay to avoid rate limiting
                time.sleep(0.1)

            # Mark as completed
            progress.status = BackfillStatus.COMPLETED if not progress.errors else BackfillStatus.PARTIAL
            progress.completed_at = datetime.utcnow()
            progress.current_date = None

        except Exception as e:
            progress.status = BackfillStatus.FAILED
            progress.errors.append(str(e))
            progress.completed_at = datetime.utcnow()

        self._update_progress(progress)
        return progress

    def _update_progress(self, progress: BackfillProgress):
        """Update progress and call callback if set."""
        _current_progress[BackfillSource.OURA.value] = progress
        if self.progress_callback:
            self.progress_callback(progress)


class CalendarBackfillService:
    """
    Service for backfilling Google Calendar historical data.
    """

    def __init__(
        self,
        db: Session,
        user_id: int = 1,
        progress_callback: Optional[Callable[[BackfillProgress], None]] = None
    ):
        """
        Initialize Calendar backfill service.

        Args:
            db: Database session
            user_id: User ID for calendar sync
            progress_callback: Optional callback for progress updates
        """
        self.db = db
        self.user_id = user_id
        self.sync_service = CalendarSyncService(db, user_id)
        self.progress_callback = progress_callback

    def backfill(
        self,
        days_back: int = 90,
        days_forward: int = 30
    ) -> BackfillProgress:
        """
        Backfill calendar events for the specified period.

        Args:
            days_back: Days of history to import (default 90)
            days_forward: Days of future events (default 30)

        Returns:
            BackfillProgress with results
        """
        total_days = days_back + days_forward

        progress = BackfillProgress(
            source=BackfillSource.CALENDAR,
            status=BackfillStatus.IN_PROGRESS,
            total_days=total_days,
            completed_days=0,
            records_synced=0,
            started_at=datetime.utcnow()
        )
        _current_progress[BackfillSource.CALENDAR.value] = progress

        try:
            progress.current_date = f"Syncing {days_back} days back, {days_forward} days forward"
            self._update_progress(progress)

            # Sync calendar events
            result = self.sync_service.sync(
                days_back=days_back,
                days_forward=days_forward
            )

            if result.status == CalendarSyncStatus.NOT_CONFIGURED:
                progress.status = BackfillStatus.FAILED
                progress.errors.append("Google Calendar not configured")
            elif result.status == CalendarSyncStatus.FAILED:
                progress.status = BackfillStatus.FAILED
                progress.errors.extend(result.errors)
            else:
                progress.records_synced = result.events_synced + result.events_updated
                progress.completed_days = total_days
                progress.status = BackfillStatus.COMPLETED if not result.errors else BackfillStatus.PARTIAL
                if result.errors:
                    progress.errors.extend(result.errors)

            progress.completed_at = datetime.utcnow()
            progress.current_date = None

        except Exception as e:
            progress.status = BackfillStatus.FAILED
            progress.errors.append(str(e))
            progress.completed_at = datetime.utcnow()

        self._update_progress(progress)
        return progress

    def _update_progress(self, progress: BackfillProgress):
        """Update progress and call callback if set."""
        _current_progress[BackfillSource.CALENDAR.value] = progress
        if self.progress_callback:
            self.progress_callback(progress)


class BackfillManager:
    """
    Manages backfill operations for all data sources.

    Provides unified interface for first-connect historical imports.
    """

    def __init__(self, db: Session, user_id: int = 1):
        """
        Initialize backfill manager.

        Args:
            db: Database session
            user_id: User ID for calendar operations
        """
        self.db = db
        self.user_id = user_id

    def needs_backfill(self, source: BackfillSource) -> bool:
        """
        Check if a source needs initial backfill.

        Returns True if there's no historical data for this source.
        """
        cutoff = (date.today() - timedelta(days=7)).isoformat()

        if source == BackfillSource.OURA:
            count = self.db.query(DataPoint).filter(
                DataPoint.source == "oura",
                DataPoint.date < cutoff
            ).count()
            return count < 7  # Need at least a week of historical data

        elif source == BackfillSource.CALENDAR:
            count = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.start_time < datetime.strptime(cutoff, "%Y-%m-%d")
            ).count()
            return count < 5  # Need some historical events

        return False

    def get_data_summary(self) -> Dict[str, Any]:
        """
        Get summary of existing data for each source.

        Returns counts and date ranges for all sources.
        """
        # Oura data summary
        oura_count = self.db.query(DataPoint).filter(
            DataPoint.source == "oura"
        ).count()

        oura_earliest = self.db.query(DataPoint.date).filter(
            DataPoint.source == "oura"
        ).order_by(DataPoint.date.asc()).first()

        oura_latest = self.db.query(DataPoint.date).filter(
            DataPoint.source == "oura"
        ).order_by(DataPoint.date.desc()).first()

        # Calendar data summary
        calendar_count = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == self.user_id
        ).count()

        calendar_earliest = self.db.query(CalendarEvent.start_time).filter(
            CalendarEvent.user_id == self.user_id
        ).order_by(CalendarEvent.start_time.asc()).first()

        calendar_latest = self.db.query(CalendarEvent.start_time).filter(
            CalendarEvent.user_id == self.user_id
        ).order_by(CalendarEvent.start_time.desc()).first()

        return {
            "oura": {
                "record_count": oura_count,
                "earliest_date": oura_earliest[0] if oura_earliest else None,
                "latest_date": oura_latest[0] if oura_latest else None,
                "needs_backfill": self.needs_backfill(BackfillSource.OURA)
            },
            "calendar": {
                "event_count": calendar_count,
                "earliest_date": calendar_earliest[0].isoformat() if calendar_earliest else None,
                "latest_date": calendar_latest[0].isoformat() if calendar_latest else None,
                "needs_backfill": self.needs_backfill(BackfillSource.CALENDAR)
            }
        }

    def run_full_backfill(
        self,
        oura_days: int = 90,
        calendar_days_back: int = 90,
        calendar_days_forward: int = 30,
        progress_callback: Optional[Callable[[BackfillResult], None]] = None
    ) -> BackfillResult:
        """
        Run full backfill for all configured sources.

        Args:
            oura_days: Days of Oura history to import
            calendar_days_back: Days of calendar history
            calendar_days_forward: Days of future calendar events
            progress_callback: Optional callback for progress updates

        Returns:
            BackfillResult with progress for all sources
        """
        result = BackfillResult()

        # Backfill Oura if configured
        from .config import settings
        if settings.oura_token:
            oura_service = OuraBackfillService(self.db)
            result.oura = oura_service.backfill(days=oura_days)

        if progress_callback:
            progress_callback(result)

        # Backfill Calendar if configured
        if settings.google_client_id and settings.google_client_secret:
            from .integrations.calendar import get_oauth_token
            token = get_oauth_token(self.db, self.user_id)
            if token:
                calendar_service = CalendarBackfillService(self.db, self.user_id)
                result.calendar = calendar_service.backfill(
                    days_back=calendar_days_back,
                    days_forward=calendar_days_forward
                )

        if progress_callback:
            progress_callback(result)

        return result


def get_backfill_manager(db: Session, user_id: int = 1) -> BackfillManager:
    """Factory function for BackfillManager."""
    return BackfillManager(db, user_id)
