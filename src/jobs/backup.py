#!/usr/bin/env python3
"""
LifeOS Database Backup/Restore

Automated backup and restore functionality for SQLite database.

Run daily backup via cron:
    crontab: 0 2 * * * cd /path/to/lifeOS && python -m src.jobs.backup

Manual commands:
    python -m src.jobs.backup                    # Create backup
    python -m src.jobs.backup --list             # List backups
    python -m src.jobs.backup --restore latest   # Restore latest backup
    python -m src.jobs.backup --restore 2026-02-03_020000  # Restore specific
    python -m src.jobs.backup --prune 7          # Keep only last 7 days
"""

import sys
import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config import settings


def get_backup_dir() -> Path:
    """Get the backup directory path."""
    backup_dir = settings.base_dir / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


def get_backup_filename(timestamp: Optional[datetime] = None) -> str:
    """Generate a backup filename with timestamp."""
    ts = timestamp or datetime.now()
    return f"lifeos_{ts.strftime('%Y-%m-%d_%H%M%S')}.db"


def create_backup(verify: bool = True) -> Tuple[bool, str]:
    """
    Create a backup of the SQLite database.

    Uses SQLite's backup API for a consistent, safe copy even if
    the database is in use.

    Args:
        verify: Whether to verify the backup integrity

    Returns:
        Tuple of (success, message)
    """
    db_path = settings.db_path

    if not db_path.exists():
        return False, f"Database not found: {db_path}"

    backup_dir = get_backup_dir()
    backup_filename = get_backup_filename()
    backup_path = backup_dir / backup_filename

    try:
        # Use SQLite backup API for safe copying
        source = sqlite3.connect(str(db_path))
        dest = sqlite3.connect(str(backup_path))

        with dest:
            source.backup(dest)

        source.close()
        dest.close()

        # Verify backup if requested
        if verify:
            is_valid, verify_msg = verify_backup(backup_path)
            if not is_valid:
                backup_path.unlink()  # Remove invalid backup
                return False, f"Backup verification failed: {verify_msg}"

        # Get file size
        size_mb = backup_path.stat().st_size / (1024 * 1024)

        return True, f"Backup created: {backup_filename} ({size_mb:.2f} MB)"

    except Exception as e:
        # Clean up partial backup
        if backup_path.exists():
            backup_path.unlink()
        return False, f"Backup failed: {e}"


