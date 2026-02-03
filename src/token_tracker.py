"""
LifeOS Token Cost Tracking

Tracks token usage per AI call and calculates costs per feature.
"""
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

from sqlalchemy import Column, Integer, String, Float, DateTime, Index
from sqlalchemy.orm import Session

from .database import Base


class AIFeature(Enum):
    """Features that use AI calls."""
    DAILY_BRIEF = "daily_brief"
    WEEKLY_REVIEW = "weekly_review"
    ENERGY_PREDICTION = "energy_prediction"
    PATTERN_DETECTION = "pattern_detection"
    CAPTURE = "capture"
    GOAL_BREAKDOWN = "goal_breakdown"
    OTHER = "other"


# Pricing per 1M tokens (as of 2024)
# These are estimates - actual costs vary by provider
MODEL_PRICING = {
    # Anthropic Claude
    "claude-3-opus": {"input": 15.0, "output": 75.0},
    "claude-3-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    # OpenAI
    "gpt-4": {"input": 30.0, "output": 60.0},
    "gpt-4-turbo": {"input": 10.0, "output": 30.0},
    "gpt-4o": {"input": 5.0, "output": 15.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
    # Default fallback
    "default": {"input": 3.0, "output": 15.0}
}


class TokenUsage(Base):
    """
    Tracks token usage for each AI call.

    Stores input/output tokens, model used, feature, and calculated cost.
    """
    __tablename__ = "token_usage"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    feature = Column(String(50), nullable=False)  # daily_brief, weekly_review, etc.
    model = Column(String(100), nullable=False)   # Model identifier
    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    total_tokens = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Float, nullable=False, default=0.0)  # Calculated cost in USD

    __table_args__ = (
        Index('idx_token_timestamp', 'timestamp'),
        Index('idx_token_feature', 'feature'),
    )


@dataclass
class UsageRecord:
    """Single token usage record."""
    feature: AIFeature
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: datetime


@dataclass
class FeatureCostSummary:
    """Cost summary for a single feature."""
    feature: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_call: float
    avg_cost_per_call: float


@dataclass
class CostReport:
    """Complete cost report."""
    period_start: str
    period_end: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    by_feature: List[FeatureCostSummary]
    by_day: Dict[str, float]
    model_used: str


class TokenTracker:
    """
    Tracks and reports AI token usage.

    Integrates with the AI module to automatically log usage.
    """

    def __init__(self, db: Session):
        self.db = db

    def get_model_pricing(self, model: str) -> Dict[str, float]:
        """Get pricing for a model."""
        model_lower = model.lower()

        # Try exact match first
        for key, pricing in MODEL_PRICING.items():
            if key in model_lower:
                return pricing

        return MODEL_PRICING["default"]

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost in USD for token usage."""
        pricing = self.get_model_pricing(model)

        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]

        return round(input_cost + output_cost, 6)

    def log_usage(
        self,
        feature: AIFeature,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> TokenUsage:
        """
        Log token usage for an AI call.

        Args:
            feature: Which feature made the call
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens

        Returns:
            TokenUsage record
        """
        total_tokens = input_tokens + output_tokens
        cost = self.calculate_cost(model, input_tokens, output_tokens)

        usage = TokenUsage(
            feature=feature.value,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost
        )

        self.db.add(usage)
        self.db.commit()
        self.db.refresh(usage)

        return usage

    def get_usage_by_feature(
        self,
        days: int = 30
    ) -> List[FeatureCostSummary]:
        """Get usage summary grouped by feature."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        usages = self.db.query(TokenUsage).filter(
            TokenUsage.timestamp >= cutoff
        ).all()

        # Group by feature
        by_feature: Dict[str, List[TokenUsage]] = defaultdict(list)
        for u in usages:
            by_feature[u.feature].append(u)

        summaries = []
        for feature, records in by_feature.items():
            total_calls = len(records)
            total_tokens = sum(r.total_tokens for r in records)
            total_cost = sum(r.cost_usd for r in records)

            summaries.append(FeatureCostSummary(
                feature=feature,
                total_calls=total_calls,
                total_tokens=total_tokens,
                total_cost_usd=round(total_cost, 4),
                avg_tokens_per_call=round(total_tokens / total_calls, 1) if total_calls > 0 else 0,
                avg_cost_per_call=round(total_cost / total_calls, 6) if total_calls > 0 else 0
            ))

        # Sort by cost descending
        summaries.sort(key=lambda x: x.total_cost_usd, reverse=True)

        return summaries

    def get_usage_by_day(
        self,
        days: int = 30
    ) -> Dict[str, float]:
        """Get daily cost totals."""
        cutoff = datetime.utcnow() - timedelta(days=days)

        usages = self.db.query(TokenUsage).filter(
            TokenUsage.timestamp >= cutoff
        ).all()

        by_day: Dict[str, float] = defaultdict(float)
        for u in usages:
            day = u.timestamp.strftime("%Y-%m-%d")
            by_day[day] += u.cost_usd

        # Round values
        return {k: round(v, 4) for k, v in sorted(by_day.items())}

    def get_cost_report(
        self,
        days: int = 30
    ) -> CostReport:
        """Generate complete cost report."""
        cutoff = datetime.utcnow() - timedelta(days=days)
        end_date = datetime.utcnow()

        usages = self.db.query(TokenUsage).filter(
            TokenUsage.timestamp >= cutoff
        ).all()

        total_calls = len(usages)
        total_tokens = sum(u.total_tokens for u in usages)
        total_cost = sum(u.cost_usd for u in usages)

        # Most common model
        model_counts: Dict[str, int] = defaultdict(int)
        for u in usages:
            model_counts[u.model] += 1

        most_used_model = max(model_counts, key=model_counts.get) if model_counts else "none"

        return CostReport(
            period_start=cutoff.strftime("%Y-%m-%d"),
            period_end=end_date.strftime("%Y-%m-%d"),
            total_calls=total_calls,
            total_tokens=total_tokens,
            total_cost_usd=round(total_cost, 4),
            by_feature=self.get_usage_by_feature(days),
            by_day=self.get_usage_by_day(days),
            model_used=most_used_model
        )

    def get_recent_usage(
        self,
        limit: int = 50
    ) -> List[UsageRecord]:
        """Get recent usage records."""
        usages = self.db.query(TokenUsage).order_by(
            TokenUsage.timestamp.desc()
        ).limit(limit).all()

        return [
            UsageRecord(
                feature=AIFeature(u.feature) if u.feature in [f.value for f in AIFeature] else AIFeature.OTHER,
                model=u.model,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                total_tokens=u.total_tokens,
                cost_usd=u.cost_usd,
                timestamp=u.timestamp
            )
            for u in usages
        ]


def get_token_tracker(db: Session) -> TokenTracker:
    """Get a token tracker instance."""
    return TokenTracker(db)
