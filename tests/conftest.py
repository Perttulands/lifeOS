"""
Shared pytest fixtures for LifeOS test suite.

Provides database sessions, mock services, and test data factories.
"""

import pytest
from datetime import datetime, date, timedelta
from typing import Generator, Dict, Any
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from src.database import Base
from src.models import (
    User, DataPoint, Insight, Pattern, JournalEntry,
    Goal, Milestone, Task, Note, OAuthToken, CalendarEvent,
    UserPreference, InsightFeedback, VoiceNote
)


# === Database Fixtures ===

@pytest.fixture(scope="function")
def test_engine():
    """Create an in-memory SQLite engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db(test_engine) -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def db_with_user(db: Session) -> Session:
    """Database session with a default user created."""
    user = User(id=1, name="Test User", timezone="UTC")
    db.add(user)
    db.commit()
    return db


# === Test Data Factories ===

@pytest.fixture
def sample_sleep_data() -> Dict[str, Any]:
    """Sample sleep data point."""
    return {
        "date": "2026-02-03",
        "source": "oura",
        "type": "sleep",
        "value": 7.5,  # hours
        "extra_data": {
            "score": 85,
            "deep_sleep_hours": 1.5,
            "rem_sleep_hours": 2.0,
            "light_sleep_hours": 4.0,
            "efficiency": 92,
            "bedtime": "23:00",
            "wake_time": "06:30"
        }
    }


@pytest.fixture
def sample_readiness_data() -> Dict[str, Any]:
    """Sample readiness data point."""
    return {
        "date": "2026-02-03",
        "source": "oura",
        "type": "readiness",
        "value": 78,
        "extra_data": {
            "score": 78,
            "hrv_balance": 70,
            "recovery_index": 82,
            "resting_heart_rate": 58
        }
    }


@pytest.fixture
def sample_activity_data() -> Dict[str, Any]:
    """Sample activity data point."""
    return {
        "date": "2026-02-03",
        "source": "oura",
        "type": "activity",
        "value": 72,
        "extra_data": {
            "score": 72,
            "steps": 8500,
            "active_calories": 450,
            "total_calories": 2200
        }
    }


@pytest.fixture
def create_data_point(db: Session):
    """Factory fixture to create data points."""
    def _create(
        date: str = "2026-02-03",
        source: str = "oura",
        type: str = "sleep",
        value: float = 7.5,
        extra_data: Dict = None
    ) -> DataPoint:
        dp = DataPoint(
            user_id=1,
            date=date,
            source=source,
            type=type,
            value=value,
            extra_data=extra_data or {}
        )
        db.add(dp)
        db.commit()
        db.refresh(dp)
        return dp
    return _create


@pytest.fixture
def create_journal_entry(db: Session):
    """Factory fixture to create journal entries."""
    def _create(
        date: str = "2026-02-03",
        energy: int = 4,
        mood: int = 4,
        notes: str = None,
        time: str = "10:00"
    ) -> JournalEntry:
        entry = JournalEntry(
            user_id=1,
            date=date,
            time=time,
            energy=energy,
            mood=mood,
            notes=notes
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry
    return _create


@pytest.fixture
def create_insight(db: Session):
    """Factory fixture to create insights."""
    def _create(
        date: str = "2026-02-03",
        type: str = "daily_brief",
        content: str = "Test insight content",
        confidence: float = 0.8,
        context: Dict = None
    ) -> Insight:
        insight = Insight(
            user_id=1,
            date=date,
            type=type,
            content=content,
            confidence=confidence,
            context=context or {}
        )
        db.add(insight)
        db.commit()
        db.refresh(insight)
        return insight
    return _create


@pytest.fixture
def create_pattern(db: Session):
    """Factory fixture to create patterns."""
    def _create(
        name: str = "Test Pattern",
        description: str = "Test pattern description",
        pattern_type: str = "correlation",
        strength: float = 0.7,
        confidence: float = 0.8,
        active: bool = True
    ) -> Pattern:
        pattern = Pattern(
            user_id=1,
            name=name,
            description=description,
            pattern_type=pattern_type,
            variables=["sleep", "energy"],
            strength=strength,
            confidence=confidence,
            sample_size=30,
            actionable=True,
            active=active
        )
        db.add(pattern)
        db.commit()
        db.refresh(pattern)
        return pattern
    return _create


@pytest.fixture
def create_preference(db: Session):
    """Factory fixture to create user preferences."""
    def _create(
        category: str = "tone",
        key: str = "style",
        value: Any = "casual",
        weight: float = 0.8,
        source: str = "explicit"
    ) -> UserPreference:
        pref = UserPreference(
            user_id=1,
            category=category,
            key=key,
            value=value,
            weight=weight,
            source=source,
            evidence_count=1
        )
        db.add(pref)
        db.commit()
        db.refresh(pref)
        return pref
    return _create


@pytest.fixture
def create_calendar_event(db: Session):
    """Factory fixture to create calendar events."""
    def _create(
        event_id: str = "event_001",
        summary: str = "Team Meeting",
        start_time: datetime = None,
        end_time: datetime = None,
        calendar_id: str = "primary"
    ) -> CalendarEvent:
        if start_time is None:
            start_time = datetime(2026, 2, 3, 10, 0)
        if end_time is None:
            end_time = datetime(2026, 2, 3, 11, 0)

        event = CalendarEvent(
            user_id=1,
            event_id=event_id,
            calendar_id=calendar_id,
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            status="confirmed"
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event
    return _create


@pytest.fixture
def create_goal(db: Session):
    """Factory fixture to create goals."""
    def _create(
        title: str = "Test Goal",
        description: str = "Test goal description",
        target_date: str = None,
        category: str = "personal",
        status: str = "active"
    ) -> Goal:
        goal = Goal(
            user_id=1,
            title=title,
            description=description,
            target_date=target_date,
            category=category,
            status=status,
            progress=0.0,
            actual_hours=0.0,
            tags=[]
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)
        return goal
    return _create


@pytest.fixture
def create_milestone(db: Session):
    """Factory fixture to create milestones."""
    def _create(
        goal_id: int,
        title: str = "Test Milestone",
        description: str = "Test milestone description",
        order: int = 1,
        status: str = "pending",
        estimated_hours: float = 2.0,
        source: str = "manual"
    ) -> Milestone:
        milestone = Milestone(
            goal_id=goal_id,
            user_id=1,
            title=title,
            description=description,
            order=order,
            status=status,
            estimated_hours=estimated_hours,
            actual_hours=0.0,
            source=source
        )
        db.add(milestone)
        db.commit()
        db.refresh(milestone)
        return milestone
    return _create


# === Mock Service Fixtures ===

@pytest.fixture
def mock_ai():
    """Mock AI service for testing without API calls."""
    mock = MagicMock()
    mock.generate_brief.return_value = MagicMock(
        content="Your sleep was good. Energy should be high today.",
        confidence=0.85,
        context={"sleep_score": 85},
        tokens_used=150
    )
    mock.detect_patterns.return_value = [
        MagicMock(
            name="Sleep-Energy Correlation",
            description="More sleep leads to higher energy",
            pattern_type="correlation",
            variables=["sleep_duration", "energy"],
            strength=0.75,
            confidence=0.8,
            sample_size=30,
            actionable=True
        )
    ]
    mock.generate_weekly_review.return_value = MagicMock(
        content="This week you averaged 7.5 hours of sleep.",
        confidence=0.9,
        context={"avg_sleep": 7.5},
        tokens_used=200
    )
    return mock


@pytest.fixture
def mock_analyzer():
    """Mock pattern analyzer for testing without scipy."""
    mock = MagicMock()
    mock.analyze_all.return_value = [
        MagicMock(
            name="Sleep-Energy Correlation",
            description="Statistical correlation detected",
            pattern_type="correlation",
            variables=["sleep_duration", "energy"],
            strength=0.72,
            confidence=0.85,
            sample_size=28,
            actionable=True
        )
    ]
    return mock


@pytest.fixture
def mock_personalization():
    """Mock personalization service."""
    mock = MagicMock()
    mock.build_personalization_prompt.return_value = "Use a casual tone. Focus on sleep quality."
    mock.get_preference_context.return_value = MagicMock(
        tone_style="casual",
        focus_areas=["sleep", "energy"],
        include_comparisons=True,
        include_predictions=True,
        preferred_insight_length="medium",
        active_patterns=[],
        raw_preferences={}
    )
    return mock


# === API Testing Fixtures ===

@pytest.fixture
def test_client(test_engine):
    """Create a FastAPI test client with test database."""
    from fastapi.testclient import TestClient
    from src.api import app
    from src.database import get_db

    TestSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine
    )

    def override_get_db():
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


# === Time Helpers ===

@pytest.fixture
def today() -> str:
    """Return today's date as string."""
    return date.today().isoformat()


