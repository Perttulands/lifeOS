"""
Token cost and usage statistics endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List

from ..database import get_db
from ..schemas import (
    CostReportResponse,
    FeatureCostSummary,
    TokenUsageResponse,
    StatsResponse,
)
from ..token_tracker import get_token_tracker, AIFeature

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsResponse)
async def get_stats(
    days: int = Query(30, ge=1, le=365, description="Days of history to include"),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive token usage statistics.

    Returns cost report with breakdown by feature and day,
    plus recent usage records.
    """
    tracker = get_token_tracker(db)

    cost_report = tracker.get_cost_report(days)
    recent_usage = tracker.get_recent_usage(limit=50)

    return StatsResponse(
        cost_report=CostReportResponse(
            period_start=cost_report.period_start,
            period_end=cost_report.period_end,
            total_calls=cost_report.total_calls,
            total_tokens=cost_report.total_tokens,
            total_cost_usd=cost_report.total_cost_usd,
            by_feature=[
                FeatureCostSummary(
                    feature=f.feature,
                    total_calls=f.total_calls,
                    total_tokens=f.total_tokens,
                    total_cost_usd=f.total_cost_usd,
                    avg_tokens_per_call=f.avg_tokens_per_call,
                    avg_cost_per_call=f.avg_cost_per_call
                )
                for f in cost_report.by_feature
            ],
            by_day=cost_report.by_day,
            model_used=cost_report.model_used
        ),
        recent_usage=[
            TokenUsageResponse(
                feature=u.feature.value,
                model=u.model,
                input_tokens=u.input_tokens,
                output_tokens=u.output_tokens,
                total_tokens=u.total_tokens,
                cost_usd=u.cost_usd,
                timestamp=u.timestamp.isoformat()
            )
            for u in recent_usage
        ]
    )


@router.get("/cost", response_model=CostReportResponse)
async def get_cost_report(
    days: int = Query(30, ge=1, le=365, description="Days of history"),
    db: Session = Depends(get_db)
):
    """
    Get token cost report.

    Returns total costs and breakdown by feature and day.
    """
    tracker = get_token_tracker(db)
    report = tracker.get_cost_report(days)

    return CostReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        total_calls=report.total_calls,
        total_tokens=report.total_tokens,
        total_cost_usd=report.total_cost_usd,
        by_feature=[
            FeatureCostSummary(
                feature=f.feature,
                total_calls=f.total_calls,
                total_tokens=f.total_tokens,
                total_cost_usd=f.total_cost_usd,
                avg_tokens_per_call=f.avg_tokens_per_call,
                avg_cost_per_call=f.avg_cost_per_call
            )
            for f in report.by_feature
        ],
        by_day=report.by_day,
        model_used=report.model_used
    )


@router.get("/usage", response_model=List[TokenUsageResponse])
async def get_recent_usage(
    limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    db: Session = Depends(get_db)
):
    """
    Get recent token usage records.

    Returns individual AI call records sorted by most recent.
    """
    tracker = get_token_tracker(db)
    usage = tracker.get_recent_usage(limit)

    return [
        TokenUsageResponse(
            feature=u.feature.value,
            model=u.model,
            input_tokens=u.input_tokens,
            output_tokens=u.output_tokens,
            total_tokens=u.total_tokens,
            cost_usd=u.cost_usd,
            timestamp=u.timestamp.isoformat()
        )
        for u in usage
    ]


@router.get("/by-feature", response_model=List[FeatureCostSummary])
async def get_cost_by_feature(
    days: int = Query(30, ge=1, le=365, description="Days of history"),
    db: Session = Depends(get_db)
):
    """
    Get cost breakdown by AI feature.

    Returns costs for each feature (daily_brief, weekly_review, etc.)
    sorted by total cost descending.
    """
    tracker = get_token_tracker(db)
    summaries = tracker.get_usage_by_feature(days)

    return [
        FeatureCostSummary(
            feature=s.feature,
            total_calls=s.total_calls,
            total_tokens=s.total_tokens,
            total_cost_usd=s.total_cost_usd,
            avg_tokens_per_call=s.avg_tokens_per_call,
            avg_cost_per_call=s.avg_cost_per_call
        )
        for s in summaries
    ]


@router.get("/summary")
async def get_quick_summary(
    db: Session = Depends(get_db)
):
    """
    Get quick cost summary for dashboard.

    Returns key metrics: total cost, calls today, most expensive feature.
    """
    tracker = get_token_tracker(db)

    # Get today's data
    today_report = tracker.get_cost_report(days=1)

    # Get 30-day report for comparison
    month_report = tracker.get_cost_report(days=30)

    # Most expensive feature
    top_feature = month_report.by_feature[0] if month_report.by_feature else None

    return {
        "today": {
            "calls": today_report.total_calls,
            "tokens": today_report.total_tokens,
            "cost_usd": today_report.total_cost_usd
        },
        "last_30_days": {
            "calls": month_report.total_calls,
            "tokens": month_report.total_tokens,
            "cost_usd": month_report.total_cost_usd,
            "avg_daily_cost": round(month_report.total_cost_usd / 30, 4) if month_report.total_cost_usd else 0
        },
        "top_feature": {
            "name": top_feature.feature if top_feature else None,
            "cost_usd": top_feature.total_cost_usd if top_feature else 0,
            "calls": top_feature.total_calls if top_feature else 0
        } if top_feature else None,
        "model": month_report.model_used
    }
