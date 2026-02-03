"""
Quick capture, logging, tasks, and notes endpoints.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataPoint, JournalEntry, Task, Note
from ..integrations.capture import CaptureService, process_webhook
from ..schemas import (
    LogEnergyRequest,
    CaptureRequest,
    WebhookPayload,
    CaptureResponse,
    TaskResponse,
    NoteResponse,
)

router = APIRouter(prefix="/api", tags=["capture"])


@router.post("/log")
async def log_energy(
    request: LogEnergyRequest,
    db: Session = Depends(get_db)
):
    """
    Quick log energy/mood.

    Minimal friction capture for current state.
    """
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")

    entry = JournalEntry(
        date=date,
        time=time,
        energy=request.energy,
        mood=request.mood,
        notes=request.notes
    )
    db.add(entry)

    # Also store as data point for pattern analysis
    dp = DataPoint(
        source="manual",
        type="energy",
        date=date,
        value=request.energy,
        extra_data={
            "time": time,
            "mood": request.mood,
            "notes": request.notes
        }
    )
    db.add(dp)

    db.commit()

    return {
        "success": True,
        "date": date,
        "time": time,
        "energy": request.energy
    }


@router.post("/capture", response_model=CaptureResponse)
async def capture_message(
    request: CaptureRequest,
    db: Session = Depends(get_db)
):
    """
    Quick capture with AI categorization.

    Accepts free-form text, uses AI to categorize as note/task/energy,
    and stores appropriately.
    """
    service = CaptureService(db)
    result = service.process(
        text=request.text,
        source=request.source or "manual"
    )

    return CaptureResponse(
        type=result.type.value,
        success=result.success,
        message=result.message,
        data=result.data
    )


@router.post("/webhook/clawdbot", response_model=CaptureResponse)
async def clawdbot_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Clawdbot (Telegram/Discord).

    Receives messages and processes them through the capture system.
    """
    result = process_webhook(db, payload.model_dump())

    return CaptureResponse(
        type=result.type.value,
        success=result.success,
        message=result.message,
        data=result.data
    )


@router.get("/tasks", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get tasks, optionally filtered by status."""
    query = db.query(Task)

    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()

    return [
        TaskResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            due_date=t.due_date,
            tags=t.tags or [],
            source=t.source,
            created_at=t.created_at.isoformat()
        )
        for t in tasks
    ]


@router.get("/notes", response_model=List[NoteResponse])
async def get_notes(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get recent notes."""
    notes = db.query(Note).order_by(Note.created_at.desc()).limit(limit).all()

    return [
        NoteResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            tags=n.tags or [],
            source=n.source,
            created_at=n.created_at.isoformat()
        )
        for n in notes
    ]
