#!/usr/bin/env python3
"""
Daily Brief Job

Generates the morning brief from last night's sleep and today's calendar.
Sends via Telegram/Discord using the notification service.

Run at 7 AM daily:
    crontab: 0 7 * * * cd /path/to/lifeOS && python -m src.jobs.daily_brief --notify

Or manually:
    python -m src.jobs.daily_brief           # Generate only
    python -m src.jobs.daily_brief --notify  # Generate and send
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.insights_service import InsightsService
from src.models import DataPoint, Insight
from src.config import settings


def get_sleep_and_readiness(db, date: str) -> Tuple[Optional[float], Optional[int]]:
    """
    Get sleep hours and readiness score for a date.

    Returns:
        Tuple of (sleep_hours, readiness_score)
    """
    # Get sleep data
    sleep_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "sleep"
    ).first()
    sleep_hours = sleep_dp.value if sleep_dp else None

    # Get readiness data
    readiness_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "readiness"
    ).first()
    readiness_score = int(readiness_dp.value) if readiness_dp else None

    return sleep_hours, readiness_score


def run_daily_brief(force: bool = False) -> Optional[Insight]:
    """
    Generate today's daily brief.

    Args:
        force: If True, regenerate even if one exists

    Returns:
        The Insight object or None if failed.
    """
    print(f"[{datetime.now().isoformat()}] Running daily brief job...")

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        service = InsightsService(db)
        today = datetime.now().strftime("%Y-%m-%d")

        # Generate brief
        print(f"  Generating brief for {today}...")

        if force:
            insight = service.force_regenerate("daily_brief", today)
        else:
            insight = service.generate_daily_brief(today)

        if insight:
            print(f"  Brief generated successfully!")
            print(f"  Confidence: {insight.confidence:.0%}")
            print(f"\n--- Daily Brief ---\n")
            print(insight.content)
            print(f"\n-------------------\n")
            return insight
        else:
            print("  Failed to generate brief - no data?")
            return None

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def send_notification(insight: Insight) -> bool:
    """
    Send brief via Telegram/Discord.

    Args:
        insight: The Insight object containing the brief

    Returns:
        True if at least one notification was sent successfully
    """
    from src.integrations.notify import get_notification_service

    print(f"[{datetime.now().isoformat()}] Sending notifications...")

    # Get notification service
    notifier = get_notification_service()

    if not notifier.enabled_channels:
        print("  No notification channels configured!")
        print("  Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL")
        return False

    print(f"  Enabled channels: {[c.value for c in notifier.enabled_channels]}")

    # Get sleep and readiness data for display
    init_db()
    db = SessionLocal()
    try:
        sleep_hours, readiness_score = get_sleep_and_readiness(db, insight.date)
    finally:
        db.close()

    # Send to all configured channels
    results = notifier.send_brief_sync(
        content=insight.content,
        date=insight.date,
        sleep_hours=sleep_hours,
        readiness_score=readiness_score,
        confidence=insight.confidence
    )

    # Report results
    success_count = 0
    for result in results:
        if result.success:
            print(f"  [{result.channel.value}] Sent successfully (msg_id: {result.message_id})")
            success_count += 1
        else:
            print(f"  [{result.channel.value}] Failed: {result.error}")

    return success_count > 0


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(description="Generate and send daily brief")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notification after generating"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate even if brief exists"
    )
    parser.add_argument(
        "--notify-only",
        action="store_true",
        help="Only send notification for existing brief (don't regenerate)"
    )

    args = parser.parse_args()

    if args.notify_only:
        # Get existing brief and send
        init_db()
        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            insight = db.query(Insight).filter(
                Insight.date == today,
                Insight.type == "daily_brief"
            ).first()

            if insight:
                success = send_notification(insight)
                sys.exit(0 if success else 1)
            else:
                print(f"No brief found for {today}. Run without --notify-only first.")
                sys.exit(1)
        finally:
            db.close()
    else:
        # Generate brief
        insight = run_daily_brief(force=args.force)

        if insight and args.notify:
            success = send_notification(insight)
            sys.exit(0 if success else 1)
        elif not insight:
            sys.exit(1)


if __name__ == "__main__":
    main()
