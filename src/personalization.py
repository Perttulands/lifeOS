"""
LifeOS Personalization Service

Learns user preferences over time and provides personalized context
for AI-generated insights.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session
from sqlalchemy import func

from .models import UserPreference, InsightFeedback, Insight, JournalEntry, Pattern


@dataclass
class PreferenceContext:
    """Aggregated preference context for prompt personalization."""
    tone_style: str  # casual, professional, concise, detailed
    focus_areas: List[str]  # sleep, energy, productivity, recovery
    include_comparisons: bool  # show vs-average comparisons
    include_predictions: bool  # include energy predictions
    preferred_insight_length: str  # short, medium, long
    active_patterns: List[str]  # patterns user cares about
    raw_preferences: Dict[str, Any]  # all preferences for custom use


class PersonalizationService:
    """
    Service for learning and applying user preferences.

    Learns from:
    - Explicit feedback (thumbs up/down on insights)
    - Implicit signals (which insights are acted on)
    - Usage patterns (time of day, interaction frequency)
    - Historical data (energy logs, patterns)
    """

    # Default preference values
    DEFAULTS = {
        'tone': {
            'style': 'casual',  # casual, professional, concise, detailed
        },
        'focus': {
            'areas': ['sleep', 'energy'],  # What user cares about most
            'show_comparisons': True,
            'show_predictions': True,
        },
        'content': {
            'insight_length': 'medium',  # short, medium, long
            'include_numbers': True,
            'include_suggestions': True,
        },
        'schedule': {
            'is_morning_person': None,  # True, False, or None (unknown)
            'peak_hours': None,  # Learned peak productivity hours
        }
    }

    # Weight decay factor (preferences decay if not reinforced)
    WEIGHT_DECAY = 0.95

    # Minimum weight to keep a preference
    MIN_WEIGHT = 0.1

    def __init__(self, db: Session):
        self.db = db

    def get_preference(
        self,
        category: str,
        key: str,
        user_id: int = 1
    ) -> Optional[Any]:
        """Get a specific preference value."""
        pref = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
            UserPreference.key == key
        ).first()

        if pref:
            return pref.value

        # Return default if exists
        if category in self.DEFAULTS and key in self.DEFAULTS[category]:
            return self.DEFAULTS[category][key]

        return None

    def get_all_preferences(self, user_id: int = 1) -> Dict[str, Dict[str, Any]]:
        """Get all preferences organized by category."""
        prefs = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.weight >= self.MIN_WEIGHT
        ).all()

        # Start with defaults
        result = {cat: dict(vals) for cat, vals in self.DEFAULTS.items()}

        # Override with stored preferences
        for pref in prefs:
            if pref.category not in result:
                result[pref.category] = {}
            result[pref.category][pref.key] = pref.value

        return result

    def set_preference(
        self,
        category: str,
        key: str,
        value: Any,
        source: str = "explicit",
        user_id: int = 1
    ) -> UserPreference:
        """Set a preference explicitly."""
        pref = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
            UserPreference.key == key
        ).first()

        if pref:
            pref.value = value
            pref.source = source
            pref.weight = 1.0 if source == "explicit" else pref.weight
            pref.evidence_count += 1
            pref.last_reinforced = datetime.utcnow()
        else:
            pref = UserPreference(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                weight=1.0 if source == "explicit" else 0.5,
                source=source,
                evidence_count=1
            )
            self.db.add(pref)

        self.db.commit()
        self.db.refresh(pref)
        return pref

    def reinforce_preference(
        self,
        category: str,
        key: str,
        positive: bool = True,
        user_id: int = 1
    ) -> Optional[UserPreference]:
        """Reinforce or weaken a preference based on feedback."""
        pref = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
            UserPreference.key == key
        ).first()

        if not pref:
            return None

        # Adjust weight based on feedback
        if positive:
            pref.weight = min(1.0, pref.weight + 0.1)
            pref.evidence_count += 1
        else:
            pref.weight = max(0.0, pref.weight - 0.15)

        pref.last_reinforced = datetime.utcnow()
        self.db.commit()
        return pref

    def record_feedback(
        self,
        insight_id: int,
        feedback_type: str,
        context: Dict[str, Any] = None,
        user_id: int = 1
    ) -> InsightFeedback:
        """
        Record feedback on an insight.

        feedback_type: helpful, not_helpful, acted_on, dismissed
        """
        feedback = InsightFeedback(
            user_id=user_id,
            insight_id=insight_id,
            feedback_type=feedback_type,
            context=context or {}
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)

        # Learn from feedback
        self._learn_from_feedback(insight_id, feedback_type, user_id)

        return feedback

    def _learn_from_feedback(
        self,
        insight_id: int,
        feedback_type: str,
        user_id: int
    ):
        """Learn preferences from insight feedback."""
        insight = self.db.query(Insight).filter(Insight.id == insight_id).first()
        if not insight:
            return

        # Mark insight as acted on if applicable
        if feedback_type == "acted_on":
            insight.acted_on = True
            self.db.commit()

        # Analyze insight context to learn preferences
        context = insight.context or {}

        # If user found brief helpful, reinforce current settings
        if feedback_type in ("helpful", "acted_on"):
            # Reinforce focus areas based on insight content
            if "sleep" in insight.content.lower():
                self._update_inferred_preference(
                    "focus", "areas", "sleep", positive=True, user_id=user_id
                )
            if "energy" in insight.content.lower():
                self._update_inferred_preference(
                    "focus", "areas", "energy", positive=True, user_id=user_id
                )

            # Reinforce content length preference
            word_count = len(insight.content.split())
            if word_count < 50:
                self._update_inferred_preference(
                    "content", "insight_length", "short", positive=True, user_id=user_id
                )
            elif word_count > 150:
                self._update_inferred_preference(
                    "content", "insight_length", "long", positive=True, user_id=user_id
                )
            else:
                self._update_inferred_preference(
                    "content", "insight_length", "medium", positive=True, user_id=user_id
                )

        elif feedback_type == "not_helpful":
            # Weaken current settings
            word_count = len(insight.content.split())
            if word_count < 50:
                self._update_inferred_preference(
                    "content", "insight_length", "short", positive=False, user_id=user_id
                )
            elif word_count > 150:
                self._update_inferred_preference(
                    "content", "insight_length", "long", positive=False, user_id=user_id
                )

    def _update_inferred_preference(
        self,
        category: str,
        key: str,
        value: Any,
        positive: bool,
        user_id: int
    ):
        """Update an inferred preference based on behavior."""
        pref = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.category == category,
            UserPreference.key == key
        ).first()

        if pref:
            if pref.source == "explicit":
                # Don't override explicit preferences
                return

            if positive:
                # If same value, reinforce; otherwise weaken
                if pref.value == value:
                    pref.weight = min(1.0, pref.weight + 0.05)
                    pref.evidence_count += 1
                else:
                    pref.weight = max(0.0, pref.weight - 0.05)
            else:
                if pref.value == value:
                    pref.weight = max(0.0, pref.weight - 0.1)

            pref.last_reinforced = datetime.utcnow()
        else:
            # Create new inferred preference
            if positive:
                pref = UserPreference(
                    user_id=user_id,
                    category=category,
                    key=key,
                    value=value,
                    weight=0.3,  # Start with low confidence for inferred
                    source="inferred",
                    evidence_count=1
                )
                self.db.add(pref)

        self.db.commit()

    def learn_from_patterns(self, user_id: int = 1):
        """Learn preferences from detected patterns and historical data."""
        # Analyze energy logs to determine if user is morning/evening person
        recent_logs = self.db.query(JournalEntry).filter(
            JournalEntry.user_id == user_id,
            JournalEntry.energy.isnot(None),
            JournalEntry.time.isnot(None)
        ).order_by(JournalEntry.created_at.desc()).limit(30).all()

        if len(recent_logs) >= 7:
            morning_energy = []
            evening_energy = []

            for log in recent_logs:
                if log.time:
                    hour = int(log.time.split(":")[0])
                    if 6 <= hour < 12:
                        morning_energy.append(log.energy)
                    elif 18 <= hour < 23:
                        evening_energy.append(log.energy)

            if len(morning_energy) >= 3 and len(evening_energy) >= 3:
                avg_morning = sum(morning_energy) / len(morning_energy)
                avg_evening = sum(evening_energy) / len(evening_energy)

                if avg_morning > avg_evening + 0.5:
                    self.set_preference(
                        "schedule", "is_morning_person", True,
                        source="inferred", user_id=user_id
                    )
                elif avg_evening > avg_morning + 0.5:
                    self.set_preference(
                        "schedule", "is_morning_person", False,
                        source="inferred", user_id=user_id
                    )

        # Learn focus areas from most frequent pattern topics
        active_patterns = self.db.query(Pattern).filter(
            Pattern.user_id == user_id,
            Pattern.active == True
        ).all()

        if active_patterns:
            topic_counts: Dict[str, int] = {}
            for pattern in active_patterns:
                for var in (pattern.variables or []):
                    topic_counts[var] = topic_counts.get(var, 0) + 1

            # Get top 3 topics
            top_topics = sorted(
                topic_counts.items(), key=lambda x: x[1], reverse=True
            )[:3]

            if top_topics:
                focus_areas = [topic for topic, _ in top_topics]
                self.set_preference(
                    "focus", "areas", focus_areas,
                    source="inferred", user_id=user_id
                )

    def decay_preferences(self, user_id: int = 1):
        """Apply decay to preferences that haven't been reinforced recently."""
        cutoff = datetime.utcnow() - timedelta(days=7)

        old_prefs = self.db.query(UserPreference).filter(
            UserPreference.user_id == user_id,
            UserPreference.source == "inferred",
            UserPreference.last_reinforced < cutoff
        ).all()

        for pref in old_prefs:
            pref.weight *= self.WEIGHT_DECAY
            if pref.weight < self.MIN_WEIGHT:
                self.db.delete(pref)

        self.db.commit()

    def get_preference_context(self, user_id: int = 1) -> PreferenceContext:
        """Get aggregated preference context for AI prompts."""
        prefs = self.get_all_preferences(user_id)

        # Get active patterns for context
        active_patterns = self.db.query(Pattern).filter(
            Pattern.user_id == user_id,
            Pattern.active == True,
            Pattern.actionable == True
        ).order_by(Pattern.confidence.desc()).limit(5).all()

        pattern_names = [p.name for p in active_patterns]

        return PreferenceContext(
            tone_style=prefs.get('tone', {}).get('style', 'casual'),
            focus_areas=prefs.get('focus', {}).get('areas', ['sleep', 'energy']),
            include_comparisons=prefs.get('focus', {}).get('show_comparisons', True),
            include_predictions=prefs.get('focus', {}).get('show_predictions', True),
            preferred_insight_length=prefs.get('content', {}).get('insight_length', 'medium'),
            active_patterns=pattern_names,
            raw_preferences=prefs
        )

    def build_personalization_prompt(self, user_id: int = 1) -> str:
        """Build a prompt section describing user preferences for the AI."""
        ctx = self.get_preference_context(user_id)

        sections = []

        # Tone/style
        tone_map = {
            'casual': 'Use a friendly, conversational tone like a helpful friend.',
            'professional': 'Use a clear, professional tone focused on data.',
            'concise': 'Be extremely brief - bullet points over paragraphs.',
            'detailed': 'Provide thorough explanations with context.',
        }
        sections.append(f"COMMUNICATION STYLE: {tone_map.get(ctx.tone_style, tone_map['casual'])}")

        # Focus areas
        if ctx.focus_areas:
            sections.append(f"USER PRIORITIES: Focus especially on {', '.join(ctx.focus_areas)}.")

        # Length preference
        length_map = {
            'short': 'Keep response under 75 words.',
            'medium': 'Keep response between 100-150 words.',
            'long': 'Provide detailed response up to 200 words.',
        }
        sections.append(length_map.get(ctx.preferred_insight_length, length_map['medium']))

        # Active patterns to reference
        if ctx.active_patterns:
            sections.append(
                f"KNOWN PATTERNS: Reference these established patterns if relevant: {', '.join(ctx.active_patterns[:3])}"
            )

        # Schedule preferences
        schedule = ctx.raw_preferences.get('schedule', {})
        if schedule.get('is_morning_person') is True:
            sections.append("Note: User is a morning person - frame advice around morning productivity.")
        elif schedule.get('is_morning_person') is False:
            sections.append("Note: User is an evening person - don't push early morning schedules.")

        return "\n".join(sections)


# Singleton instance
_personalization_instance: Optional[PersonalizationService] = None


def get_personalization(db: Session) -> PersonalizationService:
    """Get personalization service instance."""
    return PersonalizationService(db)
