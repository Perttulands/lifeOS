#!/usr/bin/env python3
"""
Daily Brief Job

Generates the morning brief from last night's sleep and today's calendar.

Run at 7 AM daily:
    crontab: 0 7 * * * cd /path/to/lifeOS && python -m src.jobs.daily_brief

Or manually:
    python -m src.jobs.daily_brief
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.insights_service import InsightsService
from src.config import settings


def run_daily_brief():
    """
    Generate today's daily brief.

    Returns the brief content or None if failed.
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
        insight = service.generate_daily_brief(today)

        if insight:
            print(f"  Brief generated successfully!")
            print(f"  Confidence: {insight.confidence:.0%}")
            print(f"\n--- Daily Brief ---\n")
            print(insight.content)
            print(f"\n-------------------\n")
            return insight.content
        else:
            print("  Failed to generate brief - no data?")
            return None

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def send_notification(content: str):
    """
    Send brief via notification channel.

    TODO: Integrate with Clawdbot for Telegram/Discord delivery.
    """
    # Placeholder for notification integration
    # Could use:
    # - Telegram bot API
    # - Discord webhook
    # - Email
    # - Push notification

    print("[Notification] Would send to configured channel:")
    print(f"  {content[:100]}...")


if __name__ == "__main__":
    brief = run_daily_brief()

    if brief and "--notify" in sys.argv:
        send_notification(brief)
