"""
LifeOS AI Engine

LiteLLM-powered intelligence for insights, briefs, and pattern detection.
"""

import os
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

from litellm import completion
from litellm.exceptions import APIError

from .config import settings


@dataclass
class SleepData:
    """Sleep data for a single night."""
    date: str
    duration_hours: float
    deep_sleep_hours: float
    rem_sleep_hours: float
    light_sleep_hours: float
    efficiency: float
    score: int
    bedtime: Optional[str] = None
    wake_time: Optional[str] = None


@dataclass
class DayContext:
    """Context for a single day used in brief generation."""
    date: str
    sleep: Optional[SleepData]
    readiness_score: Optional[int]
    activity_score: Optional[int]
    energy_log: Optional[int]  # 1-5 manual log
    calendar_events: List[Dict[str, Any]]
    notes: Optional[str] = None


@dataclass
class InsightResult:
    """Result from AI insight generation."""
    content: str
    confidence: float
    context: Dict[str, Any]
    tokens_used: int


@dataclass
class PatternResult:
    """A detected pattern."""
    name: str
    description: str
    pattern_type: str  # correlation, trend, anomaly
    variables: List[str]
    strength: float  # -1 to 1
    confidence: float
    sample_size: int
    actionable: bool


class LifeOSAI:
    """
    AI engine for LifeOS.

    Uses LiteLLM for model-agnostic AI calls.
    Supports personalization via preference context.
    """

    def __init__(
        self,
        model: str = None,
        api_key: str = None
    ):
        self.model = model or settings.litellm_model
        self.api_key = api_key or settings.get_ai_api_key()

        # Set API key in environment for LiteLLM
        if self.api_key:
            # LiteLLM reads from env vars
            if "claude" in self.model.lower() or "anthropic" in self.model.lower():
                os.environ["ANTHROPIC_API_KEY"] = self.api_key
            elif "gpt" in self.model.lower() or "openai" in self.model.lower():
                os.environ["OPENAI_API_KEY"] = self.api_key

    # === SYSTEM PROMPTS ===

    SYSTEM_PROMPT_BRIEF_BASE = """You are LifeOS, a personal AI assistant that helps optimize daily life.

Given the user's sleep data, calendar, and recent patterns, generate a brief, actionable morning summary. Be conversational, not clinical.

Focus on:
1. Sleep quality assessment (compare to their average)
2. Energy prediction for the day
3. One specific, actionable suggestion
4. Encouraging but honest tone

Keep it under 150 words. No bullet points - write naturally like a helpful friend.

IMPORTANT: Be specific with numbers. If sleep was 6h 12m, say that. If deep sleep was 1h 45m, mention it. Specificity builds trust."""

    # Alias for backwards compatibility
    SYSTEM_PROMPT_BRIEF = SYSTEM_PROMPT_BRIEF_BASE

    SYSTEM_PROMPT_PATTERN = """You are LifeOS pattern analyzer. Your job is to find actionable patterns in personal data.

Given historical data, identify correlations, trends, and anomalies that can help the user optimize their life.

Good patterns are:
- Specific and measurable ("Deep sleep drops 35% on days with >4h meetings")
- Actionable (user can do something about it)
- Based on sufficient data (mention sample size)
- Honest about confidence level

Avoid:
- Obvious statements ("You sleep less on busy days")
- Patterns with tiny sample sizes (<5 data points)
- Unactionable observations

Return patterns as JSON array."""

    SYSTEM_PROMPT_ENERGY = """You are LifeOS energy predictor. Based on sleep data and schedule, predict energy levels throughout the day.

Consider:
- Sleep duration vs personal average
- Deep sleep quality
- Meeting load and timing
- Historical patterns for this day of week

Return a prediction with:
- Overall energy level (1-10)
- Expected peak hours
- Expected low hours
- One optimization suggestion

Be practical and specific."""

    SYSTEM_PROMPT_WEEKLY = """You are LifeOS weekly reviewer. Summarize the user's week and identify key insights.

Include:
1. Sleep summary (avg duration, best/worst nights)
2. Energy patterns (high and low days)
3. Notable correlations observed
4. One key insight for next week
5. One celebration (what went well)

Tone: Supportive coach, not demanding boss. ~200 words."""

    # === PERSONALIZATION ===

    def build_personalized_brief_prompt(
        self,
        personalization_prompt: Optional[str] = None
    ) -> str:
        """
        Build a personalized system prompt for daily briefs.

        Args:
            personalization_prompt: User-specific preferences from PersonalizationService

        Returns:
            Complete system prompt with personalization
        """
        base_prompt = self.SYSTEM_PROMPT_BRIEF_BASE

        if not personalization_prompt:
            return base_prompt

        # Insert personalization after base instructions
        return f"""{base_prompt}

--- USER PREFERENCES ---
{personalization_prompt}
--- END PREFERENCES ---

Apply these preferences while maintaining helpfulness and specificity."""

    def build_personalized_weekly_prompt(
        self,
        personalization_prompt: Optional[str] = None
    ) -> str:
        """Build a personalized system prompt for weekly reviews."""
        base_prompt = self.SYSTEM_PROMPT_WEEKLY

        if not personalization_prompt:
            return base_prompt

        return f"""{base_prompt}

--- USER PREFERENCES ---
{personalization_prompt}
--- END PREFERENCES ---

Apply these preferences in your weekly summary."""

    # === CORE METHODS ===

    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        feature: str = "other"
    ) -> tuple[str, int, int, int]:
        """
        Make a call to the LLM via LiteLLM.

        Args:
            system_prompt: System prompt for the LLM
            user_prompt: User prompt
            temperature: Sampling temperature
            max_tokens: Max tokens to generate
            feature: Feature name for token tracking

        Returns: (response_text, total_tokens, input_tokens, output_tokens)
        """
        try:
            response = completion(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content

            # Extract token counts
            total_tokens = response.usage.total_tokens if response.usage else 0
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0

            # Log token usage
            self._log_token_usage(feature, input_tokens, output_tokens)

            return content, total_tokens, input_tokens, output_tokens

        except APIError as e:
            raise RuntimeError(f"LiteLLM API error: {e}")
        except Exception as e:
            raise RuntimeError(f"AI call failed: {e}")

    def _log_token_usage(
        self,
        feature: str,
        input_tokens: int,
        output_tokens: int
    ):
        """Log token usage to database if available."""
        try:
            from .token_tracker import AIFeature, TokenUsage
            from .database import SessionLocal

            # Map feature string to enum
            try:
                ai_feature = AIFeature(feature)
            except ValueError:
                ai_feature = AIFeature.OTHER

            db = SessionLocal()
            try:
                usage = TokenUsage(
                    feature=ai_feature.value,
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=input_tokens + output_tokens,
                    cost_usd=self._calculate_cost(input_tokens, output_tokens)
                )
                db.add(usage)
                db.commit()
            finally:
                db.close()
        except Exception:
            # Don't fail AI calls if token tracking fails
            pass

    def _calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost based on model pricing."""
        from .token_tracker import MODEL_PRICING

        model_lower = self.model.lower()
        pricing = MODEL_PRICING.get("default")

        for key, p in MODEL_PRICING.items():
            if key in model_lower:
                pricing = p
                break

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def generate_daily_brief(
        self,
        today: DayContext,
        history: List[DayContext],
        timezone: str = "UTC",
        personalization_prompt: Optional[str] = None
    ) -> InsightResult:
        """
        Generate a personalized morning brief.

        Args:
            today: Today's context (sleep, calendar, etc.)
            history: Last 7 days of context for comparison
            timezone: User's timezone
            personalization_prompt: Optional personalization context from PersonalizationService

        Returns:
            InsightResult with the brief content
        """
        # Calculate averages from history
        sleep_durations = [d.sleep.duration_hours for d in history if d.sleep]
        avg_sleep = sum(sleep_durations) / len(sleep_durations) if sleep_durations else 7.0

        deep_sleeps = [d.sleep.deep_sleep_hours for d in history if d.sleep]
        avg_deep = sum(deep_sleeps) / len(deep_sleeps) if deep_sleeps else 1.5

        # Build context for prompt
        prompt_parts = []

        # Today's sleep
        if today.sleep:
            sleep = today.sleep
            prompt_parts.append(f"""LAST NIGHT'S SLEEP:
- Duration: {sleep.duration_hours:.1f}h (your 7-day avg: {avg_sleep:.1f}h)
- Deep sleep: {sleep.deep_sleep_hours:.1f}h (your avg: {avg_deep:.1f}h)
- REM sleep: {sleep.rem_sleep_hours:.1f}h
- Sleep score: {sleep.score}/100
- Efficiency: {sleep.efficiency:.0%}""")

            if sleep.bedtime and sleep.wake_time:
                prompt_parts.append(f"- Bedtime: {sleep.bedtime}, Wake: {sleep.wake_time}")

        # Readiness
        if today.readiness_score:
            prompt_parts.append(f"\nREADINESS SCORE: {today.readiness_score}/100")

        # Calendar
        if today.calendar_events:
            meetings = [e for e in today.calendar_events if e.get('type') == 'meeting']
            total_meeting_hours = sum(e.get('duration_hours', 1) for e in meetings)
            prompt_parts.append(f"\nTODAY'S CALENDAR:")
            prompt_parts.append(f"- {len(meetings)} meetings ({total_meeting_hours:.1f}h total)")
            for event in today.calendar_events[:5]:
                time = event.get('time', 'TBD')
                title = event.get('title', 'Event')
                prompt_parts.append(f"- {time}: {title}")

        # Day of week pattern
        day_name = datetime.strptime(today.date, "%Y-%m-%d").strftime("%A")
        prompt_parts.append(f"\nTODAY: {day_name}, {today.date}")

        # Recent patterns
        recent_low_sleeps = sum(1 for d in history[-3:] if d.sleep and d.sleep.duration_hours < 6)
        if recent_low_sleeps >= 2:
            prompt_parts.append(f"\nNOTE: You've had {recent_low_sleeps} short sleep nights in the last 3 days.")

        user_prompt = "\n".join(prompt_parts)

        # Build personalized system prompt
        system_prompt = self.build_personalized_brief_prompt(personalization_prompt)

        # Call LLM
        content, tokens, _, _ = self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=300,
            feature="daily_brief"
        )

        return InsightResult(
            content=content,
            confidence=0.8,  # Default confidence
            context={
                "date": today.date,
                "sleep_hours": today.sleep.duration_hours if today.sleep else None,
                "avg_sleep_hours": avg_sleep,
                "calendar_events": len(today.calendar_events),
                "history_days": len(history)
            },
            tokens_used=tokens
        )

    def analyze_patterns(
        self,
        data_points: List[Dict[str, Any]],
        days: int = 30
    ) -> List[PatternResult]:
        """
        Analyze historical data to find actionable patterns.

        Args:
            data_points: List of data points with date, type, value
            days: Number of days of history to analyze

        Returns:
            List of detected patterns
        """
        if len(data_points) < 7:
            return []  # Need at least a week of data

        # Organize data by date
        by_date = {}
        for dp in data_points:
            date = dp.get('date')
            if date not in by_date:
                by_date[date] = {}
            by_date[date][dp.get('type')] = dp

        # Build data summary for prompt
        prompt_parts = [f"HISTORICAL DATA ({len(by_date)} days):"]

        # Sleep patterns
        sleep_data = [(d, by_date[d].get('sleep', {})) for d in sorted(by_date.keys())]
        if sleep_data:
            prompt_parts.append("\nSLEEP DATA:")
            for date, sleep in sleep_data[-14:]:  # Last 2 weeks
                if sleep:
                    day = datetime.strptime(date, "%Y-%m-%d").strftime("%a")
                    duration = sleep.get('value', 0)
                    deep = sleep.get('metadata', {}).get('deep_sleep_hours', 0)
                    prompt_parts.append(f"  {date} ({day}): {duration:.1f}h total, {deep:.1f}h deep")

        # Activity data
        activity_data = [(d, by_date[d].get('activity', {})) for d in sorted(by_date.keys())]
        if activity_data:
            prompt_parts.append("\nACTIVITY DATA:")
            for date, activity in activity_data[-14:]:
                if activity:
                    day = datetime.strptime(date, "%Y-%m-%d").strftime("%a")
                    score = activity.get('value', 0)
                    prompt_parts.append(f"  {date} ({day}): score {score}")

        # Energy logs
        energy_data = [(d, by_date[d].get('energy', {})) for d in sorted(by_date.keys())]
        if energy_data:
            prompt_parts.append("\nMANUAL ENERGY LOGS:")
            for date, energy in energy_data[-14:]:
                if energy:
                    day = datetime.strptime(date, "%Y-%m-%d").strftime("%a")
                    level = energy.get('value', 0)
                    prompt_parts.append(f"  {date} ({day}): {level}/5")

        prompt_parts.append("""
TASK: Identify 2-4 actionable patterns from this data. Look for:
- Day-of-week effects (weekday vs weekend)
- Sleep quality correlations
- Recovery patterns
- Trends over time

Return as JSON array:
[
  {
    "name": "Pattern name",
    "description": "Detailed description with specific numbers",
    "pattern_type": "correlation|trend|anomaly",
    "variables": ["sleep", "activity"],
    "strength": 0.7,
    "confidence": 0.8,
    "sample_size": 14,
    "actionable": true
  }
]""")

        user_prompt = "\n".join(prompt_parts)

        content, tokens, _, _ = self._call_llm(
            system_prompt=self.SYSTEM_PROMPT_PATTERN,
            user_prompt=user_prompt,
            temperature=0.5,  # Lower temp for more consistent JSON
            max_tokens=800,
            feature="pattern_detection"
        )

        # Parse JSON response
        try:
            # Find JSON array in response
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                patterns_json = json.loads(content[start:end])
                return [
                    PatternResult(
                        name=p.get('name', 'Unknown'),
                        description=p.get('description', ''),
                        pattern_type=p.get('pattern_type', 'correlation'),
                        variables=p.get('variables', []),
                        strength=float(p.get('strength', 0)),
                        confidence=float(p.get('confidence', 0.5)),
                        sample_size=int(p.get('sample_size', 0)),
                        actionable=bool(p.get('actionable', True))
                    )
                    for p in patterns_json
                ]
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, return empty list
            pass

        return []

    def predict_energy(
        self,
        today: DayContext,
        history: List[DayContext]
    ) -> Dict[str, Any]:
        """
        Predict energy levels for the day.

        Returns dict with:
        - overall: 1-10 energy level
        - peak_hours: list of expected high-energy hours
        - low_hours: list of expected low-energy hours
        - suggestion: one actionable tip
        """
        # Build context
        prompt_parts = []

        if today.sleep:
            sleep = today.sleep
            avg_duration = sum(d.sleep.duration_hours for d in history if d.sleep) / max(1, len([d for d in history if d.sleep]))
            sleep_delta = sleep.duration_hours - avg_duration

            prompt_parts.append(f"""LAST NIGHT:
- Sleep: {sleep.duration_hours:.1f}h ({'+' if sleep_delta >= 0 else ''}{sleep_delta:.1f}h vs average)
- Deep sleep: {sleep.deep_sleep_hours:.1f}h
- Score: {sleep.score}/100""")

        if today.calendar_events:
            meetings = [e for e in today.calendar_events if e.get('type') == 'meeting']
            prompt_parts.append(f"\nSCHEDULE:")
            prompt_parts.append(f"- {len(meetings)} meetings today")
            for event in meetings[:5]:
                prompt_parts.append(f"- {event.get('time', 'TBD')}: {event.get('title', 'Meeting')}")

        day_name = datetime.strptime(today.date, "%Y-%m-%d").strftime("%A")
        prompt_parts.append(f"\nDAY: {day_name}")

        prompt_parts.append("""
Predict my energy for today. Return JSON:
{
  "overall": 7,
  "peak_hours": ["9:00-11:00", "15:00-16:00"],
  "low_hours": ["14:00-15:00"],
  "suggestion": "One actionable tip"
}""")

        user_prompt = "\n".join(prompt_parts)

        content, _, _, _ = self._call_llm(
            system_prompt=self.SYSTEM_PROMPT_ENERGY,
            user_prompt=user_prompt,
            temperature=0.6,
            max_tokens=300,
            feature="energy_prediction"
        )

        # Parse JSON
        try:
            start = content.find('{')
            end = content.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(content[start:end])
        except:
            pass

        # Default prediction
        return {
            "overall": 5,
            "peak_hours": ["9:00-12:00"],
            "low_hours": ["14:00-16:00"],
            "suggestion": "Unable to generate prediction. Check your data."
        }

    def generate_weekly_review(
        self,
        week_data: List[DayContext],
        personalization_prompt: Optional[str] = None
    ) -> InsightResult:
        """
        Generate a weekly review summary.

        Args:
            week_data: 7 days of context data
            personalization_prompt: Optional personalization context from PersonalizationService

        Returns:
            InsightResult with weekly review
        """
        if not week_data:
            return InsightResult(
                content="Not enough data for weekly review.",
                confidence=0.0,
                context={},
                tokens_used=0
            )

        # Calculate weekly stats
        sleep_hours = [d.sleep.duration_hours for d in week_data if d.sleep]
        avg_sleep = sum(sleep_hours) / len(sleep_hours) if sleep_hours else 0
        best_sleep = max(sleep_hours) if sleep_hours else 0
        worst_sleep = min(sleep_hours) if sleep_hours else 0

        deep_sleeps = [d.sleep.deep_sleep_hours for d in week_data if d.sleep]
        avg_deep = sum(deep_sleeps) / len(deep_sleeps) if deep_sleeps else 0

        # Build prompt
        prompt_parts = [f"WEEK IN REVIEW ({len(week_data)} days):"]

        prompt_parts.append(f"""
SLEEP SUMMARY:
- Average: {avg_sleep:.1f}h/night
- Best night: {best_sleep:.1f}h
- Worst night: {worst_sleep:.1f}h
- Average deep sleep: {avg_deep:.1f}h

DAY BY DAY:""")

        for day in week_data:
            day_name = datetime.strptime(day.date, "%Y-%m-%d").strftime("%A")
            if day.sleep:
                prompt_parts.append(
                    f"- {day_name}: {day.sleep.duration_hours:.1f}h sleep, "
                    f"score {day.sleep.score}"
                )
            if day.energy_log:
                prompt_parts[-1] += f", energy {day.energy_log}/5"

        user_prompt = "\n".join(prompt_parts)

        # Build personalized system prompt
        system_prompt = self.build_personalized_weekly_prompt(personalization_prompt)

        content, tokens, _, _ = self._call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.7,
            max_tokens=400,
            feature="weekly_review"
        )

        return InsightResult(
            content=content,
            confidence=0.75,
            context={
                "days": len(week_data),
                "avg_sleep": avg_sleep,
                "avg_deep_sleep": avg_deep,
                "personalized": personalization_prompt is not None
            },
            tokens_used=tokens
        )


# Singleton instance
_ai_instance: Optional[LifeOSAI] = None


def get_ai() -> LifeOSAI:
    """Get or create the AI engine singleton."""
    global _ai_instance
    if _ai_instance is None:
        _ai_instance = LifeOSAI()
    return _ai_instance
