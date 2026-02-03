"""
LifeOS Google Calendar Integration

OAuth2 flow and API adapter for syncing calendar events.
Detects meeting patterns and stores events in the database.

API docs: https://developers.google.com/calendar/api/v3/reference
"""

import urllib.parse
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import OAuthToken, CalendarEvent, DataPoint


# Google OAuth2 endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_API = "https://www.googleapis.com/calendar/v3"

# Required scopes for calendar read access
CALENDAR_SCOPES = [
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events.readonly"
]


class CalendarSyncStatus(str, Enum):
    """Status of a calendar sync operation."""
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"
    TOKEN_EXPIRED = "token_expired"


@dataclass
class CalendarSyncResult:
    """Result of a calendar sync operation."""
    status: CalendarSyncStatus
    events_synced: int = 0
    events_updated: int = 0
    events_deleted: int = 0
    date_range: tuple[str, str] = ("", "")
    errors: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.status == CalendarSyncStatus.SUCCESS:
            return f"Synced {self.events_synced} events ({self.date_range[0]} to {self.date_range[1]})"
        return f"Sync {self.status.value}: {', '.join(self.errors) if self.errors else 'Unknown error'}"


class GoogleCalendarClient:
    """
    HTTP client for Google Calendar API.

    Handles OAuth2 authentication and request formatting.
    """

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Google Calendar client.

        Args:
            access_token: OAuth2 access token
            refresh_token: OAuth2 refresh token
            client_id: OAuth2 client ID
            client_secret: OAuth2 client secret
        """
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.client_id = client_id or settings.google_client_id
        self.client_secret = client_secret or settings.google_client_secret
        self._http_client: Optional[httpx.Client] = None

    @property
    def is_configured(self) -> bool:
        """Check if OAuth2 credentials are configured."""
        return bool(self.client_id and self.client_secret)

    @property
    def has_token(self) -> bool:
        """Check if we have an access token."""
        return bool(self.access_token)

    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=GOOGLE_CALENDAR_API,
                headers=self._auth_headers(),
                timeout=30.0
            )
        return self._http_client

    def _auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    def _refresh_access_token(self) -> bool:
        """
        Refresh OAuth2 access token.

        Returns:
            True if refresh succeeded, False otherwise
        """
        if not self.refresh_token or not self.client_id or not self.client_secret:
            return False

        try:
            response = httpx.post(
                GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()
            self.access_token = data["access_token"]

            # Reset HTTP client to use new token
            if self._http_client:
                self._http_client.close()
                self._http_client = None

            return True
        except Exception:
            return False

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        retry_on_401: bool = True
    ) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated request to the Calendar API.

        Args:
            method: HTTP method
            endpoint: API endpoint (e.g., /calendars/primary/events)
            params: Query parameters
            retry_on_401: Whether to retry with refreshed token on 401

        Returns:
            Response JSON or None on error
        """
        try:
            response = self.http_client.request(method, endpoint, params=params)

            if response.status_code == 401 and retry_on_401:
                if self._refresh_access_token():
                    return self._request(method, endpoint, params, retry_on_401=False)
                return None

            response.raise_for_status()
            return response.json()

        except Exception:
            return None

    def get_calendar_list(self) -> Optional[List[Dict]]:
        """
        Get list of calendars accessible by the user.

        Returns:
            List of calendar objects or None on error
        """
        result = self._request("GET", "/users/me/calendarList")
        if result:
            return result.get("items", [])
        return None

    def get_events(
        self,
        calendar_id: str = "primary",
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 250,
        single_events: bool = True
    ) -> Optional[List[Dict]]:
        """
        Get events from a calendar.

        Args:
            calendar_id: Calendar ID (default "primary")
            time_min: Minimum start time
            time_max: Maximum start time
            max_results: Maximum number of events to return
            single_events: Expand recurring events into instances

        Returns:
            List of event objects or None on error
        """
        params = {
            "maxResults": max_results,
            "singleEvents": str(single_events).lower(),
            "orderBy": "startTime"
        }

        if time_min:
            params["timeMin"] = time_min.isoformat() + "Z"
        if time_max:
            params["timeMax"] = time_max.isoformat() + "Z"

        result = self._request("GET", f"/calendars/{calendar_id}/events", params=params)
        if result:
            return result.get("items", [])
        return None

    def close(self):
        """Close the HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


def get_oauth_url(state: Optional[str] = None) -> str:
    """
    Generate the Google OAuth2 authorization URL.

    Args:
        state: Optional state parameter for CSRF protection

    Returns:
        Authorization URL to redirect the user to
    """
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": " ".join(CALENDAR_SCOPES),
        "access_type": "offline",
        "prompt": "consent"  # Force consent to get refresh token
    }

    if state:
        params["state"] = state

    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def exchange_code_for_tokens(code: str) -> Optional[Dict[str, Any]]:
    """
    Exchange authorization code for access and refresh tokens.

    Args:
        code: Authorization code from OAuth callback

    Returns:
        Token response dict or None on error
    """
    try:
        response = httpx.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "redirect_uri": settings.google_redirect_uri,
                "grant_type": "authorization_code"
            },
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def save_oauth_token(
    db: Session,
    token_data: Dict[str, Any],
    user_id: int = 1
) -> OAuthToken:
    """
    Save OAuth tokens to the database.

    Args:
        db: Database session
        token_data: Token response from Google
        user_id: User ID

    Returns:
        Saved OAuthToken object
    """
    # Calculate expiry time
    expires_in = token_data.get("expires_in", 3600)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in)

    # Check for existing token
    existing = db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "google"
    ).first()

    if existing:
        existing.access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            existing.refresh_token = token_data["refresh_token"]
        existing.expires_at = expires_at
        existing.scope = token_data.get("scope", "")
        existing.updated_at = datetime.utcnow()
        db.commit()
        return existing

    # Create new token
    token = OAuthToken(
        user_id=user_id,
        provider="google",
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type", "Bearer"),
        expires_at=expires_at,
        scope=token_data.get("scope", "")
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token


def get_oauth_token(db: Session, user_id: int = 1) -> Optional[OAuthToken]:
    """
    Get stored OAuth token for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        OAuthToken or None if not found
    """
    return db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.provider == "google"
    ).first()


def is_token_expired(token: OAuthToken, buffer_minutes: int = 5) -> bool:
    """
    Check if an OAuth token is expired.

    Args:
        token: OAuthToken object
        buffer_minutes: Minutes before actual expiry to consider expired

    Returns:
        True if token is expired or will expire soon
    """
    if not token.expires_at:
        return True
    return datetime.utcnow() >= (token.expires_at - timedelta(minutes=buffer_minutes))


class CalendarSyncService:
    """
    Service for syncing Google Calendar events to the database.
    """

    def __init__(self, db: Session, user_id: int = 1):
        """
        Initialize the sync service.

        Args:
            db: Database session
            user_id: User ID
        """
        self.db = db
        self.user_id = user_id
        self._client: Optional[GoogleCalendarClient] = None

    def _get_client(self) -> Optional[GoogleCalendarClient]:
        """Get or create a calendar client with valid token."""
        if self._client:
            return self._client

        token = get_oauth_token(self.db, self.user_id)
        if not token:
            return None

        # Check if token needs refresh
        if is_token_expired(token):
            client = GoogleCalendarClient(
                access_token=token.access_token,
                refresh_token=token.refresh_token
            )
            if client._refresh_access_token():
                # Update token in database
                token.access_token = client.access_token
                token.expires_at = datetime.utcnow() + timedelta(hours=1)
                self.db.commit()
            else:
                return None

        self._client = GoogleCalendarClient(
            access_token=token.access_token,
            refresh_token=token.refresh_token
        )
        return self._client

    def _parse_event_time(self, event_time: Dict) -> tuple[datetime, bool]:
        """
        Parse event time from Google Calendar format.

        Args:
            event_time: Dict with 'dateTime' or 'date' key

        Returns:
            Tuple of (datetime, is_all_day)
        """
        if "dateTime" in event_time:
            # Regular event with time
            dt_str = event_time["dateTime"]
            # Handle timezone offset
            if "+" in dt_str or dt_str.endswith("Z"):
                # Remove timezone for simplicity (store as UTC)
                dt_str = dt_str.replace("Z", "").split("+")[0].split("-")[0]
                if "T" in dt_str:
                    return datetime.fromisoformat(dt_str), False
            return datetime.fromisoformat(dt_str), False
        elif "date" in event_time:
            # All-day event
            return datetime.strptime(event_time["date"], "%Y-%m-%d"), True
        return datetime.now(), False

    def _upsert_event(self, event_data: Dict, calendar_id: str) -> CalendarEvent:
        """
        Insert or update a calendar event.

        Args:
            event_data: Event data from Google Calendar API
            calendar_id: Calendar ID

        Returns:
            CalendarEvent object
        """
        event_id = event_data["id"]

        # Parse times
        start_time, all_day = self._parse_event_time(event_data.get("start", {}))
        end_time, _ = self._parse_event_time(event_data.get("end", {}))

        # Get attendee count
        attendees = event_data.get("attendees", [])
        attendees_count = len(attendees)

        # Check for existing event
        existing = self.db.query(CalendarEvent).filter(
            CalendarEvent.event_id == event_id,
            CalendarEvent.user_id == self.user_id
        ).first()

        if existing:
            existing.summary = event_data.get("summary", "")
            existing.description = event_data.get("description")
            existing.location = event_data.get("location")
            existing.start_time = start_time
            existing.end_time = end_time
            existing.all_day = all_day
            existing.status = event_data.get("status", "confirmed")
            existing.organizer = event_data.get("organizer", {}).get("email")
            existing.attendees_count = attendees_count
            existing.is_recurring = "recurringEventId" in event_data
            existing.recurring_event_id = event_data.get("recurringEventId")
            existing.synced_at = datetime.utcnow()
            return existing

        # Create new event
        event = CalendarEvent(
            user_id=self.user_id,
            event_id=event_id,
            calendar_id=calendar_id,
            summary=event_data.get("summary", ""),
            description=event_data.get("description"),
            location=event_data.get("location"),
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            status=event_data.get("status", "confirmed"),
            organizer=event_data.get("organizer", {}).get("email"),
            attendees_count=attendees_count,
            is_recurring="recurringEventId" in event_data,
            recurring_event_id=event_data.get("recurringEventId")
        )
        self.db.add(event)
        return event

    def sync(
        self,
        days_back: int = 7,
        days_forward: int = 14,
        calendar_id: str = "primary"
    ) -> CalendarSyncResult:
        """
        Sync calendar events for a date range.

        Args:
            days_back: Number of days in the past to sync
            days_forward: Number of days in the future to sync
            calendar_id: Calendar ID to sync (default "primary")

        Returns:
            CalendarSyncResult with sync statistics
        """
        client = self._get_client()

        if not client:
            return CalendarSyncResult(
                status=CalendarSyncStatus.NOT_CONFIGURED,
                errors=["Google Calendar not connected"]
            )

        if not client.is_configured:
            return CalendarSyncResult(
                status=CalendarSyncStatus.NOT_CONFIGURED,
                errors=["Google OAuth credentials not configured"]
            )

        # Calculate date range
        now = datetime.utcnow()
        time_min = now - timedelta(days=days_back)
        time_max = now + timedelta(days=days_forward)

        # Fetch events
        events = client.get_events(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max
        )

        if events is None:
            return CalendarSyncResult(
                status=CalendarSyncStatus.FAILED,
                errors=["Failed to fetch events from Google Calendar"]
            )

        # Sync events to database
        synced = 0
        updated = 0
        errors = []

        for event_data in events:
            try:
                # Skip cancelled events
                if event_data.get("status") == "cancelled":
                    continue

                existing = self.db.query(CalendarEvent).filter(
                    CalendarEvent.event_id == event_data["id"],
                    CalendarEvent.user_id == self.user_id
                ).first()

                self._upsert_event(event_data, calendar_id)

                if existing:
                    updated += 1
                else:
                    synced += 1

            except Exception as e:
                errors.append(f"Error syncing event {event_data.get('id', 'unknown')}: {str(e)}")

        self.db.commit()

        # Also create meeting density data points for pattern detection
        self._create_meeting_density_datapoints(time_min, time_max)

        status = CalendarSyncStatus.SUCCESS if not errors else CalendarSyncStatus.PARTIAL

        return CalendarSyncResult(
            status=status,
            events_synced=synced,
            events_updated=updated,
            date_range=(time_min.strftime("%Y-%m-%d"), time_max.strftime("%Y-%m-%d")),
            errors=errors
        )

    def _create_meeting_density_datapoints(
        self,
        start_date: datetime,
        end_date: datetime
    ):
        """
        Create DataPoints for meeting density analysis.

        Calculates daily meeting hours and count for pattern detection.
        """
        current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)

        while current <= end_date:
            date_str = current.strftime("%Y-%m-%d")
            next_day = current + timedelta(days=1)

            # Get events for this day
            events = self.db.query(CalendarEvent).filter(
                CalendarEvent.user_id == self.user_id,
                CalendarEvent.start_time >= current,
                CalendarEvent.start_time < next_day,
                CalendarEvent.status != "cancelled"
            ).all()

            if events:
                # Calculate meeting hours
                total_minutes = 0
                meeting_count = 0

                for event in events:
                    if not event.all_day:
                        duration = (event.end_time - event.start_time).total_seconds() / 60
                        total_minutes += duration
                        meeting_count += 1

                meeting_hours = total_minutes / 60

                # Create or update DataPoint for meeting density
                existing = self.db.query(DataPoint).filter(
                    DataPoint.date == date_str,
                    DataPoint.type == "meeting_density",
                    DataPoint.source == "calendar"
                ).first()

                if existing:
                    existing.value = meeting_hours
                    existing.extra_data = {
                        "meeting_count": meeting_count,
                        "total_minutes": total_minutes
                    }
                    existing.timestamp = datetime.utcnow()
                else:
                    dp = DataPoint(
                        user_id=self.user_id,
                        source="calendar",
                        type="meeting_density",
                        date=date_str,
                        value=meeting_hours,
                        extra_data={
                            "meeting_count": meeting_count,
                            "total_minutes": total_minutes
                        }
                    )
                    self.db.add(dp)

            current = next_day

        self.db.commit()

    def get_meeting_stats(self, date: str) -> Dict[str, Any]:
        """
        Get meeting statistics for a specific date.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Dict with meeting stats
        """
        start = datetime.strptime(date, "%Y-%m-%d")
        end = start + timedelta(days=1)

        events = self.db.query(CalendarEvent).filter(
            CalendarEvent.user_id == self.user_id,
            CalendarEvent.start_time >= start,
            CalendarEvent.start_time < end,
            CalendarEvent.status != "cancelled"
        ).all()

        meeting_count = 0
        total_minutes = 0
        back_to_back = 0
        early_meetings = 0  # Before 9 AM
        late_meetings = 0   # After 6 PM

        sorted_events = sorted(events, key=lambda e: e.start_time)

        for i, event in enumerate(sorted_events):
            if event.all_day:
                continue

            meeting_count += 1
            duration = (event.end_time - event.start_time).total_seconds() / 60
            total_minutes += duration

            # Check for early/late meetings
            if event.start_time.hour < 9:
                early_meetings += 1
            if event.start_time.hour >= 18:
                late_meetings += 1

            # Check for back-to-back meetings
            if i > 0:
                prev_event = sorted_events[i - 1]
                if not prev_event.all_day:
                    gap = (event.start_time - prev_event.end_time).total_seconds() / 60
                    if gap <= 15:  # 15 minutes or less gap
                        back_to_back += 1

        return {
            "date": date,
            "meeting_count": meeting_count,
            "total_hours": round(total_minutes / 60, 1),
            "back_to_back_count": back_to_back,
            "early_meetings": early_meetings,
            "late_meetings": late_meetings,
            "events": [
                {
                    "summary": e.summary,
                    "start": e.start_time.isoformat(),
                    "end": e.end_time.isoformat(),
                    "attendees": e.attendees_count
                }
                for e in sorted_events if not e.all_day
            ]
        }


def get_calendar_sync_service(db: Session, user_id: int = 1) -> CalendarSyncService:
    """Factory function for CalendarSyncService."""
    return CalendarSyncService(db, user_id)
