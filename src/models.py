"""
LifeOS Data Models

SQLAlchemy models for all LifeOS data.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, Boolean, Index
from sqlalchemy.orm import relationship

from .database import Base


class User(Base):
    """User profile and preferences."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, default="User")
    timezone = Column(String(50), default="UTC")
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataPoint(Base):
    """
    Flexible storage for all metrics.

    Sources: oura, manual, calendar
    Types: sleep, activity, readiness, energy, mood
    """
    __tablename__ = "data_points"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    source = Column(String(50), nullable=False)  # oura, manual, calendar
    type = Column(String(50), nullable=False)    # sleep, activity, readiness, energy, mood
    date = Column(String(10), nullable=False)    # YYYY-MM-DD
    value = Column(Float)                        # Primary numeric value
    extra_data = Column("metadata", JSON, default=dict)  # Additional data (column name 'metadata' in DB)
    timestamp = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_datapoint_date_type', 'date', 'type'),
        Index('idx_datapoint_source', 'source'),
    )


class Insight(Base):
    """
    Generated insights and briefs.

    Types: daily_brief, weekly_review, pattern, prediction
    """
    __tablename__ = "insights"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    type = Column(String(50), nullable=False)    # daily_brief, weekly_review, pattern, prediction
    date = Column(String(10), nullable=False)    # YYYY-MM-DD
    content = Column(Text, nullable=False)       # The insight text
    context = Column(JSON, default=dict)         # Input data used to generate
    confidence = Column(Float, default=0.0)      # Confidence score 0-1
    acted_on = Column(Boolean, default=False)    # User marked as useful
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_insight_date_type', 'date', 'type'),
    )


class Pattern(Base):
    """
    Detected patterns from historical data.

    Stores correlations and trends.
    """
    __tablename__ = "patterns"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    name = Column(String(200), nullable=False)   # Pattern name/title
    description = Column(Text, nullable=False)   # Detailed description
    pattern_type = Column(String(50))            # correlation, trend, anomaly
    variables = Column(JSON, default=list)       # Variables involved
    strength = Column(Float)                     # Correlation strength -1 to 1
    sample_size = Column(Integer)                # Number of data points
    confidence = Column(Float, default=0.0)      # Statistical confidence
    actionable = Column(Boolean, default=True)   # Is this actionable?
    active = Column(Boolean, default=True)       # Still relevant?
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_validated = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_pattern_type', 'pattern_type'),
    )


class JournalEntry(Base):
    """Manual energy/mood logs."""
    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    date = Column(String(10), nullable=False)    # YYYY-MM-DD
    time = Column(String(5))                     # HH:MM
    energy = Column(Integer)                     # 1-5 scale
    mood = Column(Integer)                       # 1-5 scale
    notes = Column(Text)
    tags = Column(JSON, default=list)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_journal_date', 'date'),
    )


class Goal(Base):
    """
    Goal tracking with milestones and velocity-based progress.

    Goals are broken down into milestones by AI. Progress is calculated
    from milestone completion, and timeline adapts based on actual velocity.
    """
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    target_date = Column(String(10))              # YYYY-MM-DD
    status = Column(String(20), default="active") # active, completed, paused, abandoned
    progress = Column(Float, default=0.0)         # 0-100 (calculated from milestones)

    # Velocity tracking
    estimated_hours = Column(Float)               # AI-estimated total effort
    actual_hours = Column(Float, default=0.0)     # Logged hours worked
    velocity = Column(Float)                      # Calculated: milestones/week
    predicted_completion = Column(String(10))     # YYYY-MM-DD based on velocity

    # AI breakdown
    ai_breakdown = Column(JSON, default=dict)     # Raw AI response for reference
    breakdown_generated_at = Column(DateTime)     # When AI breakdown was created

    # Categorization
    category = Column(String(50))                 # health, career, learning, personal, etc.
    tags = Column(JSON, default=list)

    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_goal_status', 'status'),
        Index('idx_goal_category', 'category'),
    )


class Milestone(Base):
    """
    Goal milestones - actionable steps toward a goal.

    Created by AI breakdown or manually. Progress on milestones
    determines goal progress and informs velocity calculations.
    """
    __tablename__ = "milestones"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, nullable=False, index=True)
    user_id = Column(Integer, default=1)

    title = Column(String(300), nullable=False)
    description = Column(Text)
    order = Column(Integer, default=0)            # Sequence within goal

    # Status tracking
    status = Column(String(20), default="pending")  # pending, in_progress, completed, skipped
    completed_at = Column(DateTime)

    # Effort tracking
    estimated_hours = Column(Float)               # AI-estimated effort
    actual_hours = Column(Float, default=0.0)     # Logged hours

    # Deadline
    target_date = Column(String(10))              # YYYY-MM-DD

    # AI-generated or manual
    source = Column(String(20), default="ai")     # ai, manual

    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_milestone_goal', 'goal_id'),
        Index('idx_milestone_status', 'status'),
    )


