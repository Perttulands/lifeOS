"""
LifeOS Oura Integration

Oura API adapter for syncing sleep, activity, and readiness data.

Supports both Personal Access Tokens and OAuth2 with token refresh.
API docs: https://cloud.ouraring.com/docs/
"""

import json
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

import httpx
from sqlalchemy.orm import Session

from ..config import settings
from ..models import DataPoint


class OuraDataType(str, Enum):
    """Types of data available from Oura."""
    SLEEP = "sleep"
    ACTIVITY = "activity"
    READINESS = "readiness"


@dataclass
class OuraToken:
    """OAuth2 token storage."""
    access_token: str
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        """Check if token is expired (with 5 min buffer)."""
        if self.expires_at is None:
            return False  # PAT tokens don't expire
        return datetime.utcnow() >= (self.expires_at - timedelta(minutes=5))


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    data_type: OuraDataType
    records_synced: int
    date_range: tuple[str, str]
    errors: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.success:
            return f"Synced {self.records_synced} {self.data_type.value} records ({self.date_range[0]} to {self.date_range[1]})"
        return f"Failed to sync {self.data_type.value}: {', '.join(self.errors)}"


class OuraClient:
    """
    HTTP client for Oura API v2.

    Handles authentication and request formatting.
    """

    BASE_URL = "https://api.ouraring.com/v2"

    def __init__(
        self,
        access_token: Optional[str] = None,
        refresh_token: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None
    ):
        """
        Initialize Oura client.

        Args:
            access_token: Personal Access Token or OAuth2 access token
            refresh_token: OAuth2 refresh token (optional)
            client_id: OAuth2 client ID (for token refresh)
            client_secret: OAuth2 client secret (for token refresh)
        """
        self.token = OuraToken(
            access_token=access_token or settings.oura_token,
            refresh_token=refresh_token
        )
        self.client_id = client_id
        self.client_secret = client_secret
        self._http_client: Optional[httpx.Client] = None

    @property
    def http_client(self) -> httpx.Client:
        """Lazy-initialized HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.Client(
                base_url=self.BASE_URL,
                headers=self._auth_headers(),
                timeout=30.0
            )
        return self._http_client

    def _auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        return {
            "Authorization": f"Bearer {self.token.access_token}",
            "Content-Type": "application/json"
        }

    def _refresh_token(self) -> bool:
        """
        Refresh OAuth2 access token.

        Returns:
            True if refresh succeeded, False otherwise
        """
        if not self.token.refresh_token or not self.client_id or not self.client_secret:
            return False

        try:
            response = httpx.post(
                "https://api.ouraring.com/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.token.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret
                },
                timeout=30.0
            )
            response.raise_for_status()

            data = response.json()
            self.token = OuraToken(
                access_token=data["access_token"],
                refresh_token=data.get("refresh_token", self.token.refresh_token),
                expires_at=datetime.utcnow() + timedelta(seconds=data.get("expires_in", 86400)),
                token_type=data.get("token_type", "Bearer")
            )

            # Reset HTTP client to use new token
            if self._http_client:
                self._http_client.close()
                self._http_client = None

            return True
        except Exception:
            return False

    def _ensure_valid_token(self) -> bool:
        """Ensure token is valid, refreshing if needed."""
        if self.token.is_expired:
            return self._refresh_token()
        return True

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Make an authenticated API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters

        Returns:
            JSON response or None on error
        """
        if not self._ensure_valid_token():
            return None

        try:
            response = self.http_client.request(method, endpoint, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                # Token might be invalid, try refresh
                if self._refresh_token():
                    return self._request(method, endpoint, params)
            return None
        except Exception:
            return None

    def get_daily_sleep(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get daily sleep data.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to start_date

        Returns:
            List of daily sleep records or None on error
        """
        params = {"start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        response = self._request("GET", "/usercollection/daily_sleep", params)
        if response:
            return response.get("data", [])
        return None

    def get_daily_activity(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get daily activity data.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to start_date

        Returns:
            List of daily activity records or None on error
        """
        params = {"start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        response = self._request("GET", "/usercollection/daily_activity", params)
        if response:
            return response.get("data", [])
        return None

    def get_daily_readiness(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Get daily readiness data.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD), defaults to start_date

        Returns:
            List of daily readiness records or None on error
        """
        params = {"start_date": start_date}
        if end_date:
            params["end_date"] = end_date

        response = self._request("GET", "/usercollection/daily_readiness", params)
        if response:
            return response.get("data", [])
        return None

    def close(self):
        """Close HTTP client."""
        if self._http_client:
            self._http_client.close()
            self._http_client = None


class OuraSyncService:
    """
    Service for syncing Oura data to the database.

    Transforms Oura API responses into DataPoint records.
    """

    def __init__(self, db: Session, client: Optional[OuraClient] = None):
        """
        Initialize sync service.

        Args:
            db: Database session
            client: Oura client (defaults to new client with configured token)
        """
        self.db = db
        self.client = client or OuraClient()

    def _transform_sleep(self, data: Dict[str, Any]) -> DataPoint:
        """Transform Oura sleep data to DataPoint."""
        # Extract key metrics
        contributors = data.get("contributors", {})

        return DataPoint(
            source="oura",
            type="sleep",
            date=data.get("day", ""),
            value=data.get("score"),  # Overall sleep score
            metadata={
                "total_sleep_duration": data.get("total_sleep_duration"),  # seconds
                "deep_sleep_duration": contributors.get("deep_sleep"),
                "rem_sleep_duration": contributors.get("rem_sleep"),
                "light_sleep_duration": contributors.get("light_sleep"),
                "efficiency": contributors.get("efficiency"),
                "latency": contributors.get("latency"),
                "restfulness": contributors.get("restfulness"),
                "timing": contributors.get("timing"),
                "timestamp": data.get("timestamp"),
            }
        )

    def _transform_activity(self, data: Dict[str, Any]) -> DataPoint:
        """Transform Oura activity data to DataPoint."""
        contributors = data.get("contributors", {})

        return DataPoint(
            source="oura",
            type="activity",
            date=data.get("day", ""),
            value=data.get("score"),  # Overall activity score
            metadata={
                "active_calories": data.get("active_calories"),
                "total_calories": data.get("total_calories"),
                "steps": data.get("steps"),
                "equivalent_walking_distance": data.get("equivalent_walking_distance"),
                "high_activity_time": data.get("high_activity_time"),
                "medium_activity_time": data.get("medium_activity_time"),
                "low_activity_time": data.get("low_activity_time"),
                "sedentary_time": data.get("sedentary_time"),
                "resting_time": data.get("resting_time"),
                "meet_daily_targets": contributors.get("meet_daily_targets"),
                "move_every_hour": contributors.get("move_every_hour"),
                "recovery_time": contributors.get("recovery_time"),
                "stay_active": contributors.get("stay_active"),
                "training_frequency": contributors.get("training_frequency"),
                "training_volume": contributors.get("training_volume"),
                "timestamp": data.get("timestamp"),
            }
        )

    def _transform_readiness(self, data: Dict[str, Any]) -> DataPoint:
        """Transform Oura readiness data to DataPoint."""
        contributors = data.get("contributors", {})

        return DataPoint(
            source="oura",
            type="readiness",
            date=data.get("day", ""),
            value=data.get("score"),  # Overall readiness score
            metadata={
                "temperature_deviation": data.get("temperature_deviation"),
                "temperature_trend_deviation": data.get("temperature_trend_deviation"),
                "activity_balance": contributors.get("activity_balance"),
                "body_temperature": contributors.get("body_temperature"),
                "hrv_balance": contributors.get("hrv_balance"),
                "previous_day_activity": contributors.get("previous_day_activity"),
                "previous_night": contributors.get("previous_night"),
                "recovery_index": contributors.get("recovery_index"),
                "resting_heart_rate": contributors.get("resting_heart_rate"),
                "sleep_balance": contributors.get("sleep_balance"),
                "timestamp": data.get("timestamp"),
            }
        )

    def _upsert_datapoint(self, dp: DataPoint) -> bool:
        """
        Insert or update a DataPoint.

        Updates existing record if same source/type/date exists.

        Returns:
            True if inserted/updated, False on error
        """
        try:
            existing = self.db.query(DataPoint).filter(
                DataPoint.source == dp.source,
                DataPoint.type == dp.type,
                DataPoint.date == dp.date
            ).first()

            if existing:
                existing.value = dp.value
                existing.metadata = dp.metadata
                existing.timestamp = datetime.utcnow()
            else:
                self.db.add(dp)

            return True
        except Exception:
            return False

    def sync_sleep(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> SyncResult:
        """
        Sync sleep data from Oura.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            SyncResult with sync status
        """
        end_date = end_date or start_date

        data = self.client.get_daily_sleep(start_date, end_date)
        if data is None:
            return SyncResult(
                success=False,
                data_type=OuraDataType.SLEEP,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=["Failed to fetch sleep data from Oura API"]
            )

        synced = 0
        errors = []

        for record in data:
            dp = self._transform_sleep(record)
            if self._upsert_datapoint(dp):
                synced += 1
            else:
                errors.append(f"Failed to save sleep data for {record.get('day', 'unknown')}")

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            return SyncResult(
                success=False,
                data_type=OuraDataType.SLEEP,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=[f"Database commit failed: {str(e)}"]
            )

        return SyncResult(
            success=len(errors) == 0,
            data_type=OuraDataType.SLEEP,
            records_synced=synced,
            date_range=(start_date, end_date),
            errors=errors
        )

    def sync_activity(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> SyncResult:
        """
        Sync activity data from Oura.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            SyncResult with sync status
        """
        end_date = end_date or start_date

        data = self.client.get_daily_activity(start_date, end_date)
        if data is None:
            return SyncResult(
                success=False,
                data_type=OuraDataType.ACTIVITY,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=["Failed to fetch activity data from Oura API"]
            )

        synced = 0
        errors = []

        for record in data:
            dp = self._transform_activity(record)
            if self._upsert_datapoint(dp):
                synced += 1
            else:
                errors.append(f"Failed to save activity data for {record.get('day', 'unknown')}")

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            return SyncResult(
                success=False,
                data_type=OuraDataType.ACTIVITY,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=[f"Database commit failed: {str(e)}"]
            )

        return SyncResult(
            success=len(errors) == 0,
            data_type=OuraDataType.ACTIVITY,
            records_synced=synced,
            date_range=(start_date, end_date),
            errors=errors
        )

    def sync_readiness(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> SyncResult:
        """
        Sync readiness data from Oura.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            SyncResult with sync status
        """
        end_date = end_date or start_date

        data = self.client.get_daily_readiness(start_date, end_date)
        if data is None:
            return SyncResult(
                success=False,
                data_type=OuraDataType.READINESS,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=["Failed to fetch readiness data from Oura API"]
            )

        synced = 0
        errors = []

        for record in data:
            dp = self._transform_readiness(record)
            if self._upsert_datapoint(dp):
                synced += 1
            else:
                errors.append(f"Failed to save readiness data for {record.get('day', 'unknown')}")

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            return SyncResult(
                success=False,
                data_type=OuraDataType.READINESS,
                records_synced=0,
                date_range=(start_date, end_date),
                errors=[f"Database commit failed: {str(e)}"]
            )

        return SyncResult(
            success=len(errors) == 0,
            data_type=OuraDataType.READINESS,
            records_synced=synced,
            date_range=(start_date, end_date),
            errors=errors
        )

    def sync_all(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> List[SyncResult]:
        """
        Sync all data types from Oura.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            List of SyncResults for each data type
        """
        results = [
            self.sync_sleep(start_date, end_date),
            self.sync_activity(start_date, end_date),
            self.sync_readiness(start_date, end_date),
        ]
        return results

    def backfill(self, days: int = 30) -> List[SyncResult]:
        """
        Backfill historical data.

        Args:
            days: Number of days to backfill (default 30)

        Returns:
            List of SyncResults for each data type
        """
        end_date = date.today().isoformat()
        start_date = (date.today() - timedelta(days=days)).isoformat()
        return self.sync_all(start_date, end_date)


def sync_oura_data(
    db: Session,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 1
) -> List[SyncResult]:
    """
    Convenience function to sync Oura data.

    Args:
        db: Database session
        start_date: Start date (YYYY-MM-DD), defaults to today
        end_date: End date (YYYY-MM-DD), defaults to start_date
        days: If start_date not provided, sync this many days back

    Returns:
        List of SyncResults
    """
    if not start_date:
        start_date = (date.today() - timedelta(days=days-1)).isoformat()
    if not end_date:
        end_date = date.today().isoformat()

    service = OuraSyncService(db)
    return service.sync_all(start_date, end_date)
