#!/usr/bin/env python3
"""
Weekly Review Job

Generates a summary of the week's data and patterns.
Sends via Telegram/Discord using the notification service.

Run Sunday at 6 PM:
    crontab: 0 18 * * 0 cd /path/to/lifeOS && python -m src.jobs.weekly_review --notify

Or manually:
    python -m src.jobs.weekly_review           # Generate only
    python -m src.jobs.weekly_review --notify  # Generate and send
"""

import sys
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple, List

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.insights_service import InsightsService
from src.models import DataPoint, Insight, Pattern


def get_week_averages(db, week_ending: str) -> Tuple[Optional[float], Optional[int]]:
    """
    Calculate average sleep hours and readiness score for the week.

    Args:
        db: Database session
        week_ending: End date of the week (YYYY-MM-DD)

    Returns:
        Tuple of (avg_sleep_hours, avg_readiness_score)
    """
    end_date = datetime.strptime(week_ending, "%Y-%m-%d")
    start_date = end_date - timedelta(days=6)

    # Get sleep data for the week
    sleep_data = db.query(DataPoint).filter(
        DataPoint.type == "sleep",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    # Get readiness data for the week
    readiness_data = db.query(DataPoint).filter(
        DataPoint.type == "readiness",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    # Calculate averages
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

    return avg_sleep, avg_readiness


def get_active_patterns(db) -> List[dict]:
    """
    Get active patterns for display in the notification.

    Returns:
        List of pattern dicts with name and description
    """
    patterns = db.query(Pattern).filter(
        Pattern.active == True
    ).order_by(Pattern.confidence.desc()).limit(5).all()

    return [
        {
            "name": p.name,
            "description": p.description,
            "strength": p.strength,
            "confidence": p.confidence
        }
        for p in patterns
    ]


def run_weekly_review(force: bool = False) -> Tuple[Optional[Insight], List[Pattern]]:
    """
    Generate weekly review and detect patterns.

    Args:
        force: If True, regenerate even if one exists

    Returns:
        Tuple of (Insight, list of Pattern objects) or (None, []) if failed.
    """
    print(f"[{datetime.now().isoformat()}] Running weekly review job...")

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        service = InsightsService(db)
        today = datetime.now().strftime("%Y-%m-%d")

        # Step 1: Detect patterns from last 30 days
        print("  Detecting patterns...")
        patterns = service.detect_patterns(days=30, force=True)
        print(f"  Found {len(patterns)} patterns")

        for p in patterns:
            print(f"    - {p.name} (confidence: {p.confidence:.0%})")

        # Step 2: Generate weekly review
        print(f"\n  Generating weekly review ending {today}...")

        if force:
            insight = service.force_regenerate("weekly_review", today)
        else:
            insight = service.generate_weekly_review(today)

        if insight:
            print(f"  Review generated successfully!")
            print(f"  Confidence: {insight.confidence:.0%}")
            print(f"\n--- Weekly Review ---\n")
            print(insight.content)
            print(f"\n---------------------\n")

            # Print actionable patterns
            if patterns:
                print("--- Detected Patterns ---\n")
                for p in patterns:
                    if p.actionable:
                        print(f"* {p.name}")
                        print(f"  {p.description}")
                        print(f"  (Strength: {p.strength:.2f}, Confidence: {p.confidence:.0%})")
                        print()
                print("-------------------------\n")

            return insight, patterns
        else:
            print("  Failed to generate review - not enough data?")
            return None, []

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def send_notification(insight: Insight, patterns: List[Pattern]) -> bool:
    """
    Send weekly review via Telegram/Discord.

    Args:
        insight: The Insight object containing the review
        patterns: List of detected patterns

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

    # Get week averages for display
    init_db()
    db = SessionLocal()
    try:
        avg_sleep, avg_readiness = get_week_averages(db, insight.date)
        pattern_dicts = [
            {"name": p.name, "description": p.description}
            for p in patterns if p.actionable
        ]
    finally:
        db.close()

    # Send to all configured channels
    results = notifier.send_weekly_review_sync(
        content=insight.content,
        week_ending=insight.date,
        avg_sleep_hours=avg_sleep,
        avg_readiness=avg_readiness,
        patterns=pattern_dicts,
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
    parser = argparse.ArgumentParser(description="Generate and send weekly review")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Send notification after generating"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force regenerate even if review exists"
    )
    parser.add_argument(
        "--notify-only",
        action="store_true",
        help="Only send notification for existing review (don't regenerate)"
    )

    args = parser.parse_args()

    if args.notify_only:
        # Get existing review and send
        init_db()
        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            insight = db.query(Insight).filter(
                Insight.date == today,
                Insight.type == "weekly_review"
            ).first()

            if insight:
                patterns = db.query(Pattern).filter(Pattern.active == True).all()
                success = send_notification(insight, patterns)
                sys.exit(0 if success else 1)
            else:
                print(f"No weekly review found for {today}. Run without --notify-only first.")
                sys.exit(1)
        finally:
            db.close()
    else:
        # Generate review
        insight, patterns = run_weekly_review(force=args.force)

        if insight and args.notify:
            success = send_notification(insight, patterns)
            sys.exit(0 if success else 1)
        elif not insight:
            sys.exit(1)


if __name__ == "__main__":
    main()
