"""
Tests for Oura integration.

Tests the OuraClient and OuraSyncService classes.
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import patch, MagicMock
import json

import httpx
import respx

from src.integrations.oura import (
    OuraClient,
    OuraSyncService,
    OuraToken,
    OuraDataType,
    SyncResult,
    sync_oura_data,
)
from src.database import Base, engine, SessionLocal
from src.models import DataPoint


# === Fixtures ===

@pytest.fixture(scope="function")
def db():
    """Create a fresh database for each test."""
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def mock_sleep_response():
    """Sample Oura sleep API response."""
    return {
        "data": [
            {
                "id": "sleep_001",
                "day": "2026-02-03",
                "score": 85,
                "timestamp": "2026-02-03T07:30:00+00:00",
                "total_sleep_duration": 28800,  # 8 hours in seconds
                "contributors": {
                    "deep_sleep": 75,
                    "rem_sleep": 80,
                    "light_sleep": 85,
                    "efficiency": 90,
                    "latency": 85,
                    "restfulness": 80,
                    "timing": 75,
                }
            }
        ]
    }


@pytest.fixture
def mock_activity_response():
    """Sample Oura activity API response."""
    return {
        "data": [
            {
                "id": "activity_001",
                "day": "2026-02-03",
                "score": 78,
                "timestamp": "2026-02-03T23:59:59+00:00",
                "active_calories": 450,
                "total_calories": 2200,
                "steps": 8500,
                "equivalent_walking_distance": 7000,
                "high_activity_time": 1800,
                "medium_activity_time": 3600,
                "low_activity_time": 7200,
                "sedentary_time": 28800,
                "resting_time": 21600,
                "contributors": {
                    "meet_daily_targets": 80,
                    "move_every_hour": 75,
                    "recovery_time": 85,
                    "stay_active": 70,
                    "training_frequency": 65,
                    "training_volume": 60,
                }
            }
        ]
    }


@pytest.fixture
def mock_readiness_response():
    """Sample Oura readiness API response."""
    return {
        "data": [
            {
                "id": "readiness_001",
                "day": "2026-02-03",
                "score": 82,
                "timestamp": "2026-02-03T06:00:00+00:00",
                "temperature_deviation": 0.2,
                "temperature_trend_deviation": -0.1,
                "contributors": {
                    "activity_balance": 80,
                    "body_temperature": 85,
                    "hrv_balance": 78,
                    "previous_day_activity": 75,
                    "previous_night": 88,
                    "recovery_index": 82,
                    "resting_heart_rate": 90,
                    "sleep_balance": 85,
                }
            }
        ]
    }


# === OuraToken Tests ===

class TestOuraToken:
    """Tests for OuraToken dataclass."""

    def test_token_not_expired_when_no_expiry(self):
        """PAT tokens without expiry should never be marked expired."""
        token = OuraToken(access_token="test_token")
        assert not token.is_expired

    def test_token_not_expired_when_future(self):
        """Token with future expiry should not be expired."""
        future = datetime.utcnow() + timedelta(hours=1)
        token = OuraToken(access_token="test", expires_at=future)
        assert not token.is_expired

    def test_token_expired_with_buffer(self):
        """Token expiring within 5 minutes should be marked expired."""
        soon = datetime.utcnow() + timedelta(minutes=3)
        token = OuraToken(access_token="test", expires_at=soon)
        assert token.is_expired

    def test_token_expired_when_past(self):
        """Token with past expiry should be expired."""
        past = datetime.utcnow() - timedelta(hours=1)
        token = OuraToken(access_token="test", expires_at=past)
        assert token.is_expired


# === OuraClient Tests ===

class TestOuraClient:
    """Tests for OuraClient HTTP operations."""

    @respx.mock
    def test_get_daily_sleep_success(self, mock_sleep_response):
        """Test fetching sleep data successfully."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=mock_sleep_response)
        )

        client = OuraClient(access_token="test_token")
        result = client.get_daily_sleep("2026-02-03")

        assert result is not None
        assert len(result) == 1
        assert result[0]["score"] == 85
        assert result[0]["day"] == "2026-02-03"

        client.close()

    @respx.mock
    def test_get_daily_activity_success(self, mock_activity_response):
        """Test fetching activity data successfully."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_activity").mock(
            return_value=httpx.Response(200, json=mock_activity_response)
        )

        client = OuraClient(access_token="test_token")
        result = client.get_daily_activity("2026-02-03")

        assert result is not None
        assert len(result) == 1
        assert result[0]["score"] == 78
        assert result[0]["steps"] == 8500

        client.close()

    @respx.mock
    def test_get_daily_readiness_success(self, mock_readiness_response):
        """Test fetching readiness data successfully."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_readiness").mock(
            return_value=httpx.Response(200, json=mock_readiness_response)
        )

        client = OuraClient(access_token="test_token")
        result = client.get_daily_readiness("2026-02-03")

        assert result is not None
        assert len(result) == 1
        assert result[0]["score"] == 82

        client.close()

    @respx.mock
    def test_api_error_returns_none(self):
        """Test that API errors return None gracefully."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        client = OuraClient(access_token="test_token")
        result = client.get_daily_sleep("2026-02-03")

        assert result is None
        client.close()

    @respx.mock
    def test_token_refresh_on_401(self, mock_sleep_response):
        """Test that 401 triggers token refresh."""
        # First request returns 401, after refresh returns success
        route = respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep")
        route.side_effect = [
            httpx.Response(401, json={"error": "Unauthorized"}),
            httpx.Response(200, json=mock_sleep_response),
        ]

        # Mock the token refresh endpoint
        respx.post("https://api.ouraring.com/oauth/token").mock(
            return_value=httpx.Response(200, json={
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_in": 86400,
                "token_type": "Bearer"
            })
        )

        client = OuraClient(
            access_token="old_token",
            refresh_token="old_refresh",
            client_id="client_id",
            client_secret="client_secret"
        )
        result = client.get_daily_sleep("2026-02-03")

        assert result is not None
        assert client.token.access_token == "new_access_token"
        client.close()

    @respx.mock
    def test_date_range_params(self):
        """Test that date range parameters are passed correctly."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json={"data": []})
        )

        client = OuraClient(access_token="test_token")
        client.get_daily_sleep("2026-01-01", "2026-01-31")

        request = respx.calls.last.request
        assert "start_date=2026-01-01" in str(request.url)
        assert "end_date=2026-01-31" in str(request.url)

        client.close()


