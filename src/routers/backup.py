"""
Database backup and restore endpoints.
"""

import re

from fastapi import APIRouter

from ..config import settings
from ..schemas import (
    BackupInfo,
    BackupListResponse,
    BackupResponse,
    RestoreRequest,
)

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.get("/list", response_model=BackupListResponse)
async def list_backups():
    """
    List all available database backups.

    Returns list of backups sorted by date (newest first).
    """
    from ..jobs.backup import list_backups as get_backups, get_backup_dir

    backups = get_backups()

    return BackupListResponse(
        backups=[
            BackupInfo(
                id=b["id"],
                filename=b["filename"],
                timestamp=b["timestamp"].isoformat(),
                size_mb=b["size_mb"]
            )
            for b in backups
        ],
        backup_dir=str(get_backup_dir())
    )


@router.post("/create", response_model=BackupResponse)
async def create_backup():
    """
    Create a new database backup.

    Uses SQLite's backup API for safe, consistent copies.
    Backup is automatically verified for integrity.
    """
    from ..jobs.backup import create_backup as do_backup

    success, message = do_backup(verify=True)

    # Extract backup ID from message if successful
    backup_id = None
    if success and "lifeos_" in message:
        # Message format: "Backup created: lifeos_2026-02-03_020000.db (1.23 MB)"
        match = re.search(r'lifeos_(\d{4}-\d{2}-\d{2}_\d{6})\.db', message)
        if match:
            backup_id = match.group(1)

    return BackupResponse(
        success=success,
        message=message,
        backup_id=backup_id
    )


@router.post("/restore", response_model=BackupResponse)
async def restore_backup(request: RestoreRequest):
    """
    Restore database from a backup.

    WARNING: This will overwrite the current database.
    A pre-restore backup is automatically created.

    Args:
        backup_id: Either 'latest' or a backup timestamp ID (e.g., '2026-02-03_020000')
    """
    from ..jobs.backup import restore_backup as do_restore

    success, message = do_restore(request.backup_id, force=True)

    return BackupResponse(
        success=success,
        message=message
    )


@router.get("/status")
async def backup_status():
    """
    Get backup system status.

    Returns info about backup directory, latest backup, and database.
    """
    from ..jobs.backup import list_backups as get_backups, get_backup_dir

    backups = get_backups()
    backup_dir = get_backup_dir()

    db_path = settings.db_path
    db_exists = db_path.exists()
    db_size_mb = db_path.stat().st_size / (1024 * 1024) if db_exists else 0

    latest = backups[0] if backups else None

    return {
        "database": {
            "path": str(db_path),
            "exists": db_exists,
            "size_mb": round(db_size_mb, 2)
        },
        "backups": {
            "directory": str(backup_dir),
            "count": len(backups),
            "latest": {
                "id": latest["id"],
                "timestamp": latest["timestamp"].isoformat(),
                "size_mb": round(latest["size_mb"], 2)
            } if latest else None
        }
    }
