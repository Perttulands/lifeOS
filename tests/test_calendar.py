"""
Tests for Google Calendar Integration.

Tests the OAuth2 flow, event sync, and meeting statistics.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import httpx
import respx

from src.integrations.calendar import (
    GoogleCalendarClient,
    CalendarSyncService,
    CalendarSyncStatus,
    get_oauth_url,
    exchange_code_for_tokens,
    save_oauth_token,
    get_oauth_token,
    is_token_expired,
    GOOGLE_AUTH_URL,
    GOOGLE_TOKEN_URL,
    CALENDAR_SCOPES,
)
from src.models import OAuthToken, CalendarEvent, DataPoint


# === OAuth URL Generation Tests ===

class TestOAuthUrlGeneration:
    """Tests for OAuth URL generation."""

    def test_get_oauth_url_includes_client_id(self):
        """Test OAuth URL includes client ID."""
        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_client_id"
            mock_settings.google_redirect_uri = "http://localhost:8080/callback"

            url = get_oauth_url()

            assert "client_id=test_client_id" in url

    def test_get_oauth_url_includes_scopes(self):
        """Test OAuth URL includes required scopes."""
        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_client_id"
            mock_settings.google_redirect_uri = "http://localhost:8080/callback"

            url = get_oauth_url()

            assert "calendar.readonly" in url

    def test_get_oauth_url_includes_state(self):
        """Test OAuth URL includes state parameter when provided."""
        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_client_id"
            mock_settings.google_redirect_uri = "http://localhost:8080/callback"

            url = get_oauth_url(state="csrf_token_123")

            assert "state=csrf_token_123" in url


# === Token Exchange Tests ===

class TestTokenExchange:
    """Tests for OAuth token exchange."""

    @respx.mock
    def test_exchange_code_success(self):
        """Test successful code exchange."""
        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(200, json={
                "access_token": "test_access_token",
                "refresh_token": "test_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer"
            })
        )

        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_client_id"
            mock_settings.google_client_secret = "test_secret"
            mock_settings.google_redirect_uri = "http://localhost:8080/callback"

            result = exchange_code_for_tokens("auth_code_123")

        assert result is not None
        assert result["access_token"] == "test_access_token"
        assert result["refresh_token"] == "test_refresh_token"

    @respx.mock
    def test_exchange_code_failure(self):
        """Test code exchange failure."""
        respx.post(GOOGLE_TOKEN_URL).mock(
            return_value=httpx.Response(400, json={
                "error": "invalid_grant"
            })
        )

        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_client_id"
            mock_settings.google_client_secret = "test_secret"
            mock_settings.google_redirect_uri = "http://localhost:8080/callback"

            result = exchange_code_for_tokens("invalid_code")

        assert result is None


# === Token Storage Tests ===

class TestTokenStorage:
    """Tests for OAuth token database storage."""

    def test_save_new_token(self, db_session):
        """Test saving a new OAuth token."""
        token_data = {
            "access_token": "test_access",
            "refresh_token": "test_refresh",
            "expires_in": 3600,
            "scope": "calendar.readonly"
        }

        token = save_oauth_token(db_session, token_data)

        assert token.id is not None
        assert token.access_token == "test_access"
        assert token.refresh_token == "test_refresh"
        assert token.provider == "google"

    def test_update_existing_token(self, db_session):
        """Test updating an existing OAuth token."""
        # Create initial token
        initial_token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="old_access",
            refresh_token="old_refresh"
        )
        db_session.add(initial_token)
        db_session.commit()

        # Update with new token data
        new_token_data = {
            "access_token": "new_access",
            "refresh_token": "new_refresh",
            "expires_in": 3600
        }

        updated = save_oauth_token(db_session, new_token_data)

        assert updated.id == initial_token.id
        assert updated.access_token == "new_access"
        assert updated.refresh_token == "new_refresh"

    def test_get_oauth_token(self, db_session):
        """Test retrieving OAuth token."""
        # Create token
        token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="test_access",
            refresh_token="test_refresh"
        )
        db_session.add(token)
        db_session.commit()

        # Retrieve token
        retrieved = get_oauth_token(db_session)

        assert retrieved is not None
        assert retrieved.access_token == "test_access"

    def test_get_oauth_token_not_found(self, db_session):
        """Test retrieving non-existent token."""
        retrieved = get_oauth_token(db_session)

        assert retrieved is None


# === Token Expiry Tests ===

class TestTokenExpiry:
    """Tests for token expiry checking."""

    def test_token_not_expired(self):
        """Test token that is not expired."""
        token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="test",
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )

        assert is_token_expired(token) is False

    def test_token_expired(self):
        """Test token that is expired."""
        token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="test",
            expires_at=datetime.utcnow() - timedelta(hours=1)
        )

        assert is_token_expired(token) is True

    def test_token_expired_with_buffer(self):
        """Test token expiring within buffer period."""
        token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="test",
            expires_at=datetime.utcnow() + timedelta(minutes=3)  # Within 5 min buffer
        )

        assert is_token_expired(token, buffer_minutes=5) is True

    def test_token_no_expiry(self):
        """Test token with no expiry time."""
        token = OAuthToken(
            user_id=1,
            provider="google",
            access_token="test",
            expires_at=None
        )

        assert is_token_expired(token) is True


# === Calendar Client Tests ===

class TestGoogleCalendarClient:
    """Tests for GoogleCalendarClient."""

    def test_client_not_configured(self):
        """Test client without credentials."""
        client = GoogleCalendarClient()

        assert client.is_configured is False
        assert client.has_token is False

    def test_client_configured(self):
        """Test client with credentials."""
        client = GoogleCalendarClient(
            access_token="test_token",
            client_id="test_id",
            client_secret="test_secret"
        )

        assert client.is_configured is True
        assert client.has_token is True

    @respx.mock
    def test_get_calendar_list_success(self):
        """Test fetching calendar list."""
        respx.get("https://www.googleapis.com/calendar/v3/users/me/calendarList").mock(
            return_value=httpx.Response(200, json={
                "items": [
                    {"id": "primary", "summary": "Primary Calendar"},
                    {"id": "work@example.com", "summary": "Work"}
                ]
            })
        )

        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_id"
            mock_settings.google_client_secret = "test_secret"

            client = GoogleCalendarClient(access_token="test_token")
            calendars = client.get_calendar_list()
            client.close()

        assert calendars is not None
        assert len(calendars) == 2
        assert calendars[0]["id"] == "primary"

    @respx.mock
    def test_get_events_success(self):
        """Test fetching calendar events."""
        respx.get("https://www.googleapis.com/calendar/v3/calendars/primary/events").mock(
            return_value=httpx.Response(200, json={
                "items": [
                    {
                        "id": "event1",
                        "summary": "Team Meeting",
                        "start": {"dateTime": "2026-02-03T10:00:00Z"},
                        "end": {"dateTime": "2026-02-03T11:00:00Z"}
                    }
                ]
            })
        )

        with patch('src.integrations.calendar.settings') as mock_settings:
            mock_settings.google_client_id = "test_id"
            mock_settings.google_client_secret = "test_secret"

            client = GoogleCalendarClient(access_token="test_token")
            events = client.get_events(calendar_id="primary")
            client.close()

        assert events is not None
        assert len(events) == 1
        assert events[0]["summary"] == "Team Meeting"


# === Calendar Sync Service Tests ===

class TestCalendarSyncService:
    """Tests for CalendarSyncService."""

    def test_sync_not_configured(self, db_session):
        """Test sync when not configured."""
        service = CalendarSyncService(db_session)
        result = service.sync()

        assert result.status == CalendarSyncStatus.NOT_CONFIGURED

    def test_get_meeting_stats_empty(self, db_session):
        """Test meeting stats with no events."""
        service = CalendarSyncService(db_session)
        stats = service.get_meeting_stats("2026-02-03")

        assert stats["date"] == "2026-02-03"
        assert stats["meeting_count"] == 0
        assert stats["total_hours"] == 0

    def test_get_meeting_stats_with_events(self, db_session):
        """Test meeting stats with events."""
        # Create test events
        event1 = CalendarEvent(
            user_id=1,
            event_id="event1",
            calendar_id="primary",
            summary="Morning Meeting",
            start_time=datetime(2026, 2, 3, 9, 0),
            end_time=datetime(2026, 2, 3, 10, 0),
            status="confirmed"
        )
        event2 = CalendarEvent(
            user_id=1,
            event_id="event2",
            calendar_id="primary",
            summary="Afternoon Meeting",
            start_time=datetime(2026, 2, 3, 14, 0),
            end_time=datetime(2026, 2, 3, 15, 30),
            status="confirmed"
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        service = CalendarSyncService(db_session)
        stats = service.get_meeting_stats("2026-02-03")

        assert stats["meeting_count"] == 2
        assert stats["total_hours"] == 2.5  # 1h + 1.5h
        assert stats["back_to_back_count"] == 0

    def test_detect_back_to_back_meetings(self, db_session):
        """Test back-to-back meeting detection."""
        # Create back-to-back events
        event1 = CalendarEvent(
            user_id=1,
            event_id="event1",
            calendar_id="primary",
            summary="Meeting 1",
            start_time=datetime(2026, 2, 3, 9, 0),
            end_time=datetime(2026, 2, 3, 10, 0),
            status="confirmed"
        )
        event2 = CalendarEvent(
            user_id=1,
            event_id="event2",
            calendar_id="primary",
            summary="Meeting 2",
            start_time=datetime(2026, 2, 3, 10, 0),  # Starts right after event1
            end_time=datetime(2026, 2, 3, 11, 0),
            status="confirmed"
        )
        db_session.add_all([event1, event2])
        db_session.commit()

        service = CalendarSyncService(db_session)
        stats = service.get_meeting_stats("2026-02-03")

        assert stats["back_to_back_count"] == 1

    def test_detect_early_late_meetings(self, db_session):
        """Test early and late meeting detection."""
        # Create early and late events
        early = CalendarEvent(
            user_id=1,
            event_id="early",
            calendar_id="primary",
            summary="Early Meeting",
            start_time=datetime(2026, 2, 3, 7, 0),  # Before 9 AM
            end_time=datetime(2026, 2, 3, 8, 0),
            status="confirmed"
        )
        late = CalendarEvent(
            user_id=1,
            event_id="late",
            calendar_id="primary",
            summary="Late Meeting",
            start_time=datetime(2026, 2, 3, 19, 0),  # After 6 PM
            end_time=datetime(2026, 2, 3, 20, 0),
            status="confirmed"
        )
        db_session.add_all([early, late])
        db_session.commit()

        service = CalendarSyncService(db_session)
        stats = service.get_meeting_stats("2026-02-03")

        assert stats["early_meetings"] == 1
        assert stats["late_meetings"] == 1


# === Fixtures ===

@pytest.fixture
def db_session():
    """Create a test database session."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from src.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()
