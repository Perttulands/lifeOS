"""
User settings endpoints.
"""

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User
from ..schemas import (
    SettingsResponse,
    SettingsUpdateRequest,
    NotificationSettings,
    IntegrationStatus,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
async def get_settings(db: Session = Depends(get_db)):
    """
    Get current user settings.

    Returns user preferences, notification settings, and integration status.
    """
    # Get or create user
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, name="User", timezone="UTC", preferences={})
        db.add(user)
        db.commit()
        db.refresh(user)

    prefs = user.preferences or {}

    # Check integration status
    integrations = IntegrationStatus(
        oura_configured=bool(settings.oura_token),
        ai_configured=bool(settings.get_ai_api_key()),
        telegram_configured=bool(settings.telegram_bot_token and settings.telegram_chat_id),
        discord_configured=bool(settings.discord_webhook_url)
    )

    # Build notification settings
    notifications = NotificationSettings(
        telegram_enabled=integrations.telegram_configured and prefs.get('telegram_enabled', True),
        discord_enabled=integrations.discord_configured and prefs.get('discord_enabled', True),
        quiet_hours_enabled=prefs.get('quiet_hours_enabled', settings.quiet_hours_enabled),
        quiet_hours_start=prefs.get('quiet_hours_start', settings.quiet_hours_start),
        quiet_hours_end=prefs.get('quiet_hours_end', settings.quiet_hours_end)
    )

    return SettingsResponse(
        user_name=user.name,
        timezone=user.timezone or settings.user_timezone,
        notifications=notifications,
        integrations=integrations,
        ai_model=settings.litellm_model
    )


@router.put("", response_model=SettingsResponse)
async def update_settings(
    request: SettingsUpdateRequest,
    db: Session = Depends(get_db)
):
    """
    Update user settings.

    Updates user preferences stored in the database.
    Note: API keys must be configured via .env file for security.
    """
    # Get or create user
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, name="User", timezone="UTC", preferences={})
        db.add(user)

    # Update user fields
    if request.user_name is not None:
        user.name = request.user_name

    if request.timezone is not None:
        user.timezone = request.timezone

    # Update preferences JSON
    prefs = user.preferences or {}

    if request.quiet_hours_enabled is not None:
        prefs['quiet_hours_enabled'] = request.quiet_hours_enabled

    if request.quiet_hours_start is not None:
        prefs['quiet_hours_start'] = request.quiet_hours_start

    if request.quiet_hours_end is not None:
        prefs['quiet_hours_end'] = request.quiet_hours_end

    user.preferences = prefs
    user.updated_at = datetime.utcnow()

    db.commit()
    db.refresh(user)

    # Return updated settings
    return await get_settings(db)


@router.get("/timezones")
async def get_timezones():
    """
    Get list of common timezones for the settings UI.
    """
    timezones = [
        "UTC",
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "America/Toronto",
        "America/Vancouver",
        "Europe/London",
        "Europe/Paris",
        "Europe/Berlin",
        "Europe/Helsinki",
        "Europe/Moscow",
        "Asia/Tokyo",
        "Asia/Shanghai",
        "Asia/Singapore",
        "Asia/Dubai",
        "Asia/Kolkata",
        "Australia/Sydney",
        "Australia/Melbourne",
        "Pacific/Auckland",
    ]
    return {"timezones": timezones}
