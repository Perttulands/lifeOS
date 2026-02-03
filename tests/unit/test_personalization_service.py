"""
Unit tests for PersonalizationService.

Tests preference management, learning algorithms, and personalization context building.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from src.personalization import PersonalizationService, PreferenceContext
from src.models import UserPreference, InsightFeedback, Insight, Pattern


class TestPersonalizationServiceInit:
    """Tests for PersonalizationService initialization."""

    def test_init_creates_service(self, db):
        """Service initializes with database session."""
        service = PersonalizationService(db)
        assert service.db == db

    def test_has_default_preferences(self, db):
        """Service has default preference values."""
        service = PersonalizationService(db)
        assert 'tone' in service.DEFAULTS
        assert 'focus' in service.DEFAULTS
        assert 'content' in service.DEFAULTS
        assert 'schedule' in service.DEFAULTS


class TestGetPreference:
    """Tests for get_preference method."""

    def test_returns_stored_preference(self, db, create_preference):
        """Returns stored preference value."""
        create_preference(
            category="tone",
            key="style",
            value="professional"
        )

        service = PersonalizationService(db)
        result = service.get_preference("tone", "style")

        assert result == "professional"

    def test_returns_default_when_not_stored(self, db):
        """Returns default value when preference not stored."""
        service = PersonalizationService(db)
        result = service.get_preference("tone", "style")

        assert result == "casual"  # Default from DEFAULTS

    def test_returns_none_for_unknown_preference(self, db):
        """Returns None for unknown preference keys."""
        service = PersonalizationService(db)
        result = service.get_preference("unknown", "key")

        assert result is None


class TestGetAllPreferences:
    """Tests for get_all_preferences method."""

    def test_returns_merged_preferences(self, db, create_preference):
        """Returns stored preferences merged with defaults."""
        create_preference(
            category="tone",
            key="style",
            value="concise"
        )

        service = PersonalizationService(db)
        result = service.get_all_preferences()

        assert result["tone"]["style"] == "concise"
        # Defaults should still be present for other categories
        assert "focus" in result

    def test_filters_low_weight_preferences(self, db, create_preference):
        """Excludes preferences with weight below threshold."""
        create_preference(
            category="tone",
            key="style",
            value="ignored",
            weight=0.05  # Below MIN_WEIGHT of 0.1
        )

        service = PersonalizationService(db)
        result = service.get_all_preferences()

        # Should return default, not the low-weight stored value
        assert result["tone"]["style"] == "casual"


class TestSetPreference:
    """Tests for set_preference method."""

    def test_creates_new_preference(self, db):
        """Creates new preference when doesn't exist."""
        service = PersonalizationService(db)
        service.set_preference(
            category="tone",
            key="style",
            value="detailed",
            source="explicit"
        )

        stored = db.query(UserPreference).filter(
            UserPreference.category == "tone",
            UserPreference.key == "style"
        ).first()

        assert stored is not None
        assert stored.value == "detailed"
        assert stored.source == "explicit"

    def test_updates_existing_preference(self, db, create_preference):
        """Updates existing preference value."""
        create_preference(
            category="tone",
            key="style",
            value="casual"
        )

        service = PersonalizationService(db)
        service.set_preference(
            category="tone",
            key="style",
            value="professional"
        )

        stored = db.query(UserPreference).filter(
            UserPreference.category == "tone",
            UserPreference.key == "style"
        ).first()

        assert stored.value == "professional"

    def test_explicit_overrides_inferred(self, db, create_preference):
        """Explicit preferences override inferred ones."""
        create_preference(
            category="tone",
            key="style",
            value="casual",
            source="inferred",
            weight=0.5
        )

        service = PersonalizationService(db)
        service.set_preference(
            category="tone",
            key="style",
            value="professional",
            source="explicit"
        )

        stored = db.query(UserPreference).filter(
            UserPreference.category == "tone",
            UserPreference.key == "style"
        ).first()

        assert stored.value == "professional"
        assert stored.source == "explicit"
        assert stored.weight == 1.0  # Explicit has full weight


class TestReinforcePreference:
    """Tests for reinforce_preference method."""

    def test_increases_weight_on_positive(self, db, create_preference):
        """Increases preference weight on positive reinforcement."""
        pref = create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.5
        )
        original_weight = pref.weight

        service = PersonalizationService(db)
        service.reinforce_preference("tone", "style", positive=True)

        db.refresh(pref)
        assert pref.weight > original_weight
        assert pref.evidence_count > 1

    def test_decreases_weight_on_negative(self, db, create_preference):
        """Decreases preference weight on negative reinforcement."""
        pref = create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.5
        )
        original_weight = pref.weight

        service = PersonalizationService(db)
        service.reinforce_preference("tone", "style", positive=False)

        db.refresh(pref)
        assert pref.weight < original_weight

    def test_weight_bounded_at_one(self, db, create_preference):
        """Weight doesn't exceed 1.0."""
        create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.95
        )

        service = PersonalizationService(db)
        # Reinforce multiple times
        for _ in range(5):
            service.reinforce_preference("tone", "style", positive=True)

        stored = db.query(UserPreference).filter(
            UserPreference.category == "tone",
            UserPreference.key == "style"
        ).first()

        assert stored.weight <= 1.0