def verify_backup(backup_path: Path) -> Tuple[bool, str]:
    """
    Verify backup integrity using SQLite's integrity check.

    Args:
        backup_path: Path to the backup file

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        conn = sqlite3.connect(str(backup_path))
        cursor = conn.cursor()

        # Run SQLite integrity check
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]

        # Count tables
        cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
        table_count = cursor.fetchone()[0]

        conn.close()

        if result == "ok":
            return True, f"Integrity OK, {table_count} tables"
        else:
            return False, f"Integrity check failed: {result}"

    except Exception as e:
        return False, f"Verification error: {e}"


def list_backups() -> List[dict]:
    """
    List all available backups.

    Returns:
        List of backup info dicts sorted by date (newest first)
    """
    backup_dir = get_backup_dir()
    backups = []

    for backup_file in backup_dir.glob("lifeos_*.db"):
        try:
            # Parse timestamp from filename
            name = backup_file.stem  # lifeos_2026-02-03_020000
            ts_str = name.replace("lifeos_", "")
            ts = datetime.strptime(ts_str, "%Y-%m-%d_%H%M%S")

            size_mb = backup_file.stat().st_size / (1024 * 1024)

            backups.append({
                "filename": backup_file.name,
                "path": backup_file,
                "timestamp": ts,
                "size_mb": size_mb,
                "id": ts_str
            })
        except (ValueError, OSError):
            # Skip files that don't match expected format
            continue

    # Sort by timestamp, newest first
    backups.sort(key=lambda x: x["timestamp"], reverse=True)
    return backups


def restore_backup(backup_id: str, force: bool = False) -> Tuple[bool, str]:
    """
    Restore database from a backup.

    Args:
        backup_id: Either 'latest' or a backup timestamp ID (e.g., '2026-02-03_020000')
        force: Skip confirmation (for automation)

    Returns:
        Tuple of (success, message)
    """
    backups = list_backups()

    if not backups:
        return False, "No backups found"

    # Find the requested backup
    if backup_id == "latest":
        backup = backups[0]
    else:
        backup = next((b for b in backups if b["id"] == backup_id), None)
        if not backup:
            return False, f"Backup not found: {backup_id}"

    backup_path = backup["path"]
    db_path = settings.db_path

    # Verify backup before restore
    is_valid, verify_msg = verify_backup(backup_path)
    if not is_valid:
        return False, f"Backup verification failed: {verify_msg}"

    try:
        # Create a backup of current database before overwriting
        if db_path.exists():
            pre_restore_backup = db_path.with_suffix(".db.pre_restore")
            shutil.copy2(db_path, pre_restore_backup)

        # Use SQLite backup API for safe restore
        source = sqlite3.connect(str(backup_path))
        dest = sqlite3.connect(str(db_path))

        with dest:
            source.backup(dest)

        source.close()
        dest.close()

        return True, f"Restored from {backup['filename']} (created {backup['timestamp']})"

    except Exception as e:
        return False, f"Restore failed: {e}"


def prune_backups(keep_days: int = 7, keep_minimum: int = 3) -> Tuple[int, List[str]]:
    """
    Remove old backups, keeping recent ones.

    Args:
        keep_days: Keep backups from the last N days
        keep_minimum: Always keep at least this many backups

    Returns:
        Tuple of (count deleted, list of deleted filenames)
    """
    backups = list_backups()

    if len(backups) <= keep_minimum:
        return 0, []

    cutoff = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    cutoff = cutoff - timedelta(days=keep_days)

    deleted = []

    # Keep the most recent keep_minimum backups regardless of age
    for backup in backups[keep_minimum:]:
        if backup["timestamp"] < cutoff:
            try:
                backup["path"].unlink()
                deleted.append(backup["filename"])
            except OSError:
                pass

    return len(deleted), deleted


def print_backup_list(backups: List[dict]) -> None:
    """Pretty print backup list."""
    if not backups:
        print("  No backups found.")
        return

    print(f"  {'Backup ID':<20} {'Date':<20} {'Size':<10}")
    print(f"  {'-'*20} {'-'*20} {'-'*10}")

    for backup in backups:
        date_str = backup["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        size_str = f"{backup['size_mb']:.2f} MB"
        print(f"  {backup['id']:<20} {date_str:<20} {size_str:<10}")


def main():
    parser = argparse.ArgumentParser(
        description="LifeOS database backup and restore",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.jobs.backup                      # Create backup
  python -m src.jobs.backup --list               # List all backups
  python -m src.jobs.backup --restore latest     # Restore latest backup
  python -m src.jobs.backup --restore 2026-02-03_020000  # Restore specific
  python -m src.jobs.backup --prune 7            # Keep only last 7 days
"""
    )

    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--list",
        action="store_true",
        help="List available backups"
    )
    group.add_argument(
        "--restore",
        metavar="ID",
        help="Restore from backup (use 'latest' or backup ID)"
    )
    group.add_argument(
        "--prune",
        type=int,
        metavar="DAYS",
        help="Remove backups older than N days (keeps minimum 3)"
    )
    group.add_argument(
        "--verify",
        metavar="ID",
        help="Verify a specific backup"
    )

    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip verification when creating backup"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompts"
    )

    args = parser.parse_args()

    print(f"[{datetime.now().isoformat()}] LifeOS Backup")

    if args.list:
        # List backups
        print("  Available backups:")
        backups = list_backups()
        print_backup_list(backups)

    elif args.restore:
        # Restore from backup
        if not args.force:
            confirm = input(f"  Restore from '{args.restore}'? This will overwrite the current database. [y/N] ")
            if confirm.lower() != 'y':
                print("  Cancelled.")
                sys.exit(0)

        success, msg = restore_backup(args.restore, force=args.force)
        print(f"  {msg}")
        sys.exit(0 if success else 1)

    elif args.prune:
        # Prune old backups
        count, deleted = prune_backups(keep_days=args.prune)
        if count > 0:
            print(f"  Deleted {count} old backup(s):")
            for name in deleted:
                print(f"    - {name}")
        else:
            print("  No backups to prune.")

    elif args.verify:
        # Verify a specific backup
        backups = list_backups()
        backup = next((b for b in backups if b["id"] == args.verify), None)

        if not backup:
            print(f"  Backup not found: {args.verify}")
            sys.exit(1)

        is_valid, msg = verify_backup(backup["path"])
        print(f"  {backup['filename']}: {msg}")
        sys.exit(0 if is_valid else 1)

    else:
        # Create backup (default action)
        success, msg = create_backup(verify=not args.no_verify)
        print(f"  {msg}")
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
