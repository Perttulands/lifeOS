"""
First-run onboarding wizard endpoints.

Detects empty database state and guides users through:
1. Verifying Oura connection
2. Testing AI configuration
3. Importing historical data
4. Setting preferences
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..models import DataPoint, User, Insight

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


# === Pydantic Models ===

class SetupStep(BaseModel):
    """Individual setup step status."""
    id: str
    title: str
    description: str
    status: str  # pending, in_progress, completed, error, skipped
    required: bool
    error_message: Optional[str] = None
    help_url: Optional[str] = None


class OnboardingStatus(BaseModel):
    """Overall onboarding status."""
    is_first_run: bool
    setup_complete: bool
    current_step: Optional[str] = None
    steps: List[SetupStep]
    progress_percent: int


class ConnectionTestResult(BaseModel):
    """Result of testing a service connection."""
    service: str
    connected: bool
    message: str
    details: Optional[Dict[str, Any]] = None
    fix_suggestions: Optional[List[str]] = None


class OnboardingCompleteResponse(BaseModel):
    """Response when onboarding is completed."""
    success: bool
    message: str
    next_steps: List[str]


# === Helper Functions ===

def check_oura_configured() -> tuple[bool, Optional[str]]:
    """Check if Oura is configured."""
    if not settings.oura_token:
        return False, "OURA_TOKEN not set in environment"
    if settings.oura_token == "your_oura_personal_access_token":
        return False, "OURA_TOKEN is still the placeholder value"
    return True, None


def check_ai_configured() -> tuple[bool, Optional[str]]:
    """Check if AI is configured."""
    api_key = settings.get_ai_api_key()
    if not api_key:
        return False, "No AI API key configured (LITELLM_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY)"
    if api_key == "your_api_key":
        return False, "API key is still the placeholder value"
    return True, None


def get_data_counts(db: Session) -> Dict[str, int]:
    """Get counts of various data types."""
    return {
        "oura_records": db.query(DataPoint).filter(DataPoint.source == "oura").count(),
        "insights": db.query(Insight).count(),
        "users": db.query(User).count(),
    }


# === Endpoints ===

@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(db: Session = Depends(get_db)):
    """
    Get current onboarding status.

    Returns whether this is a first-run scenario and the status
    of each setup step. Use this to show appropriate UI on load.
    """
    counts = get_data_counts(db)
    oura_ok, oura_error = check_oura_configured()
    ai_ok, ai_error = check_ai_configured()

    # Determine if this is first run
    is_first_run = counts["oura_records"] == 0 and counts["insights"] == 0

    # Build steps list
    steps = []

    # Step 1: Oura Connection
    oura_status = "completed" if oura_ok and counts["oura_records"] > 0 else (
        "error" if not oura_ok else "pending"
    )
    steps.append(SetupStep(
        id="oura",
        title="Connect Oura",
        description="Link your Oura Ring for sleep and activity data",
        status=oura_status,
        required=True,
        error_message=oura_error,
        help_url="https://cloud.ouraring.com/personal-access-tokens"
    ))

    # Step 2: AI Configuration
    ai_status = "completed" if ai_ok else "error"
    steps.append(SetupStep(
        id="ai",
        title="Configure AI",
        description="Set up AI for personalized insights",
        status=ai_status,
        required=True,
        error_message=ai_error,
        help_url="https://platform.openai.com/api-keys"
    ))

    # Step 3: Import Data
    import_status = "completed" if counts["oura_records"] >= 7 else (
        "pending" if oura_ok else "pending"
    )
    steps.append(SetupStep(
        id="import",
        title="Import Historical Data",
        description="Backfill 90 days of Oura data for better insights",
        status=import_status,
        required=False,
        help_url=None
    ))

    # Step 4: Notifications (optional)
    notify_configured = bool(settings.telegram_bot_token or settings.discord_webhook_url)
    steps.append(SetupStep(
        id="notifications",
        title="Set Up Notifications",
        description="Get your daily brief via Telegram or Discord",
        status="completed" if notify_configured else "skipped",
        required=False,
        help_url=None
    ))

    # Calculate progress
    completed_required = sum(1 for s in steps if s.required and s.status == "completed")
    total_required = sum(1 for s in steps if s.required)
    progress = int((completed_required / total_required) * 100) if total_required > 0 else 0

    # Determine current step
    current_step = None
    for step in steps:
        if step.status in ("pending", "error") and step.required:
            current_step = step.id
            break

    setup_complete = all(s.status in ("completed", "skipped") for s in steps if s.required)

    return OnboardingStatus(
        is_first_run=is_first_run,
        setup_complete=setup_complete,
        current_step=current_step,
        steps=steps,
        progress_percent=progress
    )


@router.post("/test/oura", response_model=ConnectionTestResult)
async def test_oura_connection():
    """
    Test Oura API connection.

    Verifies the token is valid and can fetch data.
    Returns detailed error information if connection fails.
    """
    configured, error = check_oura_configured()

    if not configured:
        return ConnectionTestResult(
            service="oura",
            connected=False,
            message=error or "Oura not configured",
            fix_suggestions=[
                "Get your Personal Access Token from https://cloud.ouraring.com/personal-access-tokens",
                "Add OURA_TOKEN=your_token to your .env file",
                "Restart the server after updating .env"
            ]
        )

    # Try to fetch data from Oura
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{settings.oura_base_url}/usercollection/personal_info",
                headers={"Authorization": f"Bearer {settings.oura_token}"},
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                return ConnectionTestResult(
                    service="oura",
                    connected=True,
                    message="Successfully connected to Oura",
                    details={
                        "email": data.get("email", "N/A"),
                        "age": data.get("age"),
                    }
                )
            elif response.status_code == 401:
                return ConnectionTestResult(
                    service="oura",
                    connected=False,
                    message="Invalid or expired Oura token",
                    fix_suggestions=[
                        "Your token may have expired - generate a new one",
                        "Go to https://cloud.ouraring.com/personal-access-tokens",
                        "Create a new Personal Access Token and update .env"
                    ]
                )
            elif response.status_code == 429:
                return ConnectionTestResult(
                    service="oura",
                    connected=False,
                    message="Oura API rate limit exceeded",
                    fix_suggestions=[
                        "Wait a few minutes and try again",
                        "Oura limits requests to ~5000/month"
                    ]
                )
            else:
                return ConnectionTestResult(
                    service="oura",
                    connected=False,
                    message=f"Oura API returned status {response.status_code}",
                    fix_suggestions=[
                        "Check Oura API status at https://status.ouraring.com",
                        "Try again in a few minutes"
                    ]
                )

    except httpx.TimeoutException:
        return ConnectionTestResult(
            service="oura",
            connected=False,
            message="Connection to Oura timed out",
            fix_suggestions=[
                "Check your internet connection",
                "Oura API may be experiencing issues"
            ]
        )
    except Exception as e:
        return ConnectionTestResult(
            service="oura",
            connected=False,
            message=f"Connection error: {str(e)}",
            fix_suggestions=[
                "Check your internet connection",
                "Verify the OURA_TOKEN in .env is correct"
            ]
        )


@router.post("/test/ai", response_model=ConnectionTestResult)
async def test_ai_connection():
    """
    Test AI service connection.

    Sends a simple test request to verify the API key works.
    """
    configured, error = check_ai_configured()

    if not configured:
        return ConnectionTestResult(
            service="ai",
            connected=False,
            message=error or "AI not configured",
            fix_suggestions=[
                "Get an API key from OpenAI (https://platform.openai.com/api-keys)",
                "Or from Anthropic (https://console.anthropic.com/settings/keys)",
                "Add LITELLM_API_KEY=your_key to your .env file",
                "Restart the server after updating .env"
            ]
        )

    # Try a simple completion
    try:
        import litellm

        litellm.api_key = settings.get_ai_api_key()

        response = await litellm.acompletion(
            model=settings.litellm_model,
            messages=[{"role": "user", "content": "Say 'connected' in one word."}],
            max_tokens=10,
            timeout=15.0
        )

        return ConnectionTestResult(
            service="ai",
            connected=True,
            message="Successfully connected to AI service",
            details={
                "model": settings.litellm_model,
                "response": response.choices[0].message.content.strip()
            }
        )

    except Exception as e:
        error_msg = str(e).lower()

        # Parse common errors
        if "invalid api key" in error_msg or "incorrect api key" in error_msg:
            return ConnectionTestResult(
                service="ai",
                connected=False,
                message="Invalid API key",
                fix_suggestions=[
                    "Double-check your API key in .env",
                    "Make sure there are no extra spaces or quotes",
                    "Generate a new key if needed"
                ]
            )
        elif "insufficient" in error_msg or "quota" in error_msg:
            return ConnectionTestResult(
                service="ai",
                connected=False,
                message="API quota exceeded or insufficient credits",
                fix_suggestions=[
                    "Check your account balance/credits",
                    "Add payment method if using OpenAI",
                    "Upgrade your plan if needed"
                ]
            )
        elif "rate limit" in error_msg:
            return ConnectionTestResult(
                service="ai",
                connected=False,
                message="Rate limit exceeded",
                fix_suggestions=[
                    "Wait a minute and try again",
                    "Consider using a different model"
                ]
            )
        else:
            return ConnectionTestResult(
                service="ai",
                connected=False,
                message=f"AI service error: {str(e)[:100]}",
                fix_suggestions=[
                    "Check your API key is correct",
                    "Verify you have credits/quota",
                    "Try a different model (LITELLM_MODEL in .env)"
                ]
            )


@router.post("/complete", response_model=OnboardingCompleteResponse)
async def complete_onboarding(db: Session = Depends(get_db)):
    """
    Mark onboarding as complete.

    Creates initial user profile if needed and returns next steps.
    """
    # Ensure user exists
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(id=1, name="User", timezone=settings.user_timezone)
        db.add(user)
        db.commit()

    # Get current status
    counts = get_data_counts(db)

    next_steps = []

    if counts["oura_records"] == 0:
        next_steps.append("Import your Oura data: Settings > Data Import > Import Oura")

    if not settings.telegram_bot_token and not settings.discord_webhook_url:
        next_steps.append("Set up notifications to get your daily brief delivered")

    if not settings.google_client_id:
        next_steps.append("Connect Google Calendar for meeting pattern insights")

    next_steps.append("Check back tomorrow morning for your first Daily Brief!")

    return OnboardingCompleteResponse(
        success=True,
        message="Welcome to LifeOS! Your setup is complete.",
        next_steps=next_steps
    )


@router.get("/tips")
async def get_onboarding_tips():
    """
    Get contextual tips based on current setup state.

    Returns helpful suggestions for getting the most out of LifeOS.
    """
    tips = []

    # Check what's configured
    oura_ok, _ = check_oura_configured()
    ai_ok, _ = check_ai_configured()
    has_telegram = bool(settings.telegram_bot_token)
    has_discord = bool(settings.discord_webhook_url)
    has_calendar = bool(settings.google_client_id)

    if not oura_ok:
        tips.append({
            "icon": "ring",
            "title": "Connect Your Oura Ring",
            "description": "LifeOS works best with your sleep and activity data from Oura.",
            "action": "Get your token at cloud.ouraring.com",
            "priority": "high"
        })

    if not ai_ok:
        tips.append({
            "icon": "brain",
            "title": "Enable AI Insights",
            "description": "Add an AI API key to get personalized daily briefs and pattern detection.",
            "action": "Add LITELLM_API_KEY to .env",
            "priority": "high"
        })

    if oura_ok and not has_telegram and not has_discord:
        tips.append({
            "icon": "bell",
            "title": "Get Morning Notifications",
            "description": "Receive your daily brief via Telegram or Discord at 7 AM.",
            "action": "Configure in .env",
            "priority": "medium"
        })

    if oura_ok and not has_calendar:
        tips.append({
            "icon": "calendar",
            "title": "Connect Google Calendar",
            "description": "Detect how meetings affect your energy and sleep.",
            "action": "Visit /api/calendar/auth",
            "priority": "medium"
        })

    if oura_ok and ai_ok:
        tips.append({
            "icon": "chart",
            "title": "Import Historical Data",
            "description": "Backfill 90 days of data for better pattern detection.",
            "action": "Go to Settings > Data Import",
            "priority": "low"
        })

    return {"tips": tips}
