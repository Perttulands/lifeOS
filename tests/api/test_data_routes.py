"""
Integration tests for data endpoints.

Tests data point CRUD operations.
"""

import pytest
from datetime import date, timedelta

from src.models import DataPoint


class TestGetDataEndpoint:
    """Tests for GET /api/data endpoint."""

    def test_get_data_returns_list(self, test_client, db):
        """GET /api/data returns data point list."""
        # Create test data
        db.add(DataPoint(
            user_id=1,
            date=date.today().isoformat(),
            source="oura",
            type="sleep",
            value=7.5
        ))
        db.commit()

        response = test_client.get("/api/data")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_data_filters_by_type(self, test_client, db):
        """GET /api/data?type=sleep filters by type."""
        today = date.today().isoformat()
        db.add(DataPoint(user_id=1, date=today, source="oura", type="sleep", value=7.5))
        db.add(DataPoint(user_id=1, date=today, source="oura", type="activity", value=80))
        db.commit()

        response = test_client.get("/api/data?type=sleep")

        assert response.status_code == 200
        data = response.json()
        assert all(d["type"] == "sleep" for d in data)

    def test_get_data_filters_by_date_range(self, test_client, db):
        """GET /api/data filters by start_date and end_date."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        week_ago = today - timedelta(days=7)

        db.add(DataPoint(user_id=1, date=today.isoformat(), source="oura", type="sleep", value=7.0))
        db.add(DataPoint(user_id=1, date=yesterday.isoformat(), source="oura", type="sleep", value=7.5))
        db.add(DataPoint(user_id=1, date=week_ago.isoformat(), source="oura", type="sleep", value=8.0))
        db.commit()

        # Get only last 2 days
        response = test_client.get(
            f"/api/data?start_date={yesterday.isoformat()}&end_date={today.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()
        dates = [d["date"] for d in data]
        assert week_ago.isoformat() not in dates


class TestGetDataByDateEndpoint:
    """Tests for GET /api/data/{date} endpoint."""

    def test_get_data_by_date(self, test_client, db):
        """GET /api/data/{date} returns all data for date."""
        today = date.today().isoformat()
        db.add(DataPoint(user_id=1, date=today, source="oura", type="sleep", value=7.5))
        db.add(DataPoint(user_id=1, date=today, source="oura", type="readiness", value=80))
        db.commit()

        response = test_client.get(f"/api/data/{today}")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_data_by_date_empty(self, test_client):
        """GET /api/data/{date} returns empty for no data."""
        response = test_client.get("/api/data/2020-01-01")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestCreateDataEndpoint:
    """Tests for POST /api/data endpoint."""

    def test_create_data_point(self, test_client, db):
        """POST /api/data creates new data point."""
        payload = {
            "date": date.today().isoformat(),
            "source": "manual",
            "type": "energy",
            "value": 4
        }

        response = test_client.post("/api/data", json=payload)

        assert response.status_code in [200, 201]
        data = response.json()
        assert data["type"] == "energy"
        assert data["value"] == 4

    def test_create_data_point_with_metadata(self, test_client, db):
        """POST /api/data accepts extra_data."""
        payload = {
            "date": date.today().isoformat(),
            "source": "manual",
            "type": "sleep",
            "value": 7.5,
            "extra_data": {"quality": "good", "notes": "Felt rested"}
        }

        response = test_client.post("/api/data", json=payload)

        assert response.status_code in [200, 201]

    def test_create_data_validates_required_fields(self, test_client):
        """POST /api/data validates required fields."""
        payload = {
            "source": "manual"
            # Missing date, type, value
        }

        response = test_client.post("/api/data", json=payload)

        assert response.status_code == 422  # Validation error


class TestDeleteDataEndpoint:
    """Tests for DELETE /api/data/{id} endpoint."""

    def test_delete_data_point(self, test_client, db):
        """DELETE /api/data/{id} removes data point."""
        dp = DataPoint(
            user_id=1,
            date=date.today().isoformat(),
            source="manual",
            type="energy",
            value=4
        )
        db.add(dp)
        db.commit()
        db.refresh(dp)
        dp_id = dp.id

        response = test_client.delete(f"/api/data/{dp_id}")

        assert response.status_code == 200

        # Verify deleted
        deleted = db.query(DataPoint).filter(DataPoint.id == dp_id).first()
        assert deleted is None

    def test_delete_nonexistent_returns_404(self, test_client):
        """DELETE /api/data/{id} returns 404 for nonexistent."""
        response = test_client.delete("/api/data/99999")

        assert response.status_code == 404
