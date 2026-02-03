"""
LifeOS Voice Note Service

Handles voice note uploads, transcription via Whisper, and auto-categorization.
"""

import os
import uuid
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy.orm import Session

from ..models import VoiceNote
from ..config import settings
from .whisper import WhisperService, get_whisper_service, SUPPORTED_FORMATS, MAX_FILE_SIZE
from .capture import CaptureService, CaptureResult, CaptureType


# Directory for storing voice notes
VOICE_NOTES_DIR = Path(settings.base_dir) / "data" / "voice_notes"


@dataclass
class VoiceNoteResult:
    """Result from processing a voice note."""
    voice_note_id: int
    filename: str
    transcription: Optional[str]
    transcription_status: str
    categorized_type: Optional[str]
    categorized_id: Optional[int]
    success: bool
    message: str


class VoiceNoteService:
    """
    Service for processing voice notes.

    Handles:
    1. File upload and storage
    2. Transcription via Whisper API
    3. Auto-categorization of transcribed text
    """

    def __init__(self, db: Session):
        self.db = db
        self.whisper = get_whisper_service()
        self.capture = CaptureService(db)

        # Ensure storage directory exists
        VOICE_NOTES_DIR.mkdir(parents=True, exist_ok=True)

    def process_upload(
        self,
        file_content: bytes,
        filename: str,
        mime_type: Optional[str] = None,
        source: str = "upload",
        auto_transcribe: bool = True,
        auto_categorize: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> VoiceNoteResult:
        """
        Process an uploaded voice note file.

        Args:
            file_content: Raw bytes of the audio file
            filename: Original filename
            mime_type: MIME type of the file
            source: Source of upload (upload, telegram, discord)
            auto_transcribe: Whether to transcribe immediately
            auto_categorize: Whether to auto-categorize after transcription
            metadata: Additional metadata

        Returns:
            VoiceNoteResult with processing status
        """
        # Validate file size
        file_size = len(file_content)
        if file_size > MAX_FILE_SIZE:
            return VoiceNoteResult(
                voice_note_id=0,
                filename=filename,
                transcription=None,
                transcription_status="failed",
                categorized_type=None,
                categorized_id=None,
                success=False,
                message=f"File too large: {file_size / 1024 / 1024:.1f} MB (max 25 MB)"
            )

        if file_size == 0:
            return VoiceNoteResult(
                voice_note_id=0,
                filename=filename,
                transcription=None,
                transcription_status="failed",
                categorized_type=None,
                categorized_id=None,
                success=False,
                message="File is empty"
            )

        # Validate format
        ext = Path(filename).suffix.lower()
        valid_extensions = set(SUPPORTED_FORMATS.values())
        if ext not in valid_extensions:
            if mime_type not in SUPPORTED_FORMATS:
                return VoiceNoteResult(
                    voice_note_id=0,
                    filename=filename,
                    transcription=None,
                    transcription_status="failed",
                    categorized_type=None,
                    categorized_id=None,
                    success=False,
                    message=f"Unsupported format: {ext}. Supported: {', '.join(valid_extensions)}"
                )
            # Use extension from mime type
            ext = SUPPORTED_FORMATS[mime_type]

        # Generate unique filename for storage
        unique_id = str(uuid.uuid4())[:8]
        date_prefix = datetime.now().strftime("%Y%m%d")
        stored_filename = f"{date_prefix}_{unique_id}{ext}"
        file_path = VOICE_NOTES_DIR / stored_filename

        # Save file
        try:
            with open(file_path, "wb") as f:
                f.write(file_content)
        except Exception as e:
            return VoiceNoteResult(
                voice_note_id=0,
                filename=filename,
                transcription=None,
                transcription_status="failed",
                categorized_type=None,
                categorized_id=None,
                success=False,
                message=f"Failed to save file: {e}"
            )

        # Create database record
        voice_note = VoiceNote(
            filename=filename,
            file_path=str(file_path),
            file_size=file_size,
            mime_type=mime_type,
            source=source,
            transcription_status="pending",
            categorization_status="pending",
            extra_data=metadata or {}
        )
        self.db.add(voice_note)
        self.db.commit()
        self.db.refresh(voice_note)

        # Transcribe if requested and Whisper is configured
        if auto_transcribe:
            self._transcribe(voice_note)

            # Categorize if transcription succeeded
            if auto_categorize and voice_note.transcription_status == "completed":
                self._categorize(voice_note)

        return VoiceNoteResult(
            voice_note_id=voice_note.id,
            filename=filename,
            transcription=voice_note.transcription,
            transcription_status=voice_note.transcription_status,
            categorized_type=voice_note.categorized_type,
            categorized_id=voice_note.categorized_id,
            success=True,
            message=self._build_message(voice_note)
        )

    def _transcribe(self, voice_note: VoiceNote) -> None:
        """Transcribe a voice note using Whisper."""
        if not self.whisper:
            voice_note.transcription_status = "failed"
            voice_note.transcription_error = "Whisper not configured (missing OpenAI API key)"
            self.db.commit()
            return

        voice_note.transcription_status = "processing"
        self.db.commit()

        try:
            result = self.whisper.transcribe(voice_note.file_path)

            if result.success:
                voice_note.transcription = result.text
                voice_note.transcription_status = "completed"
                voice_note.transcription_language = result.language
                if result.duration:
                    voice_note.duration_seconds = result.duration
            else:
                voice_note.transcription_status = "failed"
                voice_note.transcription_error = result.error
        except Exception as e:
            voice_note.transcription_status = "failed"
            voice_note.transcription_error = str(e)

        self.db.commit()

    def _categorize(self, voice_note: VoiceNote) -> None:
        """Auto-categorize transcribed text using CaptureService."""
        if not voice_note.transcription:
            voice_note.categorization_status = "skipped"
            self.db.commit()
            return

        try:
            result = self.capture.process(
                text=voice_note.transcription,
                source="voice",
                metadata={
                    "voice_note_id": voice_note.id,
                    "original_filename": voice_note.filename
                }
            )

            voice_note.categorized_type = result.type.value
            voice_note.categorized_id = result.data.get("id")
            voice_note.categorization_status = "completed"
        except Exception as e:
            voice_note.categorization_status = "failed"
            # Store error in metadata
            meta = voice_note.extra_data or {}
            meta["categorization_error"] = str(e)
            voice_note.extra_data = meta

        self.db.commit()

    def _build_message(self, voice_note: VoiceNote) -> str:
        """Build a human-readable status message."""
        parts = [f"Voice note uploaded: {voice_note.filename}"]

        if voice_note.transcription_status == "completed":
            parts.append(f"Transcribed: {len(voice_note.transcription)} chars")
            if voice_note.categorized_type:
                parts.append(f"Categorized as: {voice_note.categorized_type}")
        elif voice_note.transcription_status == "failed":
            parts.append(f"Transcription failed: {voice_note.transcription_error}")
        elif voice_note.transcription_status == "pending":
            parts.append("Transcription pending")

        return ". ".join(parts)

    def transcribe_pending(self, voice_note_id: int) -> VoiceNoteResult:
        """Manually trigger transcription for a pending voice note."""
        voice_note = self.db.query(VoiceNote).filter(VoiceNote.id == voice_note_id).first()

        if not voice_note:
            return VoiceNoteResult(
                voice_note_id=voice_note_id,
                filename="",
                transcription=None,
                transcription_status="failed",
                categorized_type=None,
                categorized_id=None,
                success=False,
                message="Voice note not found"
            )

        self._transcribe(voice_note)

        if voice_note.transcription_status == "completed":
            self._categorize(voice_note)

        return VoiceNoteResult(
            voice_note_id=voice_note.id,
            filename=voice_note.filename,
            transcription=voice_note.transcription,
            transcription_status=voice_note.transcription_status,
            categorized_type=voice_note.categorized_type,
            categorized_id=voice_note.categorized_id,
            success=voice_note.transcription_status == "completed",
            message=self._build_message(voice_note)
        )

    def get_voice_note(self, voice_note_id: int) -> Optional[VoiceNote]:
        """Get a voice note by ID."""
        return self.db.query(VoiceNote).filter(VoiceNote.id == voice_note_id).first()

    def delete_voice_note(self, voice_note_id: int) -> bool:
        """Delete a voice note and its file."""
        voice_note = self.get_voice_note(voice_note_id)
        if not voice_note:
            return False

        # Delete file
        try:
            file_path = Path(voice_note.file_path)
            if file_path.exists():
                file_path.unlink()
        except Exception:
            pass  # Continue even if file deletion fails

        # Delete database record
        self.db.delete(voice_note)
        self.db.commit()

        return True
