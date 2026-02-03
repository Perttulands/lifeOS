"""
Google Calendar integration endpoints.

OAuth2 flow and calendar sync API.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import CalendarEvent
from ..integrations.calendar import (
    get_oauth_url,
    exchange_code_for_tokens,
    save_oauth_token,
    get_oauth_token,
    is_token_expired,
    CalendarSyncService,
    GoogleCalendarClient,
)
from ..schemas import (
    CalendarAuthUrlResponse,
    CalendarEventResponse,
    CalendarSyncRequest,
    CalendarSyncResultResponse,
    CalendarStatusResponse,
    MeetingStatsResponse,
)

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/status", response_model=CalendarStatusResponse)
async def calendar_status(db: Session = Depends(get_db)):
    """
    Check Google Calendar integration status.

    Returns whether OAuth is configured, if we have a valid token,
    and when the last sync occurred.
    """
    configured = bool(settings.google_client_id and settings.google_client_secret)

    token = get_oauth_token(db)
    connected = False
    last_sync = None
    calendars = []

    if token and not is_token_expired(token):
        connected = True

        # Get last synced event time
        last_event = db.query(CalendarEvent).order_by(
            CalendarEvent.synced_at.desc()
        ).first()
        if last_event:
            last_sync = last_event.synced_at.isoformat()

        # Try to get calendar list
        try:
            client = GoogleCalendarClient(
                access_token=token.access_token,
                refresh_token=token.refresh_token
            )
            cal_list = client.get_calendar_list()
            if cal_list:
                calendars = [
                    {"id": c.get("id"), "name": c.get("summary")}
                    for c in cal_list[:5]  # Limit to 5 calendars
                ]
            client.close()
        except Exception:
            pass

    return CalendarStatusResponse(
        configured=configured,
        connected=connected,
        last_sync=last_sync,
        calendars=calendars
    )


@router.get("/auth", response_model=CalendarAuthUrlResponse)
async def get_auth_url():
    """
    Get the Google OAuth2 authorization URL.

    Redirect users to this URL to authorize calendar access.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        return CalendarAuthUrlResponse(
            auth_url="",
            configured=False
        )

    auth_url = get_oauth_url()

    return CalendarAuthUrlResponse(
        auth_url=auth_url,
        configured=True
    )


@router.get("/callback")
async def oauth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth2 callback from Google.

    Exchanges the authorization code for access and refresh tokens.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error}"
        )

    if not code:
        raise HTTPException(
            status_code=400,
            detail="No authorization code received"
        )

    # Exchange code for tokens
    token_data = exchange_code_for_tokens(code)

    if not token_data:
        raise HTTPException(
            status_code=500,
            detail="Failed to exchange authorization code for tokens"
        )

    # Save tokens to database
    save_oauth_token(db, token_data)

    # Redirect to settings page or return success
    return RedirectResponse(url="/?calendar=connected")


@router.post("/disconnect")
async def disconnect_calendar(db: Session = Depends(get_db)):
    """
    Disconnect Google Calendar integration.

    Removes stored OAuth tokens.
    """
    token = get_oauth_token(db)

    if token:
        db.delete(token)
        db.commit()

    return {"success": True, "message": "Calendar disconnected"}


@router.post("/sync", response_model=CalendarSyncResultResponse)
async def sync_calendar(
    request: CalendarSyncRequest,
    db: Session = Depends(get_db)
):
    """
    Sync calendar events from Google Calendar.

    Fetches events within the specified date range and stores them
    in the database. Also creates meeting density data points for
    pattern detection.
    """
    service = CalendarSyncService(db)
    result = service.sync(
        days_back=request.days_back,
        days_forward=request.days_forward,
        calendar_id=request.calendar_id
    )

    return CalendarSyncResultResponse(
        status=result.status.value,
        events_synced=result.events_synced,
        events_updated=result.events_updated,
        events_deleted=result.events_deleted,
        date_range=list(result.date_range),
        errors=result.errors
    )


@router.get("/events", response_model=list[CalendarEventResponse])
async def get_events(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Get stored calendar events.

    Returns events from the database within the specified date range.
    """
    query = db.query(CalendarEvent).filter(
        CalendarEvent.status != "cancelled"
    )

    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(CalendarEvent.start_time >= start_dt)

    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        end_dt = end_dt.replace(hour=23, minute=59, second=59)
        query = query.filter(CalendarEvent.start_time <= end_dt)

    events = query.order_by(CalendarEvent.start_time).limit(limit).all()

    return [
        CalendarEventResponse(
            id=e.id,
            event_id=e.event_id,
            summary=e.summary,
            description=e.description,
            location=e.location,
            start_time=e.start_time.isoformat(),
            end_time=e.end_time.isoformat(),
            all_day=e.all_day,
            status=e.status,
            organizer=e.organizer,
            attendees_count=e.attendees_count
        )
        for e in events
    ]


@router.get("/stats/{date}", response_model=MeetingStatsResponse)
async def get_meeting_stats(
    date: str,
    db: Session = Depends(get_db)
):
    """
    Get meeting statistics for a specific date.

    Returns meeting count, total hours, back-to-back meetings,
    and early/late meeting counts.
    """
    service = CalendarSyncService(db)
    stats = service.get_meeting_stats(date)

    return MeetingStatsResponse(**stats)


@router.get("/today")
async def get_today_meetings(db: Session = Depends(get_db)):
    """
    Get today's calendar overview.

    Convenient endpoint for dashboard display.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    service = CalendarSyncService(db)
    stats = service.get_meeting_stats(today)

    return {
        "date": today,
        "summary": f"{stats['meeting_count']} meetings, {stats['total_hours']}h total",
        "stats": stats
    }
