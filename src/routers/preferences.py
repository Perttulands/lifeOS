"""
Preference management and personalization endpoints.
"""

from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import UserPreference, InsightFeedback
from ..personalization import PersonalizationService, get_personalization
from ..schemas import (
    PreferenceResponse,
    PreferenceContextResponse,
    SetPreferenceRequest,
    InsightFeedbackRequest,
    InsightFeedbackResponse,
)

router = APIRouter(prefix="/api/preferences", tags=["preferences"])


@router.get("/", response_model=Dict[str, Dict[str, Any]])
async def get_all_preferences(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get all user preferences organized by category.

    Returns preferences for: tone, focus, content, schedule
    """
    service = get_personalization(db)
    return service.get_all_preferences(user_id)


@router.get("/context", response_model=PreferenceContextResponse)
async def get_preference_context(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get the aggregated preference context used for AI personalization.

    This shows how the AI will interpret user preferences.
    """
    service = get_personalization(db)
    ctx = service.get_preference_context(user_id)

    return PreferenceContextResponse(
        tone_style=ctx.tone_style,
        focus_areas=ctx.focus_areas,
        include_comparisons=ctx.include_comparisons,
        include_predictions=ctx.include_predictions,
        preferred_insight_length=ctx.preferred_insight_length,
        active_patterns=ctx.active_patterns
    )


@router.get("/prompt")
async def get_personalization_prompt(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Get the personalization prompt that will be injected into AI calls.

    Useful for debugging and understanding how preferences affect AI behavior.
    """
    service = get_personalization(db)
    prompt = service.build_personalization_prompt(user_id)

    return {"prompt": prompt}


@router.get("/{category}/{key}")
async def get_preference(
    category: str,
    key: str,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """Get a specific preference value."""
    service = get_personalization(db)
    value = service.get_preference(category, key, user_id)

    if value is None:
        return {"value": None, "source": "default"}

    # Get full preference record
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == user_id,
        UserPreference.category == category,
        UserPreference.key == key
    ).first()

    if pref:
        return {
            "value": pref.value,
            "weight": pref.weight,
            "source": pref.source,
            "evidence_count": pref.evidence_count
        }

    return {"value": value, "source": "default"}


@router.put("/{category}/{key}", response_model=PreferenceResponse)
async def set_preference(
    category: str,
    key: str,
    value: Any,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Set a preference explicitly.

    Valid categories:
    - tone: style (casual, professional, concise, detailed)
    - focus: areas (list), show_comparisons (bool), show_predictions (bool)
    - content: insight_length (short, medium, long), include_numbers (bool)
    - schedule: is_morning_person (bool), peak_hours (list)
    """
    service = get_personalization(db)
    pref = service.set_preference(category, key, value, source="explicit", user_id=user_id)

    return PreferenceResponse(
        id=pref.id,
        category=pref.category,
        key=pref.key,
        value=pref.value,
        weight=pref.weight,
        source=pref.source,
        evidence_count=pref.evidence_count,
        last_reinforced=pref.last_reinforced.isoformat()
    )


@router.post("/feedback", response_model=InsightFeedbackResponse)
async def submit_insight_feedback(
    request: InsightFeedbackRequest,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Submit feedback on an insight.

    Feedback types:
    - helpful: The insight was useful
    - not_helpful: The insight was not useful
    - acted_on: User took action based on the insight
    - dismissed: User dismissed the insight

    This feedback is used to learn and improve future personalizations.
    """
    valid_types = ["helpful", "not_helpful", "acted_on", "dismissed"]
    if request.feedback_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid feedback type. Must be one of: {valid_types}"
        )

    service = get_personalization(db)
    feedback = service.record_feedback(
        insight_id=request.insight_id,
        feedback_type=request.feedback_type,
        context=request.context,
        user_id=user_id
    )

    return InsightFeedbackResponse(
        id=feedback.id,
        insight_id=feedback.insight_id,
        feedback_type=feedback.feedback_type,
        created_at=feedback.created_at.isoformat()
    )


@router.get("/feedback/history", response_model=List[InsightFeedbackResponse])
async def get_feedback_history(
    user_id: int = Query(1, description="User ID"),
    limit: int = Query(20, ge=1, le=100, description="Max records to return"),
    db: Session = Depends(get_db)
):
    """Get recent feedback history."""
    feedbacks = db.query(InsightFeedback).filter(
        InsightFeedback.user_id == user_id
    ).order_by(
        InsightFeedback.created_at.desc()
    ).limit(limit).all()

    return [
        InsightFeedbackResponse(
            id=f.id,
            insight_id=f.insight_id,
            feedback_type=f.feedback_type,
            created_at=f.created_at.isoformat()
        )
        for f in feedbacks
    ]


@router.post("/learn")
async def trigger_learning(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """
    Manually trigger preference learning from patterns and history.

    This is normally done automatically during brief generation,
    but can be triggered manually to update preferences.
    """
    service = get_personalization(db)
    service.learn_from_patterns(user_id)
    service.decay_preferences(user_id)

    return {"status": "ok", "message": "Learning completed"}


@router.delete("/{category}/{key}")
async def delete_preference(
    category: str,
    key: str,
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """Delete a specific preference, reverting to default."""
    pref = db.query(UserPreference).filter(
        UserPreference.user_id == user_id,
        UserPreference.category == category,
        UserPreference.key == key
    ).first()

    if not pref:
        raise HTTPException(status_code=404, detail="Preference not found")

    db.delete(pref)
    db.commit()

    return {"status": "ok", "message": f"Deleted {category}.{key}"}


@router.delete("/")
async def reset_all_preferences(
    user_id: int = Query(1, description="User ID"),
    db: Session = Depends(get_db)
):
    """Reset all preferences to defaults."""
    count = db.query(UserPreference).filter(
        UserPreference.user_id == user_id
    ).delete()
    db.commit()

    return {"status": "ok", "message": f"Deleted {count} preferences"}
