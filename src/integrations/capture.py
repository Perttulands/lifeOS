"""
LifeOS Quick Capture

AI-powered categorization and storage of messages from Telegram/Discord via Clawdbot.

Receives raw text, categorizes it (note/energy/task), and stores appropriately.
"""

import json
import re
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from ..ai import get_ai
from ..models import Task, Note, JournalEntry, DataPoint
from ..config import settings


class CaptureType(str, Enum):
    """Type of captured content."""
    NOTE = "note"
    TASK = "task"
    ENERGY = "energy"
    UNKNOWN = "unknown"


@dataclass
class CaptureResult:
    """Result of processing a captured message."""
    type: CaptureType
    success: bool
    message: str
    data: Dict[str, Any]


class CaptureService:
    """
    Service for processing quick captures from Telegram/Discord.

    Uses AI to categorize input and store it appropriately.
    """

    SYSTEM_PROMPT = """You are LifeOS capture assistant. Your job is to categorize incoming messages and extract structured data.

Given a raw message, determine if it's:
1. TASK - Something the user needs to do (action items, reminders, todos)
2. NOTE - An idea, thought, observation, or piece of information to remember
3. ENERGY - A self-report of current energy/mood level (e.g., "feeling tired", "energy 3/5", "great mood today")

Respond with JSON only:
{
  "type": "task" | "note" | "energy",
  "confidence": 0.0-1.0,
  "extracted": {
    // For TASK:
    "title": "concise task title",
    "priority": "low" | "normal" | "high" | "urgent",
    "due_date": "YYYY-MM-DD or null",
    "tags": ["tag1", "tag2"]

    // For NOTE:
    "title": "brief title for the note",
    "content": "the note content, cleaned up",
    "tags": ["tag1", "tag2"]

    // For ENERGY:
    "level": 1-5,
    "mood": 1-5 or null,
    "notes": "any additional context"
  },
  "reasoning": "brief explanation of categorization"
}

Examples:

Input: "buy groceries tomorrow"
Output: {"type": "task", "confidence": 0.95, "extracted": {"title": "Buy groceries", "priority": "normal", "due_date": null, "tags": ["errands"]}, "reasoning": "Action item with verb"}

Input: "had a great idea about the new dashboard - maybe add a weekly view"
Output: {"type": "note", "confidence": 0.9, "extracted": {"title": "Dashboard weekly view idea", "content": "Had a great idea about the new dashboard - maybe add a weekly view", "tags": ["ideas", "dashboard"]}, "reasoning": "Idea/thought to remember"}

Input: "feeling pretty tired today, maybe 2/5 energy"
Output: {"type": "energy", "confidence": 0.95, "extracted": {"level": 2, "mood": null, "notes": "feeling pretty tired today"}, "reasoning": "Self-report of energy level"}

Input: "the meeting with Sarah went well"
Output: {"type": "note", "confidence": 0.85, "extracted": {"title": "Meeting with Sarah", "content": "The meeting with Sarah went well", "tags": ["meetings"]}, "reasoning": "Observation about past event"}

Be generous with categorization - when in doubt, classify as a note."""

    def __init__(self, db: Session):
        self.db = db
        self.ai = get_ai()

    def process(
        self,
        text: str,
        source: str = "manual",
        metadata: Optional[Dict[str, Any]] = None
    ) -> CaptureResult:
        """
        Process a captured message.

        Args:
            text: Raw captured text
            source: Where it came from (telegram, discord, manual)
            metadata: Additional context (user_id, timestamp, etc.)

        Returns:
            CaptureResult with categorization and storage result
        """
        if not text or not text.strip():
            return CaptureResult(
                type=CaptureType.UNKNOWN,
                success=False,
                message="Empty input",
                data={}
            )

        text = text.strip()
        metadata = metadata or {}

        # Try to categorize with AI
        categorization = self._categorize(text)

        if not categorization:
            # Fallback: store as note
            return self._store_note(
                text=text,
                title=text[:50] + "..." if len(text) > 50 else text,
                tags=[],
                source=source,
                metadata=metadata
            )

        capture_type = CaptureType(categorization.get("type", "note"))
        extracted = categorization.get("extracted", {})

        # Store based on type
        if capture_type == CaptureType.TASK:
            return self._store_task(
                title=extracted.get("title", text[:100]),
                priority=extracted.get("priority", "normal"),
                due_date=extracted.get("due_date"),
                tags=extracted.get("tags", []),
                source=source,
                raw_input=text,
                metadata=metadata
            )
        elif capture_type == CaptureType.ENERGY:
            return self._store_energy(
                level=extracted.get("level", 3),
                mood=extracted.get("mood"),
                notes=extracted.get("notes", text),
                source=source,
                metadata=metadata
            )
        else:  # NOTE or fallback
            return self._store_note(
                text=extracted.get("content", text),
                title=extracted.get("title"),
                tags=extracted.get("tags", []),
                source=source,
                metadata=metadata
            )

    def _categorize(self, text: str) -> Optional[Dict[str, Any]]:
        """Use AI to categorize the input text."""
        try:
            response, _ = self.ai._call_llm(
                system_prompt=self.SYSTEM_PROMPT,
                user_prompt=text,
                temperature=0.3,  # Lower temp for consistent categorization
                max_tokens=300
            )

            # Extract JSON from response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(response[start:end])
        except Exception:
            pass

        return None

    def _store_task(
        self,
        title: str,
        priority: str,
        due_date: Optional[str],
        tags: List[str],
        source: str,
        raw_input: str,
        metadata: Dict[str, Any]
    ) -> CaptureResult:
        """Store as a task."""
        task = Task(
            title=title,
            priority=priority,
            due_date=due_date,
            tags=tags,
            source=source,
            raw_input=raw_input,
            metadata=metadata
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        return CaptureResult(
            type=CaptureType.TASK,
            success=True,
            message=f"Task created: {title}",
            data={
                "id": task.id,
                "title": task.title,
                "priority": task.priority,
                "due_date": task.due_date,
                "tags": task.tags
            }
        )

    def _store_note(
        self,
        text: str,
        title: Optional[str],
        tags: List[str],
        source: str,
        metadata: Dict[str, Any]
    ) -> CaptureResult:
        """Store as a note."""
        note = Note(
            content=text,
            title=title or (text[:50] + "..." if len(text) > 50 else text),
            tags=tags,
            source=source,
            raw_input=text,
            metadata=metadata
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)

        return CaptureResult(
            type=CaptureType.NOTE,
            success=True,
            message=f"Note saved: {note.title}",
            data={
                "id": note.id,
                "title": note.title,
                "content": note.content,
                "tags": note.tags
            }
        )

    def _store_energy(
        self,
        level: int,
        mood: Optional[int],
        notes: str,
        source: str,
        metadata: Dict[str, Any]
    ) -> CaptureResult:
        """Store as an energy log."""
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M")

        # Clamp values to valid range
        level = max(1, min(5, level))
        if mood:
            mood = max(1, min(5, mood))

        # Create journal entry
        entry = JournalEntry(
            date=date,
            time=time,
            energy=level,
            mood=mood,
            notes=notes,
            tags=[source]
        )
        self.db.add(entry)

        # Also store as data point for pattern analysis
        dp = DataPoint(
            source=source,
            type="energy",
            date=date,
            value=level,
            metadata={
                "time": time,
                "mood": mood,
                "notes": notes
            }
        )
        self.db.add(dp)

        self.db.commit()
        self.db.refresh(entry)

        return CaptureResult(
            type=CaptureType.ENERGY,
            success=True,
            message=f"Energy logged: {level}/5" + (f", mood {mood}/5" if mood else ""),
            data={
                "id": entry.id,
                "date": date,
                "time": time,
                "energy": level,
                "mood": mood,
                "notes": notes
            }
        )


def process_webhook(
    db: Session,
    payload: Dict[str, Any]
) -> CaptureResult:
    """
    Process a webhook payload from Clawdbot.

    Expected payload format:
    {
        "text": "the message content",
        "source": "telegram" | "discord",
        "user_id": "optional user identifier",
        "timestamp": "ISO timestamp",
        "chat_id": "optional chat/channel id",
        "message_id": "optional message id"
    }
    """
    text = payload.get("text", "")
    source = payload.get("source", "webhook")

    metadata = {
        "user_id": payload.get("user_id"),
        "timestamp": payload.get("timestamp"),
        "chat_id": payload.get("chat_id"),
        "message_id": payload.get("message_id")
    }
    # Remove None values
    metadata = {k: v for k, v in metadata.items() if v is not None}

    service = CaptureService(db)
    return service.process(text=text, source=source, metadata=metadata)
