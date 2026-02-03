"""
Tests for Backup/Restore functionality.

Tests the backup job module and API endpoints.
"""

import pytest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock

from src.jobs.backup import (
    create_backup,
    verify_backup,
    list_backups,
    restore_backup,
    prune_backups,
    get_backup_dir,
    get_backup_filename,
)


class TestBackupFilenames:
    """Tests for backup filename generation."""

    def test_get_backup_filename_format(self):
        """Test backup filename follows expected format."""
        ts = datetime(2026, 2, 3, 14, 30, 0)
        filename = get_backup_filename(ts)

        assert filename == "lifeos_2026-02-03_143000.db"

    def test_get_backup_filename_current_time(self):
        """Test backup filename with current time."""
        filename = get_backup_filename()

        assert filename.startswith("lifeos_")
        assert filename.endswith(".db")
        # Should contain date pattern
        assert "_" in filename


class TestBackupCreation:
    """Tests for backup creation."""

    def test_create_backup_missing_database(self):
        """Test backup fails when database doesn't exist."""
        with patch('src.jobs.backup.settings') as mock_settings:
            mock_settings.db_path = Path("/nonexistent/path/lifeos.db")

            success, message = create_backup()

            assert success is False
            assert "not found" in message.lower()

    def test_create_backup_success(self, tmp_path, monkeypatch):
        """Test successful backup creation."""
        # Create a test database
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO test (data) VALUES ('test data')")
        conn.commit()
        conn.close()

        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Use monkeypatch for settings
        import src.jobs.backup as backup_module
        mock_settings = MagicMock()
        mock_settings.db_path = db_path
        mock_settings.base_dir = tmp_path
        monkeypatch.setattr(backup_module, 'settings', mock_settings)
        monkeypatch.setattr(backup_module, 'get_backup_dir', lambda: backup_dir)

        success, message = create_backup(verify=True)

        assert success is True
        assert "Backup created" in message
        assert backup_dir.exists()
        assert len(list(backup_dir.glob("lifeos_*.db"))) == 1


class TestBackupVerification:
    """Tests for backup verification."""

    def test_verify_valid_backup(self, tmp_path):
        """Test verification of valid backup."""
        # Create a valid SQLite database
        db_path = tmp_path / "valid.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY)")
        conn.commit()
        conn.close()

        is_valid, message = verify_backup(db_path)

        assert is_valid is True
        assert "Integrity OK" in message

    def test_verify_invalid_backup(self, tmp_path):
        """Test verification of corrupted backup."""
        # Create a corrupted file
        db_path = tmp_path / "corrupted.db"
        db_path.write_text("this is not a valid sqlite database")

        is_valid, message = verify_backup(db_path)

        assert is_valid is False

    def test_verify_missing_backup(self, tmp_path):
        """Test verification of missing file."""
        db_path = tmp_path / "missing.db"

        is_valid, message = verify_backup(db_path)

        assert is_valid is False
        assert "not found" in message.lower()


