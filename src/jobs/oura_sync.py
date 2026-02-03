#!/usr/bin/env python3
"""
Oura Sync Job

Syncs sleep, activity, and readiness data from Oura API.

Run every few hours to keep data fresh:
    crontab: 0 */4 * * * cd /path/to/lifeOS && python -m src.jobs.oura_sync

Or manually:
    python -m src.jobs.oura_sync
    python -m src.jobs.oura_sync --backfill 30  # Backfill 30 days
"""

import sys
import argparse
from datetime import datetime, date, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.integrations.oura import OuraSyncService, sync_oura_data
from src.config import settings


def run_oura_sync(days: int = 1) -> bool:
    """
    Sync recent Oura data.

    Args:
        days: Number of days to sync (default 1 = today only)

    Returns:
        True if all syncs successful, False otherwise
    """
    print(f"[{datetime.now().isoformat()}] Running Oura sync job...")

    # Check token
    if not settings.oura_token:
        print("  ERROR: OURA_TOKEN not configured!")
        print("  Set OURA_TOKEN in your .env file.")
        print("  Get token at: https://cloud.ouraring.com/personal-access-tokens")
        return False

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        results = sync_oura_data(db, days=days)

        all_success = True
        total_synced = 0

        for result in results:
            if result.success:
                print(f"  {result}")
                total_synced += result.records_synced
            else:
                print(f"  FAILED: {result}")
                all_success = False

        print(f"\n  Total records synced: {total_synced}")

        return all_success

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def run_backfill(days: int = 30) -> bool:
    """
    Backfill historical Oura data.

    Args:
        days: Number of days to backfill

    Returns:
        True if all syncs successful, False otherwise
    """
    print(f"[{datetime.now().isoformat()}] Running Oura backfill ({days} days)...")

    # Check token
    if not settings.oura_token:
        print("  ERROR: OURA_TOKEN not configured!")
        return False

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        service = OuraSyncService(db)
        results = service.backfill(days=days)

        all_success = True
        total_synced = 0

        for result in results:
            if result.success:
                print(f"  {result}")
                total_synced += result.records_synced
            else:
                print(f"  FAILED: {result}")
                all_success = False

        print(f"\n  Total records synced: {total_synced}")

        return all_success

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def main():
    parser = argparse.ArgumentParser(description="Sync Oura data to LifeOS")
    parser.add_argument(
        "--backfill",
        type=int,
        metavar="DAYS",
        help="Backfill historical data for N days"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=1,
        help="Number of recent days to sync (default: 1)"
    )

    args = parser.parse_args()

    if args.backfill:
        success = run_backfill(days=args.backfill)
    else:
        success = run_oura_sync(days=args.days)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
