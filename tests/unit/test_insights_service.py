"""
Unit tests for InsightsService.

Tests the core insight generation, pattern detection, and energy prediction logic.
"""

import pytest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from src.insights_service import InsightsService
from src.models import DataPoint, Insight, Pattern, JournalEntry
from src.ai import SleepData, DayContext, InsightResult


class TestInsightsServiceInit:
    """Tests for InsightsService initialization."""

    def test_init_with_defaults(self, db):
        """Service initializes with default dependencies."""
        with patch('src.insights_service.get_ai') as mock_get_ai, \
             patch('src.insights_service.get_personalization') as mock_get_pers:
            mock_get_ai.return_value = MagicMock()
            mock_get_pers.return_value = MagicMock()

            service = InsightsService(db)

            assert service.db == db
            assert service.ai is not None
            assert service.personalization is not None

    def test_init_with_custom_dependencies(self, db, mock_ai, mock_personalization):
        """Service accepts custom dependencies for testing."""
        service = InsightsService(
            db=db,
            ai=mock_ai,
            personalization=mock_personalization
        )

        assert service.ai == mock_ai
        assert service.personalization == mock_personalization


class TestGetSleepData:
    """Tests for _get_sleep_data helper."""

    def test_returns_sleep_data_when_exists(self, db, create_data_point, mock_ai):
        """Returns SleepData when data point exists."""
        create_data_point(
            date="2026-02-03",
            type="sleep",
            value=7.5,
            extra_data={
                "score": 85,
                "deep_sleep_hours": 1.5,
                "rem_sleep_hours": 2.0,
                "light_sleep_hours": 4.0,
                "efficiency": 92,
                "bedtime": "23:00",
                "wake_time": "06:30"
            }
        )

        service = InsightsService(db, ai=mock_ai)
        result = service._get_sleep_data("2026-02-03")

        assert result is not None
        assert result.date == "2026-02-03"
        assert result.duration_hours == 7.5
        assert result.score == 85
        assert result.deep_sleep_hours == 1.5
        assert result.efficiency == 92

    def test_returns_none_when_no_data(self, db, mock_ai):
        """Returns None when no sleep data exists for date."""
        service = InsightsService(db, ai=mock_ai)
        result = service._get_sleep_data("2026-02-03")

        assert result is None

    def test_handles_missing_extra_data(self, db, create_data_point, mock_ai):
        """Handles data points with minimal extra_data."""
        create_data_point(
            date="2026-02-03",
            type="sleep",
            value=7.0,
            extra_data={}
        )

        service = InsightsService(db, ai=mock_ai)
        result = service._get_sleep_data("2026-02-03")

        assert result is not None
        assert result.duration_hours == 7.0
        assert result.deep_sleep_hours == 0
        assert result.score == 0


class TestGetDayContext:
    """Tests for _get_day_context helper."""

    def test_builds_full_context(
        self, db, create_data_point, create_journal_entry, mock_ai
    ):
        """Builds complete DayContext with all data types."""
        # Create sleep data
        create_data_point(
            date="2026-02-03",
            type="sleep",
            value=7.5,
            extra_data={"score": 85}
        )

        # Create readiness data
        create_data_point(
            date="2026-02-03",
            type="readiness",
            value=78
        )

        # Create activity data
        create_data_point(
            date="2026-02-03",
            type="activity",
            value=72
        )

        # Create journal entry
        create_journal_entry(
            date="2026-02-03",
            energy=4
        )

        service = InsightsService(db, ai=mock_ai)
        context = service._get_day_context("2026-02-03")

        assert context.date == "2026-02-03"
        assert context.sleep is not None
        assert context.sleep.duration_hours == 7.5
        assert context.readiness_score == 78
        assert context.activity_score == 72
        assert context.energy_log == 4

    def test_handles_partial_data(self, db, create_data_point, mock_ai):
        """Handles days with only some data types."""
        create_data_point(
            date="2026-02-03",
            type="sleep",
            value=7.5
        )

        service = InsightsService(db, ai=mock_ai)
        context = service._get_day_context("2026-02-03")

        assert context.sleep is not None
        assert context.readiness_score is None
        assert context.activity_score is None
        assert context.energy_log is None

    def test_handles_no_data(self, db, mock_ai):
        """Handles days with no data at all."""
        service = InsightsService(db, ai=mock_ai)
        context = service._get_day_context("2026-02-03")

        assert context.date == "2026-02-03"
        assert context.sleep is None
        assert context.readiness_score is None