# === OuraSyncService Tests ===

class TestOuraSyncService:
    """Tests for OuraSyncService database operations."""

    @respx.mock
    def test_sync_sleep_creates_datapoint(self, db, mock_sleep_response):
        """Test that syncing sleep data creates DataPoint records."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=mock_sleep_response)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        result = service.sync_sleep("2026-02-03")

        assert result.success
        assert result.records_synced == 1
        assert result.data_type == OuraDataType.SLEEP

        # Verify data point in DB
        dp = db.query(DataPoint).filter(
            DataPoint.source == "oura",
            DataPoint.type == "sleep",
            DataPoint.date == "2026-02-03"
        ).first()

        assert dp is not None
        assert dp.value == 85
        assert dp.extra_data["total_sleep_duration"] == 28800

    @respx.mock
    def test_sync_activity_creates_datapoint(self, db, mock_activity_response):
        """Test that syncing activity data creates DataPoint records."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_activity").mock(
            return_value=httpx.Response(200, json=mock_activity_response)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        result = service.sync_activity("2026-02-03")

        assert result.success
        assert result.records_synced == 1

        dp = db.query(DataPoint).filter(
            DataPoint.source == "oura",
            DataPoint.type == "activity",
            DataPoint.date == "2026-02-03"
        ).first()

        assert dp is not None
        assert dp.value == 78
        assert dp.extra_data["steps"] == 8500

    @respx.mock
    def test_sync_readiness_creates_datapoint(self, db, mock_readiness_response):
        """Test that syncing readiness data creates DataPoint records."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_readiness").mock(
            return_value=httpx.Response(200, json=mock_readiness_response)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        result = service.sync_readiness("2026-02-03")

        assert result.success
        assert result.records_synced == 1

        dp = db.query(DataPoint).filter(
            DataPoint.source == "oura",
            DataPoint.type == "readiness",
            DataPoint.date == "2026-02-03"
        ).first()

        assert dp is not None
        assert dp.value == 82

    @respx.mock
    def test_upsert_updates_existing(self, db, mock_sleep_response):
        """Test that re-syncing updates existing records rather than duplicating."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=mock_sleep_response)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))

        # First sync
        result1 = service.sync_sleep("2026-02-03")
        assert result1.records_synced == 1

        # Modify mock response score
        updated_response = {
            "data": [{**mock_sleep_response["data"][0], "score": 90}]
        }
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=updated_response)
        )

        # Second sync should update, not duplicate
        result2 = service.sync_sleep("2026-02-03")
        assert result2.records_synced == 1

        # Should still only have one record
        count = db.query(DataPoint).filter(
            DataPoint.source == "oura",
            DataPoint.type == "sleep",
            DataPoint.date == "2026-02-03"
        ).count()
        assert count == 1

        # Score should be updated
        dp = db.query(DataPoint).filter(
            DataPoint.source == "oura",
            DataPoint.type == "sleep",
            DataPoint.date == "2026-02-03"
        ).first()
        assert dp.value == 90

    @respx.mock
    def test_sync_all_returns_three_results(
        self, db, mock_sleep_response, mock_activity_response, mock_readiness_response
    ):
        """Test that sync_all syncs all three data types."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=mock_sleep_response)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_activity").mock(
            return_value=httpx.Response(200, json=mock_activity_response)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_readiness").mock(
            return_value=httpx.Response(200, json=mock_readiness_response)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        results = service.sync_all("2026-02-03")

        assert len(results) == 3
        assert all(r.success for r in results)
        assert sum(r.records_synced for r in results) == 3

    @respx.mock
    def test_api_failure_returns_error_result(self, db):
        """Test that API failures return proper error results."""
        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(500, json={"error": "Server error"})
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        result = service.sync_sleep("2026-02-03")

        assert not result.success
        assert result.records_synced == 0
        assert len(result.errors) > 0

    @respx.mock
    def test_backfill_syncs_multiple_days(
        self, db, mock_sleep_response, mock_activity_response, mock_readiness_response
    ):
        """Test that backfill syncs data for multiple days."""
        # Mock responses for 7 days
        multi_sleep = {"data": [
            {**mock_sleep_response["data"][0], "day": (date.today() - timedelta(days=i)).isoformat()}
            for i in range(7)
        ]}
        multi_activity = {"data": [
            {**mock_activity_response["data"][0], "day": (date.today() - timedelta(days=i)).isoformat()}
            for i in range(7)
        ]}
        multi_readiness = {"data": [
            {**mock_readiness_response["data"][0], "day": (date.today() - timedelta(days=i)).isoformat()}
            for i in range(7)
        ]}

        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=multi_sleep)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_activity").mock(
            return_value=httpx.Response(200, json=multi_activity)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_readiness").mock(
            return_value=httpx.Response(200, json=multi_readiness)
        )

        service = OuraSyncService(db, OuraClient(access_token="test"))
        results = service.backfill(days=7)

        assert len(results) == 3
        total_synced = sum(r.records_synced for r in results)
        assert total_synced == 21  # 7 days * 3 types


# === SyncResult Tests ===

class TestSyncResult:
    """Tests for SyncResult formatting."""

    def test_str_success(self):
        """Test string representation of successful sync."""
        result = SyncResult(
            success=True,
            data_type=OuraDataType.SLEEP,
            records_synced=5,
            date_range=("2026-01-01", "2026-01-05")
        )
        assert "Synced 5 sleep records" in str(result)

    def test_str_failure(self):
        """Test string representation of failed sync."""
        result = SyncResult(
            success=False,
            data_type=OuraDataType.ACTIVITY,
            records_synced=0,
            date_range=("2026-01-01", "2026-01-01"),
            errors=["API timeout"]
        )
        assert "Failed" in str(result)
        assert "API timeout" in str(result)


# === Integration Test ===

class TestSyncOuraDataFunction:
    """Tests for the convenience sync_oura_data function."""

    @respx.mock
    def test_sync_oura_data_defaults_to_today(
        self, db, mock_sleep_response, mock_activity_response, mock_readiness_response
    ):
        """Test that sync_oura_data syncs today by default."""
        today = date.today().isoformat()
        mock_sleep_response["data"][0]["day"] = today
        mock_activity_response["data"][0]["day"] = today
        mock_readiness_response["data"][0]["day"] = today

        respx.get("https://api.ouraring.com/v2/usercollection/daily_sleep").mock(
            return_value=httpx.Response(200, json=mock_sleep_response)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_activity").mock(
            return_value=httpx.Response(200, json=mock_activity_response)
        )
        respx.get("https://api.ouraring.com/v2/usercollection/daily_readiness").mock(
            return_value=httpx.Response(200, json=mock_readiness_response)
        )

        results = sync_oura_data(db)

        assert len(results) == 3
        assert all(r.success for r in results)
