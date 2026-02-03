"""
Integration tests for capture endpoints.

Tests quick capture of notes, tasks, and energy logs.
"""

import pytest
from unittest.mock import patch, MagicMock

from src.models import Note, Task, JournalEntry


class TestCaptureEndpoint:
    """Tests for POST /api/capture endpoint."""

    @patch('src.routers.capture.CaptureService')
    def test_capture_note(self, mock_service_class, test_client, db):
        """POST /api/capture creates note from text."""
        mock_service = MagicMock()
        mock_service.process.return_value = MagicMock(
            type="note",
            id=1,
            content="Test note content",
            title="Test Note",
            tags=["test"]
        )
        mock_service_class.return_value = mock_service

        response = test_client.post(
            "/api/capture",
            json={"text": "Remember to test the capture endpoint"}
        )

        assert response.status_code == 200
        mock_service.process.assert_called_once()

    @patch('src.routers.capture.CaptureService')
    def test_capture_task(self, mock_service_class, test_client, db):
        """POST /api/capture creates task from text."""
        mock_service = MagicMock()
        mock_service.process.return_value = MagicMock(
            type="task",
            id=1,
            content="Buy groceries",
            title="Buy groceries",
            priority="normal"
        )
        mock_service_class.return_value = mock_service

        response = test_client.post(
            "/api/capture",
            json={"text": "Todo: Buy groceries tomorrow"}
        )

        assert response.status_code == 200

    @patch('src.routers.capture.CaptureService')
    def test_capture_energy(self, mock_service_class, test_client, db):
        """POST /api/capture creates energy log."""
        mock_service = MagicMock()
        mock_service.process.return_value = MagicMock(
            type="energy",
            id=1,
            energy=4,
            mood=4,
            notes="Feeling good"
        )
        mock_service_class.return_value = mock_service

        response = test_client.post(
            "/api/capture",
            json={"text": "Energy 4, feeling good today"}
        )

        assert response.status_code == 200

    def test_capture_validates_text(self, test_client):
        """POST /api/capture requires text field."""
        response = test_client.post(
            "/api/capture",
            json={}
        )

        assert response.status_code == 422

    def test_capture_rejects_empty_text(self, test_client):
        """POST /api/capture rejects empty text."""
        response = test_client.post(
            "/api/capture",
            json={"text": ""}
        )

        # Should reject or handle gracefully
        assert response.status_code in [400, 422]


class TestNotesEndpoint:
    """Tests for notes endpoints."""

    def test_get_notes_returns_list(self, test_client, db):
        """GET /api/capture/notes returns note list."""
        db.add(Note(
            user_id=1,
            content="Test note",
            title="Test",
            source="manual"
        ))
        db.commit()

        response = test_client.get("/api/capture/notes")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_notes_paginates(self, test_client, db):
        """GET /api/capture/notes supports pagination."""
        # Create multiple notes
        for i in range(15):
            db.add(Note(
                user_id=1,
                content=f"Note {i}",
                title=f"Title {i}",
                source="manual"
            ))
        db.commit()

        response = test_client.get("/api/capture/notes?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data) <= 10


class TestTasksEndpoint:
    """Tests for tasks endpoints."""

    def test_get_tasks_returns_list(self, test_client, db):
        """GET /api/capture/tasks returns task list."""
        db.add(Task(
            user_id=1,
            title="Test task",
            status="pending",
            source="manual"
        ))
        db.commit()

        response = test_client.get("/api/capture/tasks")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_tasks_filters_by_status(self, test_client, db):
        """GET /api/capture/tasks?status=pending filters by status."""
        db.add(Task(user_id=1, title="Pending", status="pending", source="manual"))
        db.add(Task(user_id=1, title="Done", status="completed", source="manual"))
        db.commit()

        response = test_client.get("/api/capture/tasks?status=pending")

        assert response.status_code == 200
        data = response.json()
        assert all(t["status"] == "pending" for t in data)


class TestUpdateTaskEndpoint:
    """Tests for task update endpoint."""

    def test_update_task_status(self, test_client, db):
        """PATCH /api/capture/tasks/{id} updates task status."""
        task = Task(
            user_id=1,
            title="Test task",
            status="pending",
            source="manual"
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        response = test_client.patch(
            f"/api/capture/tasks/{task.id}",
            json={"status": "completed"}
        )

        assert response.status_code == 200
        db.refresh(task)
        assert task.status == "completed"