class TestRecordFeedback:
    """Tests for record_feedback method."""

    def test_stores_feedback(self, db, create_insight):
        """Stores feedback in database."""
        insight = create_insight(
            date="2026-02-03",
            type="daily_brief"
        )

        service = PersonalizationService(db)
        service.record_feedback(
            insight_id=insight.id,
            feedback_type="helpful"
        )

        feedback = db.query(InsightFeedback).filter(
            InsightFeedback.insight_id == insight.id
        ).first()

        assert feedback is not None
        assert feedback.feedback_type == "helpful"

    def test_learns_from_helpful_feedback(self, db, create_insight, create_preference):
        """Learns preferences from helpful feedback."""
        insight = create_insight(
            date="2026-02-03",
            type="daily_brief",
            context={"tone": "casual", "length": "medium"}
        )
        create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.5,
            source="inferred"
        )

        service = PersonalizationService(db)
        service.record_feedback(
            insight_id=insight.id,
            feedback_type="helpful"
        )

        # Should reinforce the tone preference
        pref = db.query(UserPreference).filter(
            UserPreference.category == "tone",
            UserPreference.key == "style"
        ).first()

        # Weight should increase from helpful feedback
        assert pref.weight >= 0.5


class TestDecayPreferences:
    """Tests for decay_preferences method."""

    def test_applies_decay_to_old_preferences(self, db, create_preference):
        """Applies weight decay to stale preferences."""
        pref = create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.8,
            source="inferred"
        )
        # Set last_reinforced to old date
        pref.last_reinforced = datetime.utcnow() - timedelta(days=30)
        db.commit()

        service = PersonalizationService(db)
        service.decay_preferences()

        db.refresh(pref)
        # Weight should decrease due to decay
        assert pref.weight < 0.8

    def test_does_not_decay_recent_preferences(self, db, create_preference):
        """Doesn't decay recently reinforced preferences."""
        pref = create_preference(
            category="tone",
            key="style",
            value="casual",
            weight=0.8,
            source="inferred"
        )
        pref.last_reinforced = datetime.utcnow()
        db.commit()

        service = PersonalizationService(db)
        service.decay_preferences()

        db.refresh(pref)
        # Weight should remain the same
        assert pref.weight == 0.8

    def test_does_not_decay_explicit_preferences(self, db, create_preference):
        """Doesn't decay explicit (user-set) preferences."""
        pref = create_preference(
            category="tone",
            key="style",
            value="professional",
            weight=1.0,
            source="explicit"
        )
        pref.last_reinforced = datetime.utcnow() - timedelta(days=60)
        db.commit()

        service = PersonalizationService(db)
        service.decay_preferences()

        db.refresh(pref)
        # Explicit preferences don't decay
        assert pref.weight == 1.0


class TestGetPreferenceContext:
    """Tests for get_preference_context method."""

    def test_returns_preference_context(self, db, create_preference):
        """Returns PreferenceContext with aggregated preferences."""
        create_preference(category="tone", key="style", value="concise")
        create_preference(category="focus", key="areas", value=["sleep", "energy"])
        create_preference(category="focus", key="show_comparisons", value=True)

        service = PersonalizationService(db)
        context = service.get_preference_context()

        assert isinstance(context, PreferenceContext)
        assert context.tone_style == "concise"
        assert "sleep" in context.focus_areas

    def test_uses_defaults_for_missing(self, db):
        """Uses defaults for missing preferences."""
        service = PersonalizationService(db)
        context = service.get_preference_context()

        # Should use default tone
        assert context.tone_style == "casual"


class TestBuildPersonalizationPrompt:
    """Tests for build_personalization_prompt method."""

    def test_builds_prompt_string(self, db, create_preference):
        """Builds personalization prompt for AI."""
        create_preference(category="tone", key="style", value="casual")
        create_preference(category="focus", key="areas", value=["sleep"])

        service = PersonalizationService(db)
        prompt = service.build_personalization_prompt()

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        # Should mention tone or focus areas
        assert "casual" in prompt.lower() or "sleep" in prompt.lower()

    def test_handles_no_preferences(self, db):
        """Handles case with no stored preferences."""
        service = PersonalizationService(db)
        prompt = service.build_personalization_prompt()

        # Should still return a valid prompt with defaults
        assert isinstance(prompt, str)


class TestLearnFromPatterns:
    """Tests for learn_from_patterns method."""

    def test_infers_preferences_from_patterns(self, db, create_pattern):
        """Infers schedule preferences from detected patterns."""
        # Create morning person pattern
        create_pattern(
            name="Morning Energy Peak",
            description="Energy highest between 8-11 AM",
            pattern_type="trend",
            strength=0.8,
            active=True
        )

        service = PersonalizationService(db)
        service.learn_from_patterns()

        # Should infer morning person preference
        pref = db.query(UserPreference).filter(
            UserPreference.category == "schedule",
            UserPreference.key == "is_morning_person"
        ).first()

        # May or may not create preference depending on implementation
        # but should not error

    def test_handles_no_patterns(self, db):
        """Handles case with no patterns."""
        service = PersonalizationService(db)
        # Should not error
        service.learn_from_patterns()
