"""
LifeOS API Schemas

Pydantic models for API request/response validation.
"""

from typing import Optional, List, Dict
from pydantic import BaseModel


# === Health Schemas ===

class ServiceCheckResponse(BaseModel):
    name: str
    status: str
    message: str
    latency_ms: Optional[float] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class DetailedHealthResponse(BaseModel):
    status: str
    version: str
    uptime_seconds: float
    started_at: str
    timestamp: str
    services: Dict[str, ServiceCheckResponse]
    recent_errors: List[Dict]


# === Insight Schemas ===

class InsightResponse(BaseModel):
    id: int
    type: str
    date: str
    content: str
    confidence: float
    created_at: str

    class Config:
        from_attributes = True


class PatternResponse(BaseModel):
    id: int
    name: str
    description: str
    pattern_type: str
    variables: List[str]
    strength: float
    confidence: float
    sample_size: int
    actionable: bool

    class Config:
        from_attributes = True


class EnergyPrediction(BaseModel):
    overall: int
    peak_hours: List[str]
    low_hours: List[str]
    suggestion: str


class GenerateRequest(BaseModel):
    insight_type: str
    date: Optional[str] = None


# === Data Schemas ===

class DataPointResponse(BaseModel):
    id: int
    source: str
    type: str
    date: str
    value: Optional[float]
    metadata: dict

    class Config:
        from_attributes = True


# === Log/Capture Schemas ===

class LogEnergyRequest(BaseModel):
    energy: int  # 1-5
    mood: Optional[int] = None  # 1-5
    notes: Optional[str] = None


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
