#!/usr/bin/env python3
"""
Pattern Detection Job

Analyzes historical data to find actionable patterns.

Run daily at midnight:
    crontab: 0 0 * * * cd /path/to/lifeOS && python -m src.jobs.pattern_detection

Or manually:
    python -m src.jobs.pattern_detection [--days 30]
"""

import sys
import argparse
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.database import SessionLocal, init_db
from src.insights_service import InsightsService


def run_pattern_detection(days: int = 30):
    """
    Run pattern detection on historical data.

    Args:
        days: Number of days to analyze

    Returns:
        List of detected patterns
    """
    print(f"[{datetime.now().isoformat()}] Running pattern detection job...")
    print(f"  Analyzing last {days} days...")

    # Initialize database
    init_db()

    # Create session
    db = SessionLocal()

    try:
        service = InsightsService(db)

        # Run detection
        patterns = service.detect_patterns(days=days, force=True)

        print(f"\n  Found {len(patterns)} patterns:\n")

        for i, p in enumerate(patterns, 1):
            print(f"  {i}. {p.name}")
            print(f"     Type: {p.pattern_type}")
            print(f"     Variables: {', '.join(p.variables or [])}")
            print(f"     Strength: {p.strength:.2f}")
            print(f"     Confidence: {p.confidence:.0%}")
            print(f"     Sample size: {p.sample_size} days")
            print(f"     Actionable: {'Yes' if p.actionable else 'No'}")
            print(f"     Description: {p.description}")
            print()

        return patterns

    except Exception as e:
        print(f"  Error: {e}")
        raise

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run pattern detection")
    parser.add_argument("--days", type=int, default=30, help="Days to analyze")
    args = parser.parse_args()

    run_pattern_detection(days=args.days)
