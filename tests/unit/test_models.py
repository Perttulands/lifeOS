"""
Unit tests for SQLAlchemy models.

Tests model creation, constraints, and relationships.
"""

import pytest
from datetime import datetime

from src.models import (
    User, DataPoint, Insight, Pattern, JournalEntry,
    Task, Note, CalendarEvent, UserPreference, InsightFeedback
)


class TestUserModel:
    """Tests for User model."""

    def test_create_user(self, db):
        """User can be created with required fields."""
        user = User(name="Test User", timezone="America/New_York")
        db.add(user)
        db.commit()
        db.refresh(user)

        assert user.id is not None
        assert user.name == "Test User"
        assert user.timezone == "America/New_York"
        assert user.created_at is not None

    def test_user_default_values(self, db):
        """User has sensible defaults."""
        user = User()
        db.add(user)
        db.commit()

        assert user.name == "User"
        assert user.timezone == "UTC"


class TestDataPointModel:
    """Tests for DataPoint model."""

    def test_create_data_point(self, db):
        """DataPoint can be created with required fields."""
        dp = DataPoint(
            user_id=1,
            source="oura",
            type="sleep",
            date="2026-02-03",
            value=7.5
        )
        db.add(dp)
        db.commit()
        db.refresh(dp)

        assert dp.id is not None
        assert dp.source == "oura"
        assert dp.type == "sleep"
        assert dp.value == 7.5

    def test_data_point_extra_data(self, db):
        """DataPoint stores JSON extra_data."""
        dp = DataPoint(
            user_id=1,
            source="oura",
            type="sleep",
            date="2026-02-03",
            value=7.5,
            extra_data={"score": 85, "deep_sleep": 1.5}
        )
        db.add(dp)
        db.commit()
        db.refresh(dp)

        assert dp.extra_data["score"] == 85
        assert dp.extra_data["deep_sleep"] == 1.5


class TestInsightModel:
    """Tests for Insight model."""

    def test_create_insight(self, db):
        """Insight can be created with required fields."""
        insight = Insight(
            user_id=1,
            type="daily_brief",
            date="2026-02-03",
            content="Test insight content",
            confidence=0.85
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)

        assert insight.id is not None
        assert insight.type == "daily_brief"
        assert insight.confidence == 0.85

    def test_insight_context(self, db):
        """Insight stores JSON context."""
        insight = Insight(
            user_id=1,
            type="daily_brief",
            date="2026-02-03",
            content="Test",
            context={"sleep_score": 85, "factors": ["good_sleep"]}
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)

        assert insight.context["sleep_score"] == 85


class TestPatternModel:
    """Tests for Pattern model."""

    def test_create_pattern(self, db):
        """Pattern can be created with required fields."""
        pattern = Pattern(
            user_id=1,
            name="Sleep-Energy Correlation",
            description="More sleep leads to higher energy",
            pattern_type="correlation",
            variables=["sleep_duration", "energy"],
            strength=0.75,
            confidence=0.8,
            sample_size=30
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)

        assert pattern.id is not None
        assert pattern.name == "Sleep-Energy Correlation"
        assert pattern.strength == 0.75

    def test_pattern_defaults(self, db):
        """Pattern has sensible defaults."""
        pattern = Pattern(
            user_id=1,
            name="Test",
            description="Test"
        )
        db.add(pattern)
        db.commit()

        assert pattern.active is True
        assert pattern.actionable is True


class TestJournalEntryModel:
    """Tests for JournalEntry model."""

    def test_create_journal_entry(self, db):
        """JournalEntry can be created."""
        entry = JournalEntry(
            user_id=1,
            date="2026-02-03",
            energy=4,
            mood=4,
            notes="Feeling good today"
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.id is not None
        assert entry.energy == 4
        assert entry.mood == 4

    def test_journal_entry_time(self, db):
        """JournalEntry stores time."""
        entry = JournalEntry(
            user_id=1,
            date="2026-02-03",
            time="10:30",
            energy=4
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)

        assert entry.time == "10:30"


class TestTaskModel:
    """Tests for Task model."""

    def test_create_task(self, db):
        """Task can be created."""
        task = Task(
            user_id=1,
            title="Test task",
            description="Task description",
            status="pending",
            priority="high"
        )
        db.add(task)
        db.commit()
        db.refresh(task)

        assert task.id is not None
        assert task.title == "Test task"
        assert task.status == "pending"

    def test_task_defaults(self, db):
        """Task has sensible defaults."""
        task = Task(
            user_id=1,
            title="Test"
        )
        db.add(task)
        db.commit()

        assert task.status == "pending"
        assert task.priority == "normal"
        assert task.source == "manual"


class TestNoteModel:
    """Tests for Note model."""

    def test_create_note(self, db):
        """Note can be created."""
        note = Note(
            user_id=1,
            content="Test note content",
            title="Test Note",
            source="manual"
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        assert note.id is not None
        assert note.content == "Test note content"

    def test_note_tags(self, db):
        """Note stores tags as JSON."""
        note = Note(
            user_id=1,
            content="Test",
            tags=["important", "meeting"]
        )
        db.add(note)
        db.commit()
        db.refresh(note)

        assert "important" in note.tags


class TestCalendarEventModel:
    """Tests for CalendarEvent model."""

    def test_create_calendar_event(self, db):
        """CalendarEvent can be created."""
        event = CalendarEvent(
            user_id=1,
            event_id="event_123",
            calendar_id="primary",
            summary="Team Meeting",
            start_time=datetime(2026, 2, 3, 10, 0),
            end_time=datetime(2026, 2, 3, 11, 0)
        )
        db.add(event)
        db.commit()
        db.refresh(event)

        assert event.id is not None
        assert event.summary == "Team Meeting"

    def test_calendar_event_defaults(self, db):
        """CalendarEvent has sensible defaults."""
        event = CalendarEvent(
            user_id=1,
            event_id="event_123",
            calendar_id="primary",
            start_time=datetime(2026, 2, 3, 10, 0),
            end_time=datetime(2026, 2, 3, 11, 0)
        )
        db.add(event)
        db.commit()

        assert event.all_day is False
        assert event.status == "confirmed"


class TestUserPreferenceModel:
    """Tests for UserPreference model."""

    def test_create_preference(self, db):
        """UserPreference can be created."""
        pref = UserPreference(
            user_id=1,
            category="tone",
            key="style",
            value="casual",
            weight=0.8,
            source="explicit"
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)

        assert pref.id is not None
        assert pref.value == "casual"

    def test_preference_defaults(self, db):
        """UserPreference has sensible defaults."""
        pref = UserPreference(
            user_id=1,
            category="tone",
            key="style",
            value="casual"
        )
        db.add(pref)
        db.commit()

        assert pref.weight == 0.5
        assert pref.source == "inferred"
        assert pref.evidence_count == 1


class TestInsightFeedbackModel:
    """Tests for InsightFeedback model."""

    def test_create_feedback(self, db):
        """InsightFeedback can be created."""
        # First create an insight
        insight = Insight(
            user_id=1,
            type="daily_brief",
            date="2026-02-03",
            content="Test"
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)

        feedback = InsightFeedback(
            user_id=1,
            insight_id=insight.id,
            feedback_type="helpful"
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)

        assert feedback.id is not None
        assert feedback.feedback_type == "helpful"
