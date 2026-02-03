"""
Notification and delivery endpoints (Telegram, Discord).
"""

from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataPoint
from ..insights_service import InsightsService
from ..schemas import (
    NotifyStatusResponse,
    BriefDeliveryRequest,
    BriefDeliveryResponse,
    NotifyResultResponse,
    WeeklyReviewDeliveryRequest,
    WeeklyReviewDeliveryResponse,
    PatternSummary,
)

router = APIRouter(prefix="/api", tags=["notifications"])


@router.get("/notify/status", response_model=NotifyStatusResponse)
async def notify_status():
    """
    Check notification configuration status.

    Returns which channels (Telegram, Discord) are configured.
    """
    from ..integrations.notify import get_notification_service

    notifier = get_notification_service()

    return NotifyStatusResponse(
        telegram_enabled=notifier.telegram_enabled,
        discord_enabled=notifier.discord_enabled,
        enabled_channels=[c.value for c in notifier.enabled_channels]
    )


@router.post("/brief/deliver", response_model=BriefDeliveryResponse)
async def deliver_brief(
    request: BriefDeliveryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and deliver today's brief via Telegram/Discord.

    This is the main endpoint for morning brief delivery.
    Can be called by cron or manually triggered.

    Args:
        date: Date for brief (defaults to today)
        channels: Specific channels to use (defaults to all enabled)
        regenerate: Force regenerate even if brief exists
    """
    from ..integrations.notify import get_notification_service, NotifyChannel

    # Get or generate brief
    date = request.date or datetime.now().strftime("%Y-%m-%d")
    service = InsightsService(db)

    if request.regenerate:
        insight = service.force_regenerate("daily_brief", date)
    else:
        insight = service.generate_daily_brief(date)

    if not insight:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate brief - insufficient data"
        )

    # Get sleep and readiness for display
    sleep_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "sleep"
    ).first()
    readiness_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "readiness"
    ).first()

    sleep_hours = sleep_dp.value if sleep_dp else None
    readiness_score = int(readiness_dp.value) if readiness_dp else None

    # Get notification service
    notifier = get_notification_service()

    if not notifier.enabled_channels:
        raise HTTPException(
            status_code=400,
            detail="No notification channels configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL"
        )

    # Parse requested channels
    channels = None
    if request.channels:
        channels = []
        for ch in request.channels:
            try:
                channels.append(NotifyChannel(ch.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid channel: {ch}. Valid: telegram, discord"
                )

    # Send notifications
    results = notifier.send_brief_sync(
        content=insight.content,
        date=insight.date,
        sleep_hours=sleep_hours,
        readiness_score=readiness_score,
        confidence=insight.confidence,
        channels=channels
    )

    # Build response
    notify_responses = [
        NotifyResultResponse(
            success=r.success,
            channel=r.channel.value,
            message_id=r.message_id,
            error=r.error
        )
        for r in results
    ]

    return BriefDeliveryResponse(
        brief_date=insight.date,
        brief_content=insight.content,
        notifications=notify_responses,
        all_successful=all(r.success for r in results)
    )


@router.post("/weekly-review/deliver", response_model=WeeklyReviewDeliveryResponse)
async def deliver_weekly_review(
    request: WeeklyReviewDeliveryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and deliver weekly review via Telegram/Discord.

    This is the main endpoint for Sunday evening delivery.
    Can be called by cron or manually triggered.

    Args:
        week_ending: End date of the week (defaults to today)
        channels: Specific channels to use (defaults to all enabled)
        regenerate: Force regenerate even if review exists
    """
    from ..integrations.notify import get_notification_service, NotifyChannel

    # Get or generate weekly review
    week_ending = request.week_ending or datetime.now().strftime("%Y-%m-%d")
    service = InsightsService(db)

    # Run pattern detection first
    patterns = service.detect_patterns(days=30, force=request.regenerate)

    if request.regenerate:
        insight = service.force_regenerate("weekly_review", week_ending)
    else:
        insight = service.generate_weekly_review(week_ending)

    if not insight:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate weekly review - insufficient data"
        )

    # Calculate week averages
    end_date = datetime.strptime(week_ending, "%Y-%m-%d")
    start_date = end_date - timedelta(days=6)

    sleep_data = db.query(DataPoint).filter(
        DataPoint.type == "sleep",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    readiness_data = db.query(DataPoint).filter(
        DataPoint.type == "readiness",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    avg_sleep = None
    if sleep_data:
        sleep_values = [dp.value for dp in sleep_data if dp.value is not None]
        if sleep_values:
            avg_sleep = sum(sleep_values) / len(sleep_values)

    avg_readiness = None
    if readiness_data:
        readiness_values = [dp.value for dp in readiness_data if dp.value is not None]
        if readiness_values:
            avg_readiness = int(sum(readiness_values) / len(readiness_values))

    # Get notification service
    notifier = get_notification_service()

    if not notifier.enabled_channels:
        raise HTTPException(
            status_code=400,
            detail="No notification channels configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL"
        )

    # Parse requested channels
    channels = None
    if request.channels:
        channels = []
        for ch in request.channels:
            try:
                channels.append(NotifyChannel(ch.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid channel: {ch}. Valid: telegram, discord"
                )

    # Build pattern dicts for notification
    pattern_dicts = [
        {"name": p.name, "description": p.description}
        for p in patterns if p.actionable
    ]

    # Send notifications
    results = notifier.send_weekly_review_sync(
        content=insight.content,
        week_ending=insight.date,
        avg_sleep_hours=avg_sleep,
        avg_readiness=avg_readiness,
        patterns=pattern_dicts,
        confidence=insight.confidence,
        channels=channels
    )

    # Build response
    notify_responses = [
        NotifyResultResponse(
            success=r.success,
            channel=r.channel.value,
            message_id=r.message_id,
            error=r.error
        )
        for r in results
    ]

    pattern_summaries = [
        PatternSummary(name=p.name, description=p.description)
        for p in patterns if p.actionable
    ]

    return WeeklyReviewDeliveryResponse(
        week_ending=insight.date,
        review_content=insight.content,
        patterns=pattern_summaries,
        avg_sleep_hours=avg_sleep,
        avg_readiness=avg_readiness,
        notifications=notify_responses,
        all_successful=all(r.success for r in results)
    )