class TestGenerateDailyBrief:
    """Tests for generate_daily_brief method."""

    def test_generates_and_stores_brief(
        self, db, create_data_point, mock_ai, mock_personalization
    ):
        """Generates brief and stores in database."""
        create_data_point(
            date="2026-02-03",
            type="sleep",
            value=7.5,
            extra_data={"score": 85}
        )

        service = InsightsService(
            db, ai=mock_ai, personalization=mock_personalization
        )
        result = service.generate_daily_brief("2026-02-03")

        assert result is not None
        assert "sleep" in result.content.lower() or "energy" in result.content.lower()

        # Verify stored in database
        stored = db.query(Insight).filter(
            Insight.date == "2026-02-03",
            Insight.type == "daily_brief"
        ).first()
        assert stored is not None

    def test_returns_existing_brief(self, db, create_insight, mock_ai):
        """Returns existing brief instead of regenerating."""
        existing = create_insight(
            date="2026-02-03",
            type="daily_brief",
            content="Existing brief content"
        )

        service = InsightsService(db, ai=mock_ai)
        result = service.generate_daily_brief("2026-02-03")

        assert result.content == "Existing brief content"
        # AI should not be called
        mock_ai.generate_brief.assert_not_called()

    def test_calls_ai_with_personalization(
        self, db, create_data_point, mock_ai, mock_personalization
    ):
        """Passes personalization context to AI."""
        create_data_point(date="2026-02-03", type="sleep", value=7.5)

        service = InsightsService(
            db, ai=mock_ai, personalization=mock_personalization
        )
        service.generate_daily_brief("2026-02-03")

        # Verify personalization was used
        mock_personalization.build_personalization_prompt.assert_called()


class TestGetDailyBrief:
    """Tests for get_daily_brief method."""

    def test_returns_existing_brief(self, db, create_insight, mock_ai):
        """Returns stored brief."""
        create_insight(
            date="2026-02-03",
            type="daily_brief",
            content="Test content"
        )

        service = InsightsService(db, ai=mock_ai)
        result = service.get_daily_brief("2026-02-03")

        assert result is not None
        assert result.content == "Test content"

    def test_returns_none_when_no_brief(self, db, mock_ai):
        """Returns None when no brief exists."""
        service = InsightsService(db, ai=mock_ai)
        result = service.get_daily_brief("2026-02-03")

        assert result is None


class TestDetectPatterns:
    """Tests for detect_patterns method."""

    def test_uses_statistical_analyzer(
        self, db, generate_week_of_data, mock_ai, mock_analyzer
    ):
        """Uses PatternAnalyzer for statistical detection."""
        generate_week_of_data()

        service = InsightsService(db, ai=mock_ai, analyzer=mock_analyzer)
        patterns = service.detect_patterns(days=7, use_statistical=True, use_llm=False)

        mock_analyzer.analyze_all.assert_called_once()
        assert len(patterns) > 0

    def test_uses_llm_for_pattern_detection(
        self, db, generate_week_of_data, mock_ai
    ):
        """Uses LLM for pattern detection when requested."""
        generate_week_of_data()

        service = InsightsService(db, ai=mock_ai, analyzer=None)
        patterns = service.detect_patterns(days=7, use_statistical=False, use_llm=True)

        mock_ai.detect_patterns.assert_called_once()

    def test_stores_detected_patterns(
        self, db, generate_week_of_data, mock_ai, mock_analyzer
    ):
        """Stores detected patterns in database."""
        generate_week_of_data()

        service = InsightsService(db, ai=mock_ai, analyzer=mock_analyzer)
        service.detect_patterns(days=7, use_statistical=True, use_llm=False)

        stored = db.query(Pattern).all()
        assert len(stored) > 0

    def test_deduplicates_patterns(self, db, mock_ai, mock_analyzer):
        """Removes duplicate patterns with similar names."""
        # Setup analyzer to return duplicate patterns
        mock_analyzer.analyze_all.return_value = [
            MagicMock(
                name="Sleep-Energy Correlation",
                description="Desc 1",
                pattern_type="correlation",
                variables=["sleep", "energy"],
                strength=0.7,
                confidence=0.8,
                sample_size=30,
                actionable=True
            ),
            MagicMock(
                name="Sleep-Energy correlation",  # Same but different case
                description="Desc 2",
                pattern_type="correlation",
                variables=["sleep", "energy"],
                strength=0.75,
                confidence=0.85,
                sample_size=30,
                actionable=True
            )
        ]

        service = InsightsService(db, ai=mock_ai, analyzer=mock_analyzer)
        patterns = service._deduplicate_patterns(mock_analyzer.analyze_all())

        # Should keep only one
        assert len(patterns) == 1


