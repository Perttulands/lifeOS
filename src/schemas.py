"""
LifeOS API Schemas

Pydantic models for API request/response validation.
Includes OpenAPI documentation via Field descriptions and examples.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# === Health Schemas ===

class ServiceCheckResponse(BaseModel):
    """Health check result for a single service."""
    name: str = Field(..., description="Service name", examples=["database"])
    status: str = Field(..., description="Status: healthy, degraded, unhealthy, unknown")
    message: str = Field(..., description="Human-readable status message")
    latency_ms: Optional[float] = Field(None, description="Response latency in milliseconds")


class HealthResponse(BaseModel):
    """Basic health check response."""
    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="API version", examples=["0.1.0"])
    timestamp: str = Field(..., description="ISO 8601 timestamp")


class DetailedHealthResponse(BaseModel):
    """Detailed health report with all service statuses."""
    status: str = Field(..., description="Overall system status")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="Server uptime in seconds")
    started_at: str = Field(..., description="Server start time (ISO 8601)")
    timestamp: str = Field(..., description="Report timestamp (ISO 8601)")
    services: Dict[str, ServiceCheckResponse] = Field(..., description="Individual service statuses")
    recent_errors: List[Dict[str, Any]] = Field(..., description="Recent error logs")


# === Insight Schemas ===

class InsightResponse(BaseModel):
    """AI-generated insight (brief, review, prediction)."""
    id: int = Field(..., description="Unique insight ID")
    type: str = Field(..., description="Insight type: daily_brief, weekly_review, energy_prediction, pattern")
    date: str = Field(..., description="Date for this insight (YYYY-MM-DD)")
    content: str = Field(..., description="The insight text content")
    confidence: float = Field(..., ge=0, le=1, description="AI confidence score (0-1)")
    created_at: str = Field(..., description="Creation timestamp (ISO 8601)")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 42,
                "type": "daily_brief",
                "date": "2026-02-03",
                "content": "Last night you got 7h 12m of sleep with 1h 45m deep sleep...",
                "confidence": 0.85,
                "created_at": "2026-02-03T07:00:00Z"
            }
        }


class PatternResponse(BaseModel):
    """Detected pattern from historical data analysis."""
    id: int = Field(..., description="Unique pattern ID")
    name: str = Field(..., description="Pattern name/title")
    description: str = Field(..., description="Detailed pattern description with evidence")
    pattern_type: str = Field(..., description="Type: correlation, trend, day_of_week, window_change")
    variables: List[str] = Field(..., description="Variables involved in the pattern")
    strength: float = Field(..., ge=-1, le=1, description="Pattern strength (-1 to 1)")
    confidence: float = Field(..., ge=0, le=1, description="Statistical confidence (0-1)")
    sample_size: int = Field(..., ge=0, description="Number of data points used")
    actionable: bool = Field(..., description="Whether this pattern is actionable")

    class Config:
        from_attributes = True


class EnergyPrediction(BaseModel):
    """Energy level prediction for a day."""
    overall: int = Field(..., ge=1, le=10, description="Predicted overall energy (1-10)")
    peak_hours: List[str] = Field(..., description="Expected high-energy time ranges")
    low_hours: List[str] = Field(..., description="Expected low-energy time ranges")
    suggestion: str = Field(..., description="Actionable suggestion for the day")

    class Config:
        json_schema_extra = {
            "example": {
                "overall": 7,
                "peak_hours": ["9:00-11:00", "15:00-16:00"],
                "low_hours": ["14:00-15:00"],
                "suggestion": "Your deep sleep was above average—capitalize on morning focus."
            }
        }


class GenerateRequest(BaseModel):
    """Request to generate an insight."""
    insight_type: str = Field(..., description="Type: daily_brief, weekly_review, energy_prediction")
    date: Optional[str] = Field(None, description="Date (YYYY-MM-DD), defaults to today")


# === Data Schemas ===

class DataPointResponse(BaseModel):
    """A single data point from any source."""
    id: int = Field(..., description="Unique data point ID")
    source: str = Field(..., description="Data source: oura, manual, calendar")
    type: str = Field(..., description="Data type: sleep, activity, readiness, energy, mood")
    date: str = Field(..., description="Date (YYYY-MM-DD)")
    value: Optional[float] = Field(None, description="Primary numeric value")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional data fields")

    class Config:
        from_attributes = True


# === Log/Capture Schemas ===

class LogEnergyRequest(BaseModel):
    """Request to log energy and mood levels."""
    energy: int = Field(..., ge=1, le=5, description="Energy level (1=Very Low, 5=Excellent)")
    mood: Optional[int] = Field(None, ge=1, le=5, description="Mood level (1-5)")
    notes: Optional[str] = Field(None, description="Optional notes about how you feel")


class CaptureRequest(BaseModel):
    text: str
    source: Optional[str] = "manual"


class WebhookPayload(BaseModel):
    text: str
    source: Optional[str] = "webhook"
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None


class CaptureResponse(BaseModel):
    type: str
    success: bool
    message: str
    data: dict


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[str]
    tags: List[str]
    source: str
    created_at: str

    class Config:
        from_attributes = True


class NoteResponse(BaseModel):
    id: int
    title: Optional[str]
    content: str
    tags: List[str]
    source: str
    created_at: str

    class Config:
        from_attributes = True


# === Oura Schemas ===

class OuraSyncRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class OuraSyncResultResponse(BaseModel):
    success: bool
    data_type: str
    records_synced: int
    date_range: List[str]
    errors: List[str]


class OuraSyncResponse(BaseModel):
    results: List[OuraSyncResultResponse]
    total_synced: int


# === Notification Schemas ===

class BriefDeliveryRequest(BaseModel):
    date: Optional[str] = None
    channels: Optional[List[str]] = None  # ["telegram", "discord"]
    regenerate: bool = False


class NotifyResultResponse(BaseModel):
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class BriefDeliveryResponse(BaseModel):
    brief_date: str
    brief_content: str
    notifications: List[NotifyResultResponse]
    all_successful: bool


class NotifyStatusResponse(BaseModel):
    telegram_enabled: bool
    discord_enabled: bool
    enabled_channels: List[str]


class WeeklyReviewDeliveryRequest(BaseModel):
    week_ending: Optional[str] = None
    channels: Optional[List[str]] = None  # ["telegram", "discord"]
    regenerate: bool = False


class PatternSummary(BaseModel):
    name: str
    description: str


class WeeklyReviewDeliveryResponse(BaseModel):
    week_ending: str
    review_content: str
    patterns: List[PatternSummary]
    avg_sleep_hours: Optional[float] = None
    avg_readiness: Optional[int] = None
    notifications: List[NotifyResultResponse]
    all_successful: bool


# === Settings Schemas ===

class NotificationSettings(BaseModel):
    telegram_enabled: bool = False
    discord_enabled: bool = False
    quiet_hours_enabled: bool = True
    quiet_hours_start: str = "23:00"
    quiet_hours_end: str = "08:00"


class IntegrationStatus(BaseModel):
    oura_configured: bool = False
    ai_configured: bool = False
    telegram_configured: bool = False
    discord_configured: bool = False


class SettingsResponse(BaseModel):
    user_name: str
    timezone: str
    notifications: NotificationSettings
    integrations: IntegrationStatus
    ai_model: str


class SettingsUpdateRequest(BaseModel):
    user_name: Optional[str] = None
    timezone: Optional[str] = None
    quiet_hours_enabled: Optional[bool] = None
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None


# === Backup Schemas ===

class BackupInfo(BaseModel):
    id: str
    filename: str
    timestamp: str
    size_mb: float


class BackupListResponse(BaseModel):
    backups: List[BackupInfo]
    backup_dir: str


class BackupResponse(BaseModel):
    success: bool
    message: str
    backup_id: Optional[str] = None


class RestoreRequest(BaseModel):
    backup_id: str


# === Calendar Schemas ===

class CalendarAuthUrlResponse(BaseModel):
    auth_url: str
    configured: bool


class CalendarEventResponse(BaseModel):
    id: int
    event_id: str
    summary: Optional[str]
    description: Optional[str]
    location: Optional[str]
    start_time: str
    end_time: str
    all_day: bool
    status: str
    organizer: Optional[str]
    attendees_count: int

    class Config:
        from_attributes = True


class CalendarSyncRequest(BaseModel):
    days_back: int = 7
    days_forward: int = 14
    calendar_id: str = "primary"


class CalendarSyncResultResponse(BaseModel):
    status: str
    events_synced: int
    events_updated: int
    events_deleted: int
    date_range: List[str]
    errors: List[str]


class CalendarStatusResponse(BaseModel):
    configured: bool
    connected: bool
    last_sync: Optional[str] = None
    calendars: List[Dict] = []


class MeetingStatsResponse(BaseModel):
    date: str
    meeting_count: int
    total_hours: float
    back_to_back_count: int
    early_meetings: int
    late_meetings: int
    events: List[Dict]


# === Token Cost/Stats Schemas ===

class FeatureCostSummary(BaseModel):
    feature: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    avg_tokens_per_call: float
    avg_cost_per_call: float


class CostReportResponse(BaseModel):
    period_start: str
    period_end: str
    total_calls: int
    total_tokens: int
    total_cost_usd: float
    by_feature: List[FeatureCostSummary]
    by_day: Dict[str, float]
    model_used: str


class TokenUsageResponse(BaseModel):
    feature: str
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: str


class StatsResponse(BaseModel):
    cost_report: CostReportResponse
    recent_usage: List[TokenUsageResponse]


# === Preference Schemas ===

class PreferenceResponse(BaseModel):
    id: int
    category: str
    key: str
    value: dict
    weight: float
    source: str
    evidence_count: int
    last_reinforced: str

    class Config:
        from_attributes = True


class PreferenceContextResponse(BaseModel):
    tone_style: str
    focus_areas: List[str]
    include_comparisons: bool
    include_predictions: bool
    preferred_insight_length: str
    active_patterns: List[str]


class SetPreferenceRequest(BaseModel):
    category: str
    key: str
    value: dict


class InsightFeedbackRequest(BaseModel):
    insight_id: int
    feedback_type: str  # helpful, not_helpful, acted_on, dismissed
    context: Optional[Dict] = None


class InsightFeedbackResponse(BaseModel):
    id: int
    insight_id: int
    feedback_type: str
    created_at: str

    class Config:
        from_attributes = True


# === Voice Note Schemas ===

class VoiceNoteResponse(BaseModel):
    id: int
    filename: str
    file_size: Optional[int]
    duration_seconds: Optional[float]
    mime_type: Optional[str]
    transcription: Optional[str]
    transcription_status: str
    transcription_language: Optional[str]
    categorized_type: Optional[str]
    categorized_id: Optional[int]
    source: str
    created_at: str

    class Config:
        from_attributes = True


class VoiceNoteUploadResponse(BaseModel):
    id: int
    filename: str
    transcription: Optional[str]
    transcription_status: str
    categorized_type: Optional[str]
    categorized_id: Optional[int]
    success: bool
    message: str


class VoiceNoteStatusResponse(BaseModel):
    whisper_configured: bool
    supported_formats: List[str]
    max_file_size_mb: int


# === Goal Tracking Schemas ===

class MilestoneCreate(BaseModel):
    title: str
    description: Optional[str] = None
    estimated_hours: Optional[float] = None
    target_date: Optional[str] = None


class MilestoneUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None  # pending, in_progress, completed, skipped
    estimated_hours: Optional[float] = None
    actual_hours: Optional[float] = None
    target_date: Optional[str] = None


class MilestoneResponse(BaseModel):
    id: int
    goal_id: int
    title: str
    description: Optional[str]
    order: int
    status: str
    completed_at: Optional[str]
    estimated_hours: Optional[float]
    actual_hours: float
    target_date: Optional[str]
    source: str
    created_at: str

    class Config:
        from_attributes = True


class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    auto_breakdown: bool = True  # Whether to auto-generate milestones with AI


class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[str] = None
    status: Optional[str] = None  # active, completed, paused, abandoned
    category: Optional[str] = None
    tags: Optional[List[str]] = None


class GoalResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    target_date: Optional[str]
    status: str
    progress: float
    estimated_hours: Optional[float]
    actual_hours: float
    velocity: Optional[float]
    predicted_completion: Optional[str]
    category: Optional[str]
    tags: List[str]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class GoalDetailResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    target_date: Optional[str]
    status: str
    progress: float
    estimated_hours: Optional[float]
    actual_hours: float
    velocity: Optional[float]
    predicted_completion: Optional[str]
    category: Optional[str]
    tags: List[str]
    milestones: List[MilestoneResponse]
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class GoalBreakdownRequest(BaseModel):
    regenerate: bool = False  # Force regenerate even if breakdown exists


class GoalBreakdownResponse(BaseModel):
    goal_id: int
    milestones_created: int
    estimated_total_hours: float
    message: str


class LogProgressRequest(BaseModel):
    hours: float
    notes: Optional[str] = None


class GoalProgressResponse(BaseModel):
    goal_id: int
    progress: float
    actual_hours: float
    velocity: Optional[float]
    predicted_completion: Optional[str]
    milestones_completed: int
    milestones_total: int
