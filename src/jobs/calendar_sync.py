#!/usr/bin/env python3
"""
Calendar Sync Job

Syncs events from Google Calendar to the database.

Run regularly to keep calendar data fresh:
    crontab: 0 */2 * * * cd /path/to/lifeOS && python -m src.jobs.calendar_sync

Or manually:
    python -m src.jobs.calendar_sync
    python -m src.jobs.calendar_sync --days-back 30 --days-forward 30
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.integrations.calendar import (
    CalendarSyncService,
    CalendarSyncStatus,
    get_oauth_token,
    is_token_expired,
)
from src.config import settings


def run_calendar_sync(
    days_back: int = 7,
    days_forward: int = 14,
    calendar_id: str = "primary"
) -> bool:
    """
    Sync Google Calendar events.

    Args:
        days_back: Number of days in the past to sync
        days_forward: Number of days in the future to sync
        calendar_id: Calendar ID to sync

    Returns:
        True if sync successful, False otherwise
    """
    print(f"[{datetime.now().isoformat()}] Running Calendar sync job...")

    # Check configuration
    if not settings.google_client_id or not settings.google_client_secret:
        print("  ERROR: Google Calendar not configured!")
        print("  Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET in your .env file.")
        print("  Get credentials at: https://console.cloud.google.com/apis/credentials")
        return False

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        # Check for valid token
        token = get_oauth_token(db)
        if not token:
            print("  ERROR: Google Calendar not connected!")
            print("  Visit /api/calendar/auth to authorize calendar access.")
            return False

        if is_token_expired(token):
            print("  Token expired, will attempt refresh...")

        # Run sync
        service = CalendarSyncService(db)
        result = service.sync(
            days_back=days_back,
            days_forward=days_forward,
            calendar_id=calendar_id
        )

        if result.status == CalendarSyncStatus.SUCCESS:
            print(f"  {result}")
            print(f"    - Events synced: {result.events_synced}")
            print(f"    - Events updated: {result.events_updated}")
            return True
        elif result.status == CalendarSyncStatus.PARTIAL:
            print(f"  Partial sync: {result}")
            for error in result.errors:
                print(f"    - {error}")
            return True
        else:
            print(f"  FAILED: {result}")
            return False

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Sync Google Calendar to LifeOS")
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="Number of days in the past to sync (default: 7)"
    )
    parser.add_argument(
        "--days-forward",
        type=int,
        default=14,
        help="Number of days in the future to sync (default: 14)"
    )
    parser.add_argument(
        "--calendar",
        type=str,
        default="primary",
        help="Calendar ID to sync (default: primary)"
    )

    args = parser.parse_args()

    success = run_calendar_sync(
        days_back=args.days_back,
        days_forward=args.days_forward,
        calendar_id=args.calendar
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