class TestGetPatterns:
    """Tests for get_patterns method."""

    def test_returns_active_patterns_only(self, db, create_pattern, mock_ai):
        """Returns only active patterns when filtered."""
        create_pattern(name="Active", active=True)
        create_pattern(name="Inactive", active=False)

        service = InsightsService(db, ai=mock_ai)
        patterns = service.get_patterns(active_only=True)

        assert len(patterns) == 1
        assert patterns[0].name == "Active"

    def test_returns_all_patterns(self, db, create_pattern, mock_ai):
        """Returns all patterns when not filtered."""
        create_pattern(name="Active", active=True)
        create_pattern(name="Inactive", active=False)

        service = InsightsService(db, ai=mock_ai)
        patterns = service.get_patterns(active_only=False)

        assert len(patterns) == 2


class TestGetHistory:
    """Tests for _get_history helper."""

    def test_returns_recent_days(self, db, generate_week_of_data, mock_ai):
        """Returns context for recent days."""
        generate_week_of_data()

        service = InsightsService(db, ai=mock_ai)
        history = service._get_history(days=3)

        assert len(history) == 3

    def test_excludes_current_date(self, db, create_data_point, mock_ai):
        """Excludes the before_date from history."""
        today = date.today().isoformat()
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        create_data_point(date=today, type="sleep", value=7.0)
        create_data_point(date=yesterday, type="sleep", value=7.5)

        service = InsightsService(db, ai=mock_ai)
        history = service._get_history(days=2, before_date=today)

        dates = [ctx.date for ctx in history]
        assert today not in dates
        assert yesterday in dates


class TestGenerateWeeklyReview:
    """Tests for generate_weekly_review method."""

    def test_generates_weekly_review(
        self, db, generate_week_of_data, mock_ai, mock_personalization
    ):
        """Generates weekly review with aggregated data."""
        generate_week_of_data()

        service = InsightsService(
            db, ai=mock_ai, personalization=mock_personalization
        )
        result = service.generate_weekly_review()

        assert result is not None
        mock_ai.generate_weekly_review.assert_called_once()

    def test_stores_weekly_review(
        self, db, generate_week_of_data, mock_ai, mock_personalization
    ):
        """Stores weekly review in database."""
        generate_week_of_data()

        service = InsightsService(
            db, ai=mock_ai, personalization=mock_personalization
        )
        service.generate_weekly_review()

        stored = db.query(Insight).filter(
            Insight.type == "weekly_review"
        ).first()
        assert stored is not None


class TestForceRegenerate:
    """Tests for force_regenerate method."""

    def test_deletes_existing_and_regenerates(
        self, db, create_insight, create_data_point, mock_ai
    ):
        """Deletes existing insight and generates new one."""
        create_insight(
            date="2026-02-03",
            type="daily_brief",
            content="Old content"
        )
        create_data_point(date="2026-02-03", type="sleep", value=7.5)

        service = InsightsService(db, ai=mock_ai)
        result = service.force_regenerate("daily_brief", "2026-02-03")

        assert result is not None
        # Should have called AI
        mock_ai.generate_brief.assert_called_once()

        # Old insight should be gone
        insights = db.query(Insight).filter(
            Insight.date == "2026-02-03",
            Insight.type == "daily_brief"
        ).all()
        assert len(insights) == 1
        assert insights[0].content != "Old content"
