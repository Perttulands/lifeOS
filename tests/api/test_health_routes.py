"""
Integration tests for health check endpoints.
"""

import pytest


class TestHealthEndpoint:
    """Tests for GET /api/health endpoint."""

    def test_health_check_returns_200(self, test_client):
        """Health check returns 200 OK."""
        response = test_client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data

    def test_health_check_has_version(self, test_client):
        """Health check includes version info."""
        response = test_client.get("/api/health")

        data = response.json()
        assert "version" in data
        assert data["version"] is not None


class TestDetailedHealthEndpoint:
    """Tests for GET /api/health/detailed endpoint."""

    def test_detailed_health_returns_services(self, test_client):
        """Detailed health check includes service status."""
        response = test_client.get("/api/health/detailed")

        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "uptime_seconds" in data

    def test_detailed_health_includes_database(self, test_client):
        """Detailed health includes database status."""
        response = test_client.get("/api/health/detailed")

        data = response.json()
        # Database should be in services
        assert "database" in data["services"]


class TestUptimeEndpoint:
    """Tests for GET /api/health/uptime endpoint."""

    def test_uptime_returns_formatted(self, test_client):
        """Uptime endpoint returns formatted time."""
        response = test_client.get("/api/health/uptime")

        assert response.status_code == 200
        data = response.json()
        assert "uptime_seconds" in data
        assert "uptime_formatted" in data
        assert "started_at" in data
