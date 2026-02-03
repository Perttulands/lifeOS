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
    metadata = Column(JSON, default=dict)        # Additional data
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
    """Goal tracking."""
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, default=1)
    title = Column(String(200), nullable=False)
    description = Column(Text)
    target_date = Column(String(10))
    status = Column(String(20), default="active")  # active, completed, paused, abandoned
    progress = Column(Float, default=0.0)          # 0-100
    metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
