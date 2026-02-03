#!/usr/bin/env python3
"""
Weekly Review Job

Generates a summary of the week's data and patterns.

Run Sunday at 6 PM:
    crontab: 0 18 * * 0 cd /path/to/lifeOS && python -m src.jobs.weekly_review

Or manually:
    python -m src.jobs.weekly_review
"""

import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.insights_service import InsightsService


def run_weekly_review():
    """
    Generate weekly review and detect patterns.

    Returns the review content or None if failed.
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
        insight = service.generate_weekly_review(today)

        if insight:
            print(f"  Review generated successfully!")
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

            return insight.content
        else:
            print("  Failed to generate review - not enough data?")
            return None

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


def send_notification(content: str):
    """Send review via notification channel."""
    print("[Notification] Would send weekly review to configured channel")


if __name__ == "__main__":
    review = run_weekly_review()

    if review and "--notify" in sys.argv:
        send_notification(review)
