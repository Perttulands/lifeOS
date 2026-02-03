"""
Goal tracking endpoints with AI-powered breakdown and velocity tracking.
"""

from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Goal, Milestone
from ..integrations.goals import GoalService
from ..schemas import (
    GoalCreate,
    GoalUpdate,
    GoalResponse,
    GoalDetailResponse,
    GoalBreakdownRequest,
    GoalBreakdownResponse,
    MilestoneCreate,
    MilestoneUpdate,
    MilestoneResponse,
    LogProgressRequest,
    GoalProgressResponse,
)

router = APIRouter(prefix="/api/goals", tags=["goals"])


# === Goal CRUD ===

@router.post("", response_model=GoalResponse)
async def create_goal(
    request: GoalCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new goal.

    If auto_breakdown is True (default), AI will generate milestones automatically.
    """
    service = GoalService(db)
    goal = service.create_goal(
        title=request.title,
        description=request.description,
        target_date=request.target_date,
        category=request.category,
        tags=request.tags,
        auto_breakdown=request.auto_breakdown
    )

    return GoalResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        target_date=goal.target_date,
        status=goal.status,
        progress=goal.progress,
        estimated_hours=goal.estimated_hours,
        actual_hours=goal.actual_hours or 0,
        velocity=goal.velocity,
        predicted_completion=goal.predicted_completion,
        category=goal.category,
        tags=goal.tags or [],
        created_at=goal.created_at.isoformat(),
        updated_at=goal.updated_at.isoformat()
    )


@router.get("", response_model=List[GoalResponse])
async def list_goals(
    status: Optional[str] = Query(None, description="Filter by status: active, completed, paused, abandoned"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """List all goals with optional filters."""
    service = GoalService(db)
    goals = service.list_goals(status=status, category=category, limit=limit)

    return [
        GoalResponse(
            id=g.id,
            title=g.title,
            description=g.description,
            target_date=g.target_date,
            status=g.status,
            progress=g.progress,
            estimated_hours=g.estimated_hours,
            actual_hours=g.actual_hours or 0,
            velocity=g.velocity,
            predicted_completion=g.predicted_completion,
            category=g.category,
            tags=g.tags or [],
            created_at=g.created_at.isoformat(),
            updated_at=g.updated_at.isoformat()
        )
        for g in goals
    ]


@router.get("/{goal_id}", response_model=GoalDetailResponse)
async def get_goal(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """Get a goal with all its milestones."""
    service = GoalService(db)
    result = service.get_goal_with_milestones(goal_id)

    if not result:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal = result["goal"]
    milestones = result["milestones"]

    return GoalDetailResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        target_date=goal.target_date,
        status=goal.status,
        progress=goal.progress,
        estimated_hours=goal.estimated_hours,
        actual_hours=goal.actual_hours or 0,
        velocity=goal.velocity,
        predicted_completion=goal.predicted_completion,
        category=goal.category,
        tags=goal.tags or [],
        milestones=[
            MilestoneResponse(
                id=m.id,
                goal_id=m.goal_id,
                title=m.title,
                description=m.description,
                order=m.order,
                status=m.status,
                completed_at=m.completed_at.isoformat() if m.completed_at else None,
                estimated_hours=m.estimated_hours,
                actual_hours=m.actual_hours or 0,
                target_date=m.target_date,
                source=m.source,
                created_at=m.created_at.isoformat()
            )
            for m in milestones
        ],
        created_at=goal.created_at.isoformat(),
        updated_at=goal.updated_at.isoformat()
    )


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    request: GoalUpdate,
    db: Session = Depends(get_db)
):
    """Update a goal's details."""
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Update fields if provided
    if request.title is not None:
        goal.title = request.title
    if request.description is not None:
        goal.description = request.description
    if request.target_date is not None:
        goal.target_date = request.target_date
    if request.status is not None:
        goal.status = request.status
    if request.category is not None:
        goal.category = request.category
    if request.tags is not None:
        goal.tags = request.tags

    db.commit()
    db.refresh(goal)

    return GoalResponse(
        id=goal.id,
        title=goal.title,
        description=goal.description,
        target_date=goal.target_date,
        status=goal.status,
        progress=goal.progress,
        estimated_hours=goal.estimated_hours,
        actual_hours=goal.actual_hours or 0,
        velocity=goal.velocity,
        predicted_completion=goal.predicted_completion,
        category=goal.category,
        tags=goal.tags or [],
        created_at=goal.created_at.isoformat(),
        updated_at=goal.updated_at.isoformat()
    )


@router.delete("/{goal_id}")
async def delete_goal(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """Delete a goal and all its milestones."""
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Delete milestones first
    db.query(Milestone).filter(Milestone.goal_id == goal_id).delete()
    db.delete(goal)
    db.commit()

    return {"status": "ok", "message": f"Goal '{goal.title}' deleted"}


# === AI Breakdown ===

@router.post("/{goal_id}/breakdown", response_model=GoalBreakdownResponse)
async def generate_breakdown(
    goal_id: int,
    request: GoalBreakdownRequest = GoalBreakdownRequest(),
    db: Session = Depends(get_db)
):
    """
    Generate AI-powered milestone breakdown for a goal.

    Use regenerate=True to replace existing milestones with a fresh breakdown.
    """
    service = GoalService(db)
    result = service.generate_breakdown(goal_id, force=request.regenerate)

    if not result.success:
        raise HTTPException(status_code=400, detail=result.message)

    return GoalBreakdownResponse(
        goal_id=goal_id,
        milestones_created=len(result.milestones),
        estimated_total_hours=result.estimated_hours,
        message=result.message
    )


# === Progress Tracking ===

@router.post("/{goal_id}/progress", response_model=GoalProgressResponse)
async def log_progress(
    goal_id: int,
    request: LogProgressRequest,
    db: Session = Depends(get_db)
):
    """Log hours worked on a goal."""
    service = GoalService(db)
    goal = service.log_progress(goal_id, request.hours, request.notes)

    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    # Get milestone counts
    milestones = db.query(Milestone).filter(Milestone.goal_id == goal_id).all()
    completed = len([m for m in milestones if m.status == "completed"])

    return GoalProgressResponse(
        goal_id=goal.id,
        progress=goal.progress,
        actual_hours=goal.actual_hours or 0,
        velocity=goal.velocity,
        predicted_completion=goal.predicted_completion,
        milestones_completed=completed,
        milestones_total=len(milestones)
    )


@router.get("/{goal_id}/progress", response_model=GoalProgressResponse)
async def get_progress(
    goal_id: int,
    db: Session = Depends(get_db)
):
    """Get current progress and velocity metrics for a goal."""
    goal = db.query(Goal).filter(Goal.id == goal_id).first()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    milestones = db.query(Milestone).filter(Milestone.goal_id == goal_id).all()
    completed = len([m for m in milestones if m.status == "completed"])

    return GoalProgressResponse(
        goal_id=goal.id,
        progress=goal.progress,
        actual_hours=goal.actual_hours or 0,
        velocity=goal.velocity,
        predicted_completion=goal.predicted_completion,
        milestones_completed=completed,
        milestones_total=len(milestones)
    )


# === Milestone Management ===

@router.post("/{goal_id}/milestones", response_model=MilestoneResponse)
async def add_milestone(
    goal_id: int,
    request: MilestoneCreate,
    db: Session = Depends(get_db)
):
    """Add a manual milestone to a goal."""
    service = GoalService(db)
    milestone = service.add_milestone(
        goal_id=goal_id,
        title=request.title,
        description=request.description,
        estimated_hours=request.estimated_hours,
        target_date=request.target_date
    )

    if not milestone:
        raise HTTPException(status_code=404, detail="Goal not found")

    return MilestoneResponse(
        id=milestone.id,
        goal_id=milestone.goal_id,
        title=milestone.title,
        description=milestone.description,
        order=milestone.order,
        status=milestone.status,
        completed_at=milestone.completed_at.isoformat() if milestone.completed_at else None,
        estimated_hours=milestone.estimated_hours,
        actual_hours=milestone.actual_hours or 0,
        target_date=milestone.target_date,
        source=milestone.source,
        created_at=milestone.created_at.isoformat()
    )


@router.patch("/milestones/{milestone_id}", response_model=MilestoneResponse)
async def update_milestone(
    milestone_id: int,
    request: MilestoneUpdate,
    db: Session = Depends(get_db)
):
    """Update a milestone."""
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    service = GoalService(db)

    # Handle status change specially for progress recalculation
    if request.status is not None:
        milestone = service.update_milestone_status(
            milestone_id=milestone_id,
            status=request.status,
            actual_hours=request.actual_hours
        )
    else:
        # Update other fields
        if request.title is not None:
            milestone.title = request.title
        if request.description is not None:
            milestone.description = request.description
        if request.estimated_hours is not None:
            milestone.estimated_hours = request.estimated_hours
        if request.actual_hours is not None:
            milestone.actual_hours = request.actual_hours
        if request.target_date is not None:
            milestone.target_date = request.target_date
        db.commit()
        db.refresh(milestone)

    return MilestoneResponse(
        id=milestone.id,
        goal_id=milestone.goal_id,
        title=milestone.title,
        description=milestone.description,
        order=milestone.order,
        status=milestone.status,
        completed_at=milestone.completed_at.isoformat() if milestone.completed_at else None,
        estimated_hours=milestone.estimated_hours,
        actual_hours=milestone.actual_hours or 0,
        target_date=milestone.target_date,
        source=milestone.source,
        created_at=milestone.created_at.isoformat()
    )


@router.delete("/milestones/{milestone_id}")
async def delete_milestone(
    milestone_id: int,
    db: Session = Depends(get_db)
):
    """Delete a milestone."""
    milestone = db.query(Milestone).filter(Milestone.id == milestone_id).first()
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")

    goal_id = milestone.goal_id
    db.delete(milestone)
    db.commit()

    # Recalculate goal progress
    service = GoalService(db)
    service._recalculate_progress(goal_id)

    return {"status": "ok", "message": "Milestone deleted"}
