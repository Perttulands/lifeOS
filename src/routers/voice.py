"""
Voice notes upload and transcription endpoints.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import VoiceNote
from ..integrations.voice import VoiceNoteService, VOICE_NOTES_DIR
from ..integrations.whisper import is_whisper_configured, SUPPORTED_FORMATS, MAX_FILE_SIZE
from ..schemas import (
    VoiceNoteResponse,
    VoiceNoteUploadResponse,
    VoiceNoteStatusResponse,
)

router = APIRouter(prefix="/api/voice", tags=["voice"])


@router.get("/status", response_model=VoiceNoteStatusResponse)
async def get_voice_status():
    """
    Get voice note service status.

    Returns whether Whisper is configured and supported formats.
    """
    return VoiceNoteStatusResponse(
        whisper_configured=is_whisper_configured(),
        supported_formats=list(set(SUPPORTED_FORMATS.values())),
        max_file_size_mb=MAX_FILE_SIZE // (1024 * 1024)
    )


@router.post("/upload", response_model=VoiceNoteUploadResponse)
async def upload_voice_note(
    file: UploadFile = File(...),
    source: str = Query("upload", description="Source of upload"),
    auto_transcribe: bool = Query(True, description="Transcribe immediately"),
    auto_categorize: bool = Query(True, description="Auto-categorize after transcription"),
    db: Session = Depends(get_db)
):
    """
    Upload a voice note for transcription.

    Accepts audio files up to 25 MB in formats: mp3, wav, m4a, webm, ogg, flac.

    If auto_transcribe is True (default), the file will be transcribed via Whisper.
    If auto_categorize is True (default), the transcribed text will be auto-categorized
    as a note, task, or energy log.
    """
    # Read file content
    content = await file.read()

    # Process upload
    service = VoiceNoteService(db)
    result = service.process_upload(
        file_content=content,
        filename=file.filename or "audio.mp3",
        mime_type=file.content_type,
        source=source,
        auto_transcribe=auto_transcribe,
        auto_categorize=auto_categorize
    )

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return VoiceNoteUploadResponse(
        id=result.voice_note_id,
        filename=result.filename,
        transcription=result.transcription,
        transcription_status=result.transcription_status,
        categorized_type=result.categorized_type,
        categorized_id=result.categorized_id,
        success=result.success,
        message=result.message
    )


@router.get("/notes", response_model=List[VoiceNoteResponse])
async def list_voice_notes(
    limit: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by transcription status"),
    db: Session = Depends(get_db)
):
    """Get recent voice notes."""
    query = db.query(VoiceNote)

    if status:
        query = query.filter(VoiceNote.transcription_status == status)

    notes = query.order_by(VoiceNote.created_at.desc()).limit(limit).all()

    return [
        VoiceNoteResponse(
            id=n.id,
            filename=n.filename,
            file_size=n.file_size,
            duration_seconds=n.duration_seconds,
            mime_type=n.mime_type,
            transcription=n.transcription,
            transcription_status=n.transcription_status,
            transcription_language=n.transcription_language,
            categorized_type=n.categorized_type,
            categorized_id=n.categorized_id,
            source=n.source,
            created_at=n.created_at.isoformat()
        )
        for n in notes
    ]


@router.get("/notes/{note_id}", response_model=VoiceNoteResponse)
async def get_voice_note(
    note_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific voice note."""
    note = db.query(VoiceNote).filter(VoiceNote.id == note_id).first()

    if not note:
        raise HTTPException(status_code=404, detail="Voice note not found")

    return VoiceNoteResponse(
        id=note.id,
        filename=note.filename,
        file_size=note.file_size,
        duration_seconds=note.duration_seconds,
        mime_type=note.mime_type,
        transcription=note.transcription,
        transcription_status=note.transcription_status,
        transcription_language=note.transcription_language,
        categorized_type=note.categorized_type,
        categorized_id=note.categorized_id,
        source=note.source,
        created_at=note.created_at.isoformat()
    )


@router.post("/notes/{note_id}/transcribe", response_model=VoiceNoteUploadResponse)
async def transcribe_voice_note(
    note_id: int,
    db: Session = Depends(get_db)
):
    """
    Manually trigger transcription for a voice note.

    Useful if the note was uploaded without auto_transcribe or if transcription failed.
    """
    service = VoiceNoteService(db)
    result = service.transcribe_pending(note_id)

    if not result.success and result.voice_note_id == 0:
        raise HTTPException(status_code=404, detail=result.message)

    return VoiceNoteUploadResponse(
        id=result.voice_note_id,
        filename=result.filename,
        transcription=result.transcription,
        transcription_status=result.transcription_status,
        categorized_type=result.categorized_type,
        categorized_id=result.categorized_id,
        success=result.success,
        message=result.message
    )


@router.delete("/notes/{note_id}")
async def delete_voice_note(
    note_id: int,
    db: Session = Depends(get_db)
):
    """Delete a voice note and its audio file."""
    service = VoiceNoteService(db)
    deleted = service.delete_voice_note(note_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Voice note not found")

    return {"status": "ok", "message": "Voice note deleted"}
