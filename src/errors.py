"""
LifeOS Error Handling

Provides user-friendly error messages with actionable fix suggestions.
All errors include context-aware help text.
"""

from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import HTTPException
from pydantic import BaseModel


class ErrorCategory(str, Enum):
    """Categories of errors for better UX."""
    CONFIGURATION = "configuration"
    AUTHENTICATION = "authentication"
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    VALIDATION = "validation"
    NOT_FOUND = "not_found"
    INTERNAL = "internal"


class HelpfulError(BaseModel):
    """
    Error response with actionable guidance.

    All LifeOS errors should include:
    - A clear, human-readable message
    - The category of error for UI handling
    - Specific suggestions to fix the issue
    - Optional documentation links
    """
    error: str
    message: str
    category: ErrorCategory
    suggestions: List[str]
    docs_url: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


class LifeOSException(HTTPException):
    """
    Custom exception with helpful error details.

    Usage:
        raise LifeOSException.oura_not_configured()
        raise LifeOSException.ai_quota_exceeded()
    """

    def __init__(
        self,
        status_code: int,
        error: str,
        message: str,
        category: ErrorCategory,
        suggestions: List[str],
        docs_url: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        self.helpful_error = HelpfulError(
            error=error,
            message=message,
            category=category,
            suggestions=suggestions,
            docs_url=docs_url,
            details=details
        )
        super().__init__(
            status_code=status_code,
            detail=self.helpful_error.model_dump()
        )

    # === Configuration Errors ===

    @classmethod
    def oura_not_configured(cls) -> "LifeOSException":
        """Oura token not set in environment."""
        return cls(
            status_code=503,
            error="oura_not_configured",
            message="Oura Ring is not configured",
            category=ErrorCategory.CONFIGURATION,
            suggestions=[
                "Get your Personal Access Token from cloud.ouraring.com/personal-access-tokens",
                "Add OURA_TOKEN=your_token to your .env file",
                "Restart the server after updating .env"
            ],
            docs_url="https://cloud.ouraring.com/personal-access-tokens"
        )

    @classmethod
    def ai_not_configured(cls) -> "LifeOSException":
        """AI API key not set."""
        return cls(
            status_code=503,
            error="ai_not_configured",
            message="AI service is not configured",
            category=ErrorCategory.CONFIGURATION,
            suggestions=[
                "Get an API key from OpenAI (platform.openai.com/api-keys)",
                "Or from Anthropic (console.anthropic.com/settings/keys)",
                "Add LITELLM_API_KEY=your_key to your .env file",
                "Restart the server after updating .env"
            ],
            docs_url="https://platform.openai.com/api-keys"
        )

    @classmethod
    def calendar_not_configured(cls) -> "LifeOSException":
        """Google Calendar OAuth not set up."""
        return cls(
            status_code=503,
            error="calendar_not_configured",
            message="Google Calendar is not configured",
            category=ErrorCategory.CONFIGURATION,
            suggestions=[
                "Create OAuth2 credentials at console.cloud.google.com/apis/credentials",
                "Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env",
                "Visit /api/calendar/auth to complete OAuth flow"
            ],
            docs_url="https://console.cloud.google.com/apis/credentials"
        )

    @classmethod
    def telegram_not_configured(cls) -> "LifeOSException":
        """Telegram bot not set up."""
        return cls(
            status_code=503,
            error="telegram_not_configured",
            message="Telegram notifications are not configured",
            category=ErrorCategory.CONFIGURATION,
            suggestions=[
                "Create a bot via @BotFather on Telegram",
                "Add TELEGRAM_BOT_TOKEN to .env",
                "Message your bot, then find your chat ID",
                "Add TELEGRAM_CHAT_ID to .env"
            ]
        )

    @classmethod
    def discord_not_configured(cls) -> "LifeOSException":
        """Discord webhook not set up."""
        return cls(
            status_code=503,
            error="discord_not_configured",
            message="Discord notifications are not configured",
            category=ErrorCategory.CONFIGURATION,
            suggestions=[
                "Go to your Discord channel settings",
                "Navigate to Integrations > Webhooks > New Webhook",
                "Copy the webhook URL",
                "Add DISCORD_WEBHOOK_URL to .env"
            ]
        )

    # === Authentication Errors ===

    @classmethod
    def oura_invalid_token(cls) -> "LifeOSException":
        """Oura token is invalid or expired."""
        return cls(
            status_code=401,
            error="oura_invalid_token",
            message="Your Oura token is invalid or has expired",
            category=ErrorCategory.AUTHENTICATION,
            suggestions=[
                "Generate a new Personal Access Token at cloud.ouraring.com",
                "Update OURA_TOKEN in your .env file",
                "Restart the server"
            ],
            docs_url="https://cloud.ouraring.com/personal-access-tokens"
        )

    @classmethod
    def ai_invalid_key(cls) -> "LifeOSException":
        """AI API key is invalid."""
        return cls(
            status_code=401,
            error="ai_invalid_key",
            message="Your AI API key is invalid",
            category=ErrorCategory.AUTHENTICATION,
            suggestions=[
                "Double-check your API key in .env",
                "Make sure there are no extra spaces or quotes",
                "Generate a new key if needed"
            ]
        )

    @classmethod
    def calendar_token_expired(cls) -> "LifeOSException":
        """Google Calendar OAuth token expired."""
        return cls(
            status_code=401,
            error="calendar_token_expired",
            message="Google Calendar authorization has expired",
            category=ErrorCategory.AUTHENTICATION,
            suggestions=[
                "Visit /api/calendar/auth to re-authorize",
                "Complete the Google OAuth flow again"
            ]
        )

    # === Rate Limit Errors ===

    @classmethod
    def oura_rate_limited(cls, retry_after: Optional[int] = None) -> "LifeOSException":
        """Oura API rate limit exceeded."""
        suggestions = ["Wait a few minutes and try again"]
        if retry_after:
            suggestions.insert(0, f"Try again in {retry_after} seconds")
        suggestions.append("Oura allows ~5000 requests per month")

        return cls(
            status_code=429,
            error="oura_rate_limited",
            message="Oura API rate limit exceeded",
            category=ErrorCategory.RATE_LIMIT,
            suggestions=suggestions,
            details={"retry_after_seconds": retry_after} if retry_after else None
        )

    @classmethod
    def ai_rate_limited(cls, model: Optional[str] = None) -> "LifeOSException":
        """AI API rate limit exceeded."""
        suggestions = [
            "Wait a minute and try again",
            "Consider using a smaller/faster model"
        ]
        if model:
            suggestions.append(f"Current model: {model}")

        return cls(
            status_code=429,
            error="ai_rate_limited",
            message="AI service rate limit exceeded",
            category=ErrorCategory.RATE_LIMIT,
            suggestions=suggestions,
            details={"model": model} if model else None
        )

    @classmethod
    def ai_quota_exceeded(cls) -> "LifeOSException":
        """AI API quota/credits exhausted."""
        return cls(
            status_code=429,
            error="ai_quota_exceeded",
            message="AI service quota exceeded or insufficient credits",
            category=ErrorCategory.RATE_LIMIT,
            suggestions=[
                "Check your account balance/credits",
                "Add payment method or credits to your AI provider",
                "Consider using a cheaper model (gpt-4o-mini)"
            ]
        )

    # === Connection Errors ===

    @classmethod
    def oura_connection_failed(cls, reason: Optional[str] = None) -> "LifeOSException":
        """Failed to connect to Oura API."""
        suggestions = [
            "Check your internet connection",
            "Oura API may be experiencing issues",
            "Try again in a few minutes"
        ]
        return cls(
            status_code=503,
            error="oura_connection_failed",
            message=f"Failed to connect to Oura{f': {reason}' if reason else ''}",
            category=ErrorCategory.CONNECTION,
            suggestions=suggestions,
            docs_url="https://status.ouraring.com"
        )

    @classmethod
    def ai_connection_failed(cls, reason: Optional[str] = None) -> "LifeOSException":
        """Failed to connect to AI service."""
        return cls(
            status_code=503,
            error="ai_connection_failed",
            message=f"Failed to connect to AI service{f': {reason}' if reason else ''}",
            category=ErrorCategory.CONNECTION,
            suggestions=[
                "Check your internet connection",
                "AI provider may be experiencing issues",
                "Try again in a few minutes"
            ]
        )

    # === Validation Errors ===

    @classmethod
    def invalid_date_range(cls, start: str, end: str) -> "LifeOSException":
        """Invalid date range provided."""
        return cls(
            status_code=400,
            error="invalid_date_range",
            message=f"Invalid date range: {start} to {end}",
            category=ErrorCategory.VALIDATION,
            suggestions=[
                "Use YYYY-MM-DD format for dates",
                "End date must be after start date",
                "Maximum range is 365 days"
            ],
            details={"start_date": start, "end_date": end}
        )

    @classmethod
    def invalid_energy_value(cls, value: Any) -> "LifeOSException":
        """Invalid energy value provided."""
        return cls(
            status_code=400,
            error="invalid_energy_value",
            message=f"Invalid energy value: {value}",
            category=ErrorCategory.VALIDATION,
            suggestions=[
                "Energy must be a number from 1 to 5",
                "1 = Very Low, 5 = Excellent"
            ],
            details={"provided_value": str(value)}
        )

    # === Not Found Errors ===

    @classmethod
    def no_data_for_date(cls, date: str) -> "LifeOSException":
        """No data available for the requested date."""
        return cls(
            status_code=404,
            error="no_data_for_date",
            message=f"No data available for {date}",
            category=ErrorCategory.NOT_FOUND,
            suggestions=[
                "Check if Oura has synced data for this date",
                "Try importing historical data via Settings > Data Import",
                "Data may take up to 24 hours to appear after a night's sleep"
            ],
            details={"date": date}
        )

    @classmethod
    def insight_not_found(cls, date: str, insight_type: str) -> "LifeOSException":
        """Requested insight not found."""
        return cls(
            status_code=404,
            error="insight_not_found",
            message=f"No {insight_type} found for {date}",
            category=ErrorCategory.NOT_FOUND,
            suggestions=[
                "Generate a new insight for this date",
                "Check if AI service is configured",
                f"Try: POST /api/insights/{insight_type}/generate"
            ],
            details={"date": date, "type": insight_type}
        )

    # === Internal Errors ===

    @classmethod
    def database_error(cls, operation: str) -> "LifeOSException":
        """Database operation failed."""
        return cls(
            status_code=500,
            error="database_error",
            message=f"Database error during {operation}",
            category=ErrorCategory.INTERNAL,
            suggestions=[
                "Try again in a moment",
                "Check if lifeos.db file exists and is writable",
                "Run ./setup.sh to reinitialize if needed"
            ]
        )

    @classmethod
    def internal_error(cls, message: str = "An unexpected error occurred") -> "LifeOSException":
        """Generic internal error."""
        return cls(
            status_code=500,
            error="internal_error",
            message=message,
            category=ErrorCategory.INTERNAL,
            suggestions=[
                "Try again in a moment",
                "Check the server logs for details",
                "Report this issue if it persists"
            ]
        )


# === Exception Handler for FastAPI ===

def format_error_response(exc: LifeOSException) -> Dict[str, Any]:
    """Format exception for JSON response."""
    return exc.helpful_error.model_dump()


# === Utility Functions ===

def get_fix_suggestions(error_type: str) -> List[str]:
    """
    Get fix suggestions for common error types.

    Used when catching generic exceptions.
    """
    suggestions_map = {
        "timeout": [
            "The request took too long to complete",
            "Try again in a few moments",
            "Check your internet connection"
        ],
        "connection_refused": [
            "Could not connect to the external service",
            "The service may be down or blocked",
            "Check your firewall settings"
        ],
        "json_decode": [
            "Received invalid response from service",
            "The API may have changed or be experiencing issues",
            "Try again later"
        ],
        "permission_denied": [
            "Insufficient permissions for this operation",
            "Check file/directory permissions",
            "Run with appropriate user privileges"
        ]
    }
    return suggestions_map.get(error_type, ["Try again later", "Check the logs for details"])