class Task(Base):
    """Quick-captured tasks."""
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    title = Column(String(500), nullable=False)
    description = Column(Text)
    status = Column(String(20), default="pending")  # pending, in_progress, completed, archived
    priority = Column(String(20), default="normal")  # low, normal, high, urgent
    due_date = Column(String(10))  # YYYY-MM-DD
    tags = Column(JSON, default=list)
    source = Column(String(50), default="manual")  # manual, telegram, discord, voice
    raw_input = Column(Text)  # Original captured text
    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_task_status', 'status'),
        Index('idx_task_created', 'created_at'),
    )


class Note(Base):
    """Quick-captured notes."""
    __tablename__ = "notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    content = Column(Text, nullable=False)
    title = Column(String(200))  # AI-generated title
    tags = Column(JSON, default=list)
    source = Column(String(50), default="manual")  # manual, telegram, discord, voice
    raw_input = Column(Text)  # Original captured text
    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_note_created', 'created_at'),
    )


class OAuthToken(Base):
    """OAuth tokens for external integrations."""
    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    provider = Column(String(50), nullable=False)  # google, etc.
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text)
    token_type = Column(String(50), default="Bearer")
    expires_at = Column(DateTime)
    scope = Column(Text)  # Comma-separated scopes
    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_oauth_provider_user', 'provider', 'user_id'),
    )


class CalendarEvent(Base):
    """Calendar events from Google Calendar."""
    __tablename__ = "calendar_events"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    event_id = Column(String(200), nullable=False)  # Google event ID
    calendar_id = Column(String(200), nullable=False)  # Google calendar ID
    summary = Column(String(500))  # Event title
    description = Column(Text)
    location = Column(String(500))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    all_day = Column(Boolean, default=False)
    status = Column(String(50), default="confirmed")  # confirmed, tentative, cancelled
    organizer = Column(String(200))  # Organizer email
    attendees_count = Column(Integer, default=0)
    is_recurring = Column(Boolean, default=False)
    recurring_event_id = Column(String(200))  # Parent recurring event ID
    extra_data = Column("metadata", JSON, default=dict)
    synced_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_calendar_event_id', 'event_id'),
        Index('idx_calendar_start_time', 'start_time'),
        Index('idx_calendar_date', 'start_time', 'end_time'),
    )


class UserPreference(Base):
    """
    Learned user preferences for personalization.

    Stores both explicit preferences (user-set) and inferred
    preferences (learned from behavior patterns).

    Categories:
    - tone: preferred communication style (casual, professional, concise, detailed)
    - focus: areas user cares about (sleep_quality, energy, productivity, recovery)
    - schedule: timing preferences (morning_person, night_owl, peak_hours)
    - content: what to include/exclude in briefs
    """
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    category = Column(String(50), nullable=False)  # tone, focus, schedule, content
    key = Column(String(100), nullable=False)      # preference key within category
    value = Column(JSON, nullable=False)           # preference value (flexible)
    weight = Column(Float, default=0.5)            # confidence 0-1 (higher = more certain)
    source = Column(String(20), default="inferred")  # explicit, inferred, feedback
    evidence_count = Column(Integer, default=1)    # number of supporting observations
    last_reinforced = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_preference_user_category', 'user_id', 'category'),
        Index('idx_preference_key', 'key'),
    )


class InsightFeedback(Base):
    """
    Tracks user feedback on generated insights.

    Used to learn preferences and improve future insights.
    """
    __tablename__ = "insight_feedback"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    insight_id = Column(Integer, nullable=False)   # Reference to insights table
    feedback_type = Column(String(20), nullable=False)  # helpful, not_helpful, acted_on, dismissed
    context = Column(JSON, default=dict)           # Additional context (time to read, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index('idx_feedback_insight', 'insight_id'),
        Index('idx_feedback_type', 'feedback_type'),
    )


class VoiceNote(Base):
    """
    Voice notes with transcription.

    Stores uploaded audio files and their Whisper transcriptions.
    After transcription, the text is auto-categorized through CaptureService.
    """
    __tablename__ = "voice_notes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    filename = Column(String(255), nullable=False)     # Original filename
    file_path = Column(String(500), nullable=False)    # Storage path
    file_size = Column(Integer)                        # Size in bytes
    duration_seconds = Column(Float)                   # Audio duration
    mime_type = Column(String(100))                    # audio/mpeg, audio/wav, etc.

    # Transcription
    transcription = Column(Text)                       # Whisper transcription result
    transcription_status = Column(String(20), default="pending")  # pending, processing, completed, failed
    transcription_error = Column(Text)                 # Error message if failed
    transcription_language = Column(String(10))        # Detected language code

    # Auto-categorization result
    categorized_type = Column(String(20))              # note, task, energy
    categorized_id = Column(Integer)                   # ID of created note/task/entry
    categorization_status = Column(String(20), default="pending")  # pending, completed, skipped

    # Metadata
    source = Column(String(50), default="upload")      # upload, telegram, discord
    extra_data = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('idx_voice_note_status', 'transcription_status'),
        Index('idx_voice_note_created', 'created_at'),
    )