@pytest.fixture
def yesterday() -> str:
    """Return yesterday's date as string."""
    return (date.today() - timedelta(days=1)).isoformat()


@pytest.fixture
def week_ago() -> str:
    """Return date from a week ago as string."""
    return (date.today() - timedelta(days=7)).isoformat()


# === Data Generation Helpers ===

@pytest.fixture
def generate_week_of_data(create_data_point, create_journal_entry):
    """Generate a week of test data."""
    def _generate(start_date: date = None):
        if start_date is None:
            start_date = date.today() - timedelta(days=7)

        data_points = []
        journal_entries = []

        for i in range(7):
            d = (start_date + timedelta(days=i)).isoformat()

            # Sleep data
            sleep_score = 70 + (i * 3) % 25  # Vary between 70-95
            data_points.append(create_data_point(
                date=d,
                type="sleep",
                value=6.5 + (i % 3) * 0.5,  # 6.5-8 hours
                extra_data={
                    "score": sleep_score,
                    "deep_sleep_hours": 1.0 + (i % 3) * 0.3,
                    "rem_sleep_hours": 1.5 + (i % 2) * 0.5,
                    "efficiency": 85 + (i % 10)
                }
            ))

            # Readiness data
            data_points.append(create_data_point(
                date=d,
                type="readiness",
                value=65 + (i * 4) % 30
            ))

            # Activity data
            data_points.append(create_data_point(
                date=d,
                type="activity",
                value=60 + (i * 5) % 35,
                extra_data={
                    "steps": 5000 + i * 1000,
                    "active_calories": 300 + i * 50
                }
            ))

            # Journal entry (energy log)
            energy = 3 + (i % 3)  # 3-5
            journal_entries.append(create_journal_entry(
                date=d,
                energy=energy,
                mood=energy
            ))

        return data_points, journal_entries

    return _generate


# === Async Fixtures ===

@pytest.fixture
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"