class TestBackupListing:
    """Tests for backup listing."""

    def test_list_backups_empty_dir(self, tmp_path):
        """Test listing with no backups."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            backups = list_backups()

        assert backups == []

    def test_list_backups_sorted_by_date(self, tmp_path):
        """Test backups are sorted newest first."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create backup files with different dates
        (backup_dir / "lifeos_2026-02-01_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2026-02-03_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2026-02-02_100000.db").write_bytes(b"x" * 100)

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            backups = list_backups()

        assert len(backups) == 3
        # Should be sorted newest first
        assert backups[0]["id"] == "2026-02-03_100000"
        assert backups[1]["id"] == "2026-02-02_100000"
        assert backups[2]["id"] == "2026-02-01_100000"

    def test_list_backups_ignores_non_matching_files(self, tmp_path):
        """Test that non-backup files are ignored."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create backup and non-backup files
        (backup_dir / "lifeos_2026-02-01_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "other_file.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_invalid.db").write_bytes(b"x" * 100)

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            backups = list_backups()

        assert len(backups) == 1
        assert backups[0]["id"] == "2026-02-01_100000"


class TestBackupRestore:
    """Tests for backup restoration."""

    def test_restore_no_backups(self, tmp_path):
        """Test restore fails when no backups exist."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            success, message = restore_backup("latest")

        assert success is False
        assert "No backups found" in message

    def test_restore_backup_not_found(self, tmp_path):
        """Test restore fails when specific backup doesn't exist."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()
        (backup_dir / "lifeos_2026-02-01_100000.db").write_bytes(b"x" * 100)

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            success, message = restore_backup("2099-01-01_000000")

        assert success is False
        assert "not found" in message.lower()

    def test_restore_latest_backup(self, tmp_path):
        """Test restoring the latest backup."""
        # Create source database
        db_path = tmp_path / "lifeos.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        conn.execute("INSERT INTO test (data) VALUES ('original')")
        conn.commit()
        conn.close()

        # Create backup directory with a valid backup
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        backup_path = backup_dir / "lifeos_2026-02-03_100000.db"
        backup_conn = sqlite3.connect(str(backup_path))
        backup_conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, data TEXT)")
        backup_conn.execute("INSERT INTO test (data) VALUES ('restored')")
        backup_conn.commit()
        backup_conn.close()

        with patch('src.jobs.backup.settings') as mock_settings:
            mock_settings.db_path = db_path
            with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
                success, message = restore_backup("latest", force=True)

        assert success is True
        assert "Restored" in message

        # Verify data was restored
        conn = sqlite3.connect(str(db_path))
        cursor = conn.execute("SELECT data FROM test")
        data = cursor.fetchone()[0]
        conn.close()

        assert data == "restored"


class TestBackupPruning:
    """Tests for backup pruning."""

    def test_prune_keeps_minimum(self, tmp_path):
        """Test pruning keeps minimum number of backups."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create 3 old backups
        (backup_dir / "lifeos_2020-01-01_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-02_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-03_100000.db").write_bytes(b"x" * 100)

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            count, deleted = prune_backups(keep_days=1, keep_minimum=3)

        # Should keep all 3 due to minimum
        assert count == 0
        assert len(deleted) == 0

    def test_prune_removes_old_backups(self, tmp_path):
        """Test pruning removes old backups beyond minimum."""
        backup_dir = tmp_path / "backups"
        backup_dir.mkdir()

        # Create old backups (beyond keep_minimum and older than keep_days)
        (backup_dir / "lifeos_2020-01-01_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-02_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-03_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-04_100000.db").write_bytes(b"x" * 100)
        (backup_dir / "lifeos_2020-01-05_100000.db").write_bytes(b"x" * 100)

        with patch('src.jobs.backup.get_backup_dir', return_value=backup_dir):
            count, deleted = prune_backups(keep_days=1, keep_minimum=2)

        # Should delete 3 old backups (keeping 2 minimum)
        assert count == 3
        assert len(deleted) == 3

        # Verify 2 remain
        remaining = list(backup_dir.glob("lifeos_*.db"))
        assert len(remaining) == 2


class TestBackupDirectory:
    """Tests for backup directory management."""

    def test_get_backup_dir_creates_if_missing(self, tmp_path):
        """Test backup directory is created if it doesn't exist."""
        with patch('src.jobs.backup.settings') as mock_settings:
            mock_settings.base_dir = tmp_path

            backup_dir = get_backup_dir()

        assert backup_dir.exists()
        assert backup_dir == tmp_path / "backups"

    def test_get_backup_dir_returns_existing(self, tmp_path):
        """Test existing backup directory is returned."""
        existing_dir = tmp_path / "backups"
        existing_dir.mkdir()
        (existing_dir / "marker.txt").write_text("exists")

        with patch('src.jobs.backup.settings') as mock_settings:
            mock_settings.base_dir = tmp_path

            backup_dir = get_backup_dir()

        assert backup_dir == existing_dir
        assert (backup_dir / "marker.txt").exists()
