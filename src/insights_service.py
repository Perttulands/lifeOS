"""
LifeOS Insights Service

Business logic for generating, storing, and retrieving insights.
Bridges between database, AI engine, and API.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from .models import DataPoint, Insight, Pattern, JournalEntry
from .ai import (
    LifeOSAI, get_ai,
    SleepData, DayContext, InsightResult, PatternResult
)
from .pattern_analyzer import PatternAnalyzer, get_analyzer, DetectedPattern


class InsightsService:
    """Service for managing LifeOS insights."""

    def __init__(
        self,
        db: Session,
        ai: Optional[LifeOSAI] = None,
        analyzer: Optional[PatternAnalyzer] = None
    ):
        self.db = db
        self.ai = ai or get_ai()
        try:
            self.analyzer = analyzer or get_analyzer()
        except ImportError:
            # scipy not installed, statistical analysis disabled
            self.analyzer = None

    # === DATA HELPERS ===

    def _get_sleep_data(self, date: str) -> Optional[SleepData]:
        """Get sleep data for a specific date."""
        dp = self.db.query(DataPoint).filter(
            DataPoint.date == date,
            DataPoint.type == "sleep"
        ).first()

        if not dp:
            return None

        meta = dp.extra_data or {}
        return SleepData(
            date=dp.date,
            duration_hours=dp.value or 0,
            deep_sleep_hours=meta.get('deep_sleep_hours', 0),
            rem_sleep_hours=meta.get('rem_sleep_hours', 0),
            light_sleep_hours=meta.get('light_sleep_hours', 0),
            efficiency=meta.get('efficiency', 0),
            score=meta.get('score', 0),
            bedtime=meta.get('bedtime'),
            wake_time=meta.get('wake_time')
        )

    def _get_day_context(self, date: str) -> DayContext:
        """Build full context for a single day."""
        # Get sleep
        sleep = self._get_sleep_data(date)

        # Get readiness
        readiness_dp = self.db.query(DataPoint).filter(
            DataPoint.date == date,
            DataPoint.type == "readiness"
        ).first()
        readiness = int(readiness_dp.value) if readiness_dp else None

        # Get activity
        activity_dp = self.db.query(DataPoint).filter(
            DataPoint.date == date,
            DataPoint.type == "activity"
        ).first()
        activity = int(activity_dp.value) if activity_dp else None

        # Get energy log
        energy_entry = self.db.query(JournalEntry).filter(
            JournalEntry.date == date
        ).order_by(JournalEntry.created_at.desc()).first()
        energy = energy_entry.energy if energy_entry else None

        # Get calendar (placeholder - would come from calendar integration)
        # For now, check if we have calendar data in metadata
        calendar_dp = self.db.query(DataPoint).filter(
            DataPoint.date == date,
            DataPoint.type == "calendar"
        ).first()
        calendar_events = calendar_dp.extra_data.get('events', []) if calendar_dp else []

        return DayContext(
            date=date,
            sleep=sleep,
            readiness_score=readiness,
            activity_score=activity,
            energy_log=energy,
            calendar_events=calendar_events,
            notes=energy_entry.notes if energy_entry else None
        )

    def _get_history(self, days: int = 7, before_date: str = None) -> List[DayContext]:
        """Get historical context for the last N days."""
        if before_date:
            end = datetime.strptime(before_date, "%Y-%m-%d")
        else:
            end = datetime.now()

        history = []
        for i in range(1, days + 1):
            date = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            context = self._get_day_context(date)
            if context.sleep or context.energy_log:  # Only include days with data
                history.append(context)

        return history

    def _get_data_points(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get all data points for pattern analysis."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        dps = self.db.query(DataPoint).filter(
            DataPoint.date >= cutoff
        ).all()

        return [
            {
                'date': dp.date,
                'type': dp.type,
                'value': dp.value,
                'metadata': dp.extra_data
            }
            for dp in dps
        ]

    # === INSIGHT GENERATION ===

    def generate_daily_brief(self, date: str = None) -> Insight:
        """
        Generate and store today's daily brief.

        Args:
            date: Date string (defaults to today)

        Returns:
            Insight object with the brief
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Check if we already have a brief for today
        existing = self.db.query(Insight).filter(
            Insight.date == date,
            Insight.type == "daily_brief"
        ).first()

        if existing:
            return existing

        # Get today's context
        today = self._get_day_context(date)

        # Get history for comparison
        history = self._get_history(days=7, before_date=date)

        # Generate brief
        result = self.ai.generate_daily_brief(today, history)

        # Store insight
        insight = Insight(
            type="daily_brief",
            date=date,
            content=result.content,
            context=result.context,
            confidence=result.confidence
        )
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)

        return insight

    def get_daily_brief(self, date: str = None) -> Optional[Insight]:
        """Get the daily brief for a specific date."""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        return self.db.query(Insight).filter(
            Insight.date == date,
            Insight.type == "daily_brief"
        ).first()

    def detect_patterns(
        self,
        days: int = 30,
        force: bool = False,
        use_statistical: bool = True,
        use_llm: bool = False
    ) -> List[Pattern]:
        """
        Detect patterns using statistical analysis and optionally LLM.

        Args:
            days: Days of history to analyze
            force: Whether to detect even if recent patterns exist
            use_statistical: Use statistical correlation/trend analysis
            use_llm: Also use LLM for additional pattern discovery

        Returns:
            List of Pattern objects
        """
        # Check for recent pattern detection
        if not force:
            recent = self.db.query(Pattern).filter(
                Pattern.discovered_at > datetime.utcnow() - timedelta(days=1)
            ).first()
            if recent:
                return self.db.query(Pattern).filter(
                    Pattern.active == True
                ).all()

        # Get data for analysis
        data_points = self._get_data_points(days)

        if len(data_points) < 7:
            return []

        all_results = []

        # Run statistical pattern detection (primary method)
        if use_statistical and self.analyzer:
            stat_patterns = self._run_statistical_analysis(data_points)
            all_results.extend(stat_patterns)

        # Optionally run LLM pattern detection
        if use_llm:
            llm_results = self.ai.analyze_patterns(data_points, days)
            # Convert LLM results to same format
            for r in llm_results:
                all_results.append(DetectedPattern(
                    name=r.name,
                    description=r.description,
                    pattern_type=r.pattern_type,
                    variables=r.variables,
                    strength=r.strength,
                    confidence=r.confidence,
                    sample_size=r.sample_size,
                    actionable=r.actionable,
                    details={'source': 'llm'}
                ))

        # Deduplicate patterns (similar names/variables)
        unique_results = self._deduplicate_patterns(all_results)

        # Deactivate old patterns
        self.db.query(Pattern).update({Pattern.active: False})

        # Store new patterns
        patterns = []
        for r in unique_results:
            pattern = Pattern(
                name=r.name,
                description=r.description,
                pattern_type=r.pattern_type,
                variables=r.variables,
                strength=r.strength,
                confidence=r.confidence,
                sample_size=r.sample_size,
                actionable=r.actionable,
                active=True
            )
            self.db.add(pattern)
            patterns.append(pattern)

        self.db.commit()
        return patterns

    def _run_statistical_analysis(
        self,
        data_points: List[Dict[str, Any]]
    ) -> List[DetectedPattern]:
        """Run statistical pattern analysis."""
        if not self.analyzer:
            return []

        try:
            # Run all statistical analyses
            patterns = self.analyzer.analyze_all(data_points)

            # Also run sliding window analysis
            organized = self.analyzer._organize_data(data_points)
            window_patterns = self.analyzer.analyze_sliding_window(organized)
            patterns.extend(window_patterns)

            return patterns
        except Exception as e:
            # Log error but don't fail
            print(f"Statistical analysis error: {e}")
            return []

    def _deduplicate_patterns(
        self,
        patterns: List[DetectedPattern]
    ) -> List[DetectedPattern]:
        """Remove duplicate patterns, keeping highest confidence."""
        seen = {}

        for p in patterns:
            # Create a key based on pattern type and variables
            key = (p.pattern_type, tuple(sorted(p.variables)))

            if key not in seen or p.confidence > seen[key].confidence:
                seen[key] = p

        return list(seen.values())

    def get_patterns(self, active_only: bool = True) -> List[Pattern]:
        """Get stored patterns."""
        query = self.db.query(Pattern)
        if active_only:
            query = query.filter(Pattern.active == True)
        return query.order_by(Pattern.confidence.desc()).all()

    def get_energy_prediction(self, date: str = None) -> Dict[str, Any]:
        """
        Get energy prediction for a date.

        Args:
            date: Date string (defaults to today)

        Returns:
            Dict with energy prediction
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Check for cached prediction
        existing = self.db.query(Insight).filter(
            Insight.date == date,
            Insight.type == "energy_prediction"
        ).first()

        if existing:
            return existing.context

        # Generate prediction
        today = self._get_day_context(date)
        history = self._get_history(days=7, before_date=date)

        prediction = self.ai.predict_energy(today, history)

        # Record LLM prediction for comparison tracking
        try:
            from .energy_predictor import get_prediction_comparator
            comparator = get_prediction_comparator()
            overall = prediction.get('overall', 5)
            comparator.record_llm_prediction(date, float(overall), 0.7)
        except ImportError:
            pass  # energy_predictor not available

        # Store as insight
        insight = Insight(
            type="energy_prediction",
            date=date,
            content=prediction.get('suggestion', ''),
            context=prediction,
            confidence=0.7
        )
        self.db.add(insight)
        self.db.commit()

        return prediction

    def generate_weekly_review(self, week_ending: str = None) -> Insight:
        """
        Generate weekly review.

        Args:
            week_ending: Last date of the week (defaults to today)

        Returns:
            Insight with weekly review
        """
        if week_ending is None:
            week_ending = datetime.now().strftime("%Y-%m-%d")

        # Check for existing
        existing = self.db.query(Insight).filter(
            Insight.date == week_ending,
            Insight.type == "weekly_review"
        ).first()

        if existing:
            return existing

        # Get week's data
        week_data = []
        end = datetime.strptime(week_ending, "%Y-%m-%d")
        for i in range(7):
            date = (end - timedelta(days=i)).strftime("%Y-%m-%d")
            context = self._get_day_context(date)
            week_data.append(context)

        week_data.reverse()  # Chronological order

        # Generate review
        result = self.ai.generate_weekly_review(week_data)

        # Store
        insight = Insight(
            type="weekly_review",
            date=week_ending,
            content=result.content,
            context=result.context,
            confidence=result.confidence
        )
        self.db.add(insight)
        self.db.commit()
        self.db.refresh(insight)

        return insight

    def get_recent_insights(self, days: int = 7, types: List[str] = None) -> List[Insight]:
        """Get recent insights of specified types."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        query = self.db.query(Insight).filter(Insight.date >= cutoff)

        if types:
            query = query.filter(Insight.type.in_(types))

        return query.order_by(Insight.created_at.desc()).all()

    def force_regenerate(self, insight_type: str, date: str = None) -> Insight:
        """
        Force regeneration of an insight.

        Args:
            insight_type: Type of insight (daily_brief, weekly_review, etc.)
            date: Date string

        Returns:
            New insight
        """
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")

        # Delete existing
        self.db.query(Insight).filter(
            Insight.date == date,
            Insight.type == insight_type
        ).delete()
        self.db.commit()

        # Generate new
        if insight_type == "daily_brief":
            return self.generate_daily_brief(date)
        elif insight_type == "weekly_review":
            return self.generate_weekly_review(date)
        elif insight_type == "energy_prediction":
            self.get_energy_prediction(date)
            return self.db.query(Insight).filter(
                Insight.date == date,
                Insight.type == "energy_prediction"
            ).first()
        else:
            raise ValueError(f"Unknown insight type: {insight_type}")
