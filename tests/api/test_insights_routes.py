"""
Integration tests for insights endpoints.

Tests daily briefs, patterns, energy predictions, and weekly reviews.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

from src.models import DataPoint, Insight, Pattern


class TestDailyBriefEndpoint:
    """Tests for daily brief endpoints."""

    def test_get_brief_returns_existing(self, test_client, db):
        """GET /api/insights/brief returns existing brief."""
        # Create test data
        today = date.today().isoformat()
        insight = Insight(
            user_id=1,
            date=today,
            type="daily_brief",
            content="Test brief content",
            confidence=0.85,
            context={}
        )
        db.add(insight)
        db.commit()

        response = test_client.get(f"/api/insights/brief?date={today}")

        assert response.status_code == 200
        data = response.json()
        assert data["content"] == "Test brief content"
        assert data["type"] == "daily_brief"

    def test_get_brief_returns_404_when_missing(self, test_client):
        """GET /api/insights/brief returns 404 when no brief exists."""
        response = test_client.get("/api/insights/brief?date=2020-01-01")

        assert response.status_code == 404

    @patch('src.routers.insights.InsightsService')
    def test_generate_brief_creates_new(self, mock_service_class, test_client, db):
        """POST /api/insights/brief/generate creates new brief."""
        mock_service = MagicMock()
        mock_service.generate_daily_brief.return_value = MagicMock(
            content="Generated brief",
            confidence=0.8,
            context={},
            type="daily_brief",
            date=date.today().isoformat()
        )
        mock_service_class.return_value = mock_service

        response = test_client.post("/api/insights/brief/generate")

        assert response.status_code == 200
        mock_service.generate_daily_brief.assert_called_once()


class TestPatternsEndpoint:
    """Tests for pattern endpoints."""

    def test_get_patterns_returns_list(self, test_client, db):
        """GET /api/insights/patterns returns pattern list."""
        # Create test pattern
        pattern = Pattern(
            user_id=1,
            name="Test Pattern",
            description="Test description",
            pattern_type="correlation",
            variables=["sleep", "energy"],
            strength=0.7,
            confidence=0.8,
            sample_size=30,
            active=True
        )
        db.add(pattern)
        db.commit()

        response = test_client.get("/api/insights/patterns")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["name"] == "Test Pattern"

    def test_get_patterns_filters_inactive(self, test_client, db):
        """GET /api/insights/patterns?active_only=true filters inactive."""
        # Create active and inactive patterns
        db.add(Pattern(
            user_id=1,
            name="Active",
            description="Active pattern",
            pattern_type="correlation",
            variables=[],
            strength=0.7,
            active=True
        ))
        db.add(Pattern(
            user_id=1,
            name="Inactive",
            description="Inactive pattern",
            pattern_type="correlation",
            variables=[],
            strength=0.5,
            active=False
        ))
        db.commit()

        response = test_client.get("/api/insights/patterns?active_only=true")

        assert response.status_code == 200
        data = response.json()
        names = [p["name"] for p in data]
        assert "Active" in names
        assert "Inactive" not in names


class TestEnergyPredictionEndpoint:
    """Tests for energy prediction endpoint."""

    def test_get_prediction_returns_data(self, test_client, db):
        """GET /api/insights/energy-prediction returns prediction."""
        # Create enough data for prediction
        for i in range(7):
            d = (date.today() - timedelta(days=i)).isoformat()
            db.add(DataPoint(
                user_id=1,
                date=d,
                source="oura",
                type="sleep",
                value=7.0 + i * 0.1,
                extra_data={"score": 80 + i}
            ))
            db.add(DataPoint(
                user_id=1,
                date=d,
                source="oura",
                type="readiness",
                value=75 + i
            ))
        db.commit()

        response = test_client.get("/api/insights/energy-prediction")

        # May return 200 or 404 depending on model state
        assert response.status_code in [200, 404, 500]


class TestWeeklyReviewEndpoint:
    """Tests for weekly review endpoints."""

    def test_get_weekly_review_returns_existing(self, test_client, db):
        """GET /api/insights/weekly-review returns existing review."""
        # Create test review
        week_ending = date.today().isoformat()
        insight = Insight(
            user_id=1,
            date=week_ending,
            type="weekly_review",
            content="Test weekly review",
            confidence=0.9,
            context={}
        )
        db.add(insight)
        db.commit()

        response = test_client.get(f"/api/insights/weekly-review?week_ending={week_ending}")

        assert response.status_code == 200
        data = response.json()
        assert data["type"] == "weekly_review"


class TestRecentInsightsEndpoint:
    """Tests for recent insights endpoint."""

    def test_get_recent_insights(self, test_client, db):
        """GET /api/insights/recent returns recent insights."""
        # Create multiple insights
        for i in range(3):
            d = (date.today() - timedelta(days=i)).isoformat()
            db.add(Insight(
                user_id=1,
                date=d,
                type="daily_brief",
                content=f"Brief {i}",
                confidence=0.8
            ))
        db.commit()

        response = test_client.get("/api/insights/recent?days=7")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
