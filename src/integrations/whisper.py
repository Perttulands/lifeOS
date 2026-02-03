"""
LifeOS Whisper Integration

OpenAI Whisper API integration for speech-to-text transcription.
"""

import os
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from openai import OpenAI

from ..config import settings


@dataclass
class TranscriptionResult:
    """Result from Whisper transcription."""
    text: str
    language: Optional[str]
    duration: Optional[float]
    success: bool
    error: Optional[str] = None


# Supported audio formats for Whisper API
SUPPORTED_FORMATS = {
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/wave": ".wav",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/mp4": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
    "audio/flac": ".flac",
}

# Max file size for Whisper API (25 MB)
MAX_FILE_SIZE = 25 * 1024 * 1024


class WhisperService:
    """
    Service for transcribing audio using OpenAI's Whisper API.

    Uses the openai library directly for Whisper API calls.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Whisper service.

        Args:
            api_key: OpenAI API key. Falls back to settings if not provided.
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise ValueError("OpenAI API key required for Whisper transcription")

        self.client = OpenAI(api_key=self.api_key)

    def transcribe(
        self,
        file_path: str,
        language: Optional[str] = None,
        prompt: Optional[str] = None
    ) -> TranscriptionResult:
        """
        Transcribe an audio file using Whisper API.

        Args:
            file_path: Path to the audio file
            language: Optional language code (e.g., 'en', 'fi'). Auto-detected if not provided.
            prompt: Optional prompt to guide transcription style

        Returns:
            TranscriptionResult with transcription text and metadata
        """
        path = Path(file_path)

        # Validate file exists
        if not path.exists():
            return TranscriptionResult(
                text="",
                language=None,
                duration=None,
                success=False,
                error=f"File not found: {file_path}"
            )

        # Validate file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return TranscriptionResult(
                text="",
                language=None,
                duration=None,
                success=False,
                error=f"File too large: {file_size / 1024 / 1024:.1f} MB (max 25 MB)"
            )

        try:
            with open(file_path, "rb") as audio_file:
                # Build API parameters
                params = {
                    "model": "whisper-1",
                    "file": audio_file,
                    "response_format": "verbose_json",
                }

                if language:
                    params["language"] = language

                if prompt:
                    params["prompt"] = prompt

                # Call Whisper API
                response = self.client.audio.transcriptions.create(**params)

                return TranscriptionResult(
                    text=response.text,
                    language=getattr(response, 'language', None),
                    duration=getattr(response, 'duration', None),
                    success=True
                )

        except Exception as e:
            return TranscriptionResult(
                text="",
                language=None,
                duration=None,
                success=False,
                error=str(e)
            )

    def validate_file(self, file_path: str, mime_type: Optional[str] = None) -> Tuple[bool, str]:
        """
        Validate an audio file for Whisper transcription.

        Args:
            file_path: Path to the audio file
            mime_type: Optional MIME type of the file

        Returns:
            Tuple of (is_valid, error_message)
        """
        path = Path(file_path)

        # Check file exists
        if not path.exists():
            return False, "File not found"

        # Check file size
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE:
            return False, f"File too large: {file_size / 1024 / 1024:.1f} MB (max 25 MB)"

        if file_size == 0:
            return False, "File is empty"

        # Check format by extension
        ext = path.suffix.lower()
        valid_extensions = set(SUPPORTED_FORMATS.values())
        if ext not in valid_extensions:
            # Also check by mime type
            if mime_type and mime_type in SUPPORTED_FORMATS:
                return True, ""
            return False, f"Unsupported format: {ext}. Supported: {', '.join(valid_extensions)}"

        return True, ""


def get_whisper_service() -> Optional[WhisperService]:
    """
    Get Whisper service instance if configured.

    Returns None if OpenAI API key is not set.
    """
    if not settings.openai_api_key:
        return None

    try:
        return WhisperService()
    except ValueError:
        return None


def is_whisper_configured() -> bool:
    """Check if Whisper transcription is available."""
    return bool(settings.openai_api_key)
