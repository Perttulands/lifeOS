"""
LifeOS Goal Tracking Service

AI-powered goal breakdown with velocity-based progress tracking.

Goals are more than todo lists - they have milestones, track actual progress,
and adapt timelines based on your real velocity.
"""

import json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional, Dict, Any, List

from sqlalchemy.orm import Session

from ..ai import get_ai
from ..models import Goal, Milestone


@dataclass
class BreakdownResult:
    """Result from AI goal breakdown."""
    success: bool
    milestones: List[Dict[str, Any]]
    estimated_hours: float
    message: str


@dataclass
class VelocityMetrics:
    """Velocity tracking metrics for a goal."""
    milestones_per_week: Optional[float]
    hours_per_week: Optional[float]
    predicted_completion: Optional[str]
    on_track: bool
    weeks_remaining: Optional[float]


class GoalService:
    """
    Service for managing goals with AI-powered breakdown and velocity tracking.

    Features:
    - AI breaks down goals into actionable milestones
    - Progress calculated from milestone completion
    - Velocity tracking adapts predicted completion date
    """

    SYSTEM_PROMPT_BREAKDOWN = """You are LifeOS goal coach. Your job is to break down goals into achievable milestones.

Given a goal, create 3-8 specific, actionable milestones that build toward achieving it.

Good milestones are:
- Specific and measurable (you know when it's done)
- Sequential (later milestones build on earlier ones)
- Realistically sized (each ~1-8 hours of effort)
- Action-oriented (start with a verb)

For each milestone, estimate hours needed. Be realistic - most people overestimate what they can do.

Return as JSON only:
{
  "milestones": [
    {
      "title": "Set up development environment",
      "description": "Install necessary tools and configure project structure",
      "estimated_hours": 2,
      "order": 1
    },
    {
      "title": "Complete first prototype",
      "description": "Build minimal working version with core feature",
      "estimated_hours": 6,
      "order": 2
    }
  ],
  "total_estimated_hours": 8,
  "reasoning": "Brief explanation of the breakdown approach"
}

Examples:

Goal: "Learn to play guitar"
Milestones: Setup (get guitar, tuner) → Learn basic chords → Practice chord transitions → Learn first song → etc.

Goal: "Launch personal blog"
Milestones: Choose platform → Set up hosting → Design layout → Write first 3 posts → Share with friends → etc.

Goal: "Run a 5K"
Milestones: Get running shoes → Walk/run 1 mile → Run 2 miles continuously → Run 3 miles → Run 5K → etc.

Be encouraging but realistic. Better to have more achievable milestones than fewer overwhelming ones."""

    SYSTEM_PROMPT_REVIEW = """You are LifeOS goal coach reviewing progress on a goal.

Given goal details and milestone progress, provide a brief, encouraging progress assessment.

Consider:
- Milestones completed vs total
- Actual time vs estimated time
- Current velocity vs needed velocity
- Days remaining to target date

Respond with JSON only:
{
  "assessment": "1-2 sentence progress summary",
  "on_track": true/false,
  "suggestion": "One specific actionable suggestion"
}

Be honest but encouraging. Celebrate progress, acknowledge challenges, give practical advice."""

    def __init__(self, db: Session):
        self.db = db
        self.ai = get_ai()

    def create_goal(
        self,
        title: str,
        description: Optional[str] = None,
        target_date: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        auto_breakdown: bool = True
    ) -> Goal:
        """
        Create a new goal, optionally with AI-generated milestones.

        Args:
            title: Goal title
            description: Detailed description
            target_date: Target completion date (YYYY-MM-DD)
            category: Goal category (health, career, learning, etc.)
            tags: Optional tags
            auto_breakdown: Whether to auto-generate milestones

        Returns:
            Created Goal with milestones if auto_breakdown=True
        """
        goal = Goal(
            title=title,
            description=description,
            target_date=target_date,
            category=category,
            tags=tags or [],
            status="active",
            progress=0.0,
            actual_hours=0.0
        )
        self.db.add(goal)
        self.db.commit()
        self.db.refresh(goal)

        if auto_breakdown:
            self.generate_breakdown(goal.id)

        return goal

    def generate_breakdown(
        self,
        goal_id: int,
        force: bool = False
    ) -> BreakdownResult:
        """
        Generate AI-powered milestone breakdown for a goal.

        Args:
            goal_id: Goal ID to break down
            force: Regenerate even if milestones exist

        Returns:
            BreakdownResult with created milestones
        """
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return BreakdownResult(
                success=False,
                milestones=[],
                estimated_hours=0,
                message="Goal not found"
            )

        # Check for existing milestones
        existing = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).count()

        if existing > 0 and not force:
            return BreakdownResult(
                success=False,
                milestones=[],
                estimated_hours=0,
                message=f"Goal already has {existing} milestones. Use force=True to regenerate."
            )

        # Delete existing if forcing regeneration
        if force and existing > 0:
            self.db.query(Milestone).filter(Milestone.goal_id == goal_id).delete()
            self.db.commit()

        # Build prompt with goal context
        prompt_parts = [f"GOAL: {goal.title}"]
        if goal.description:
            prompt_parts.append(f"DESCRIPTION: {goal.description}")
        if goal.target_date:
            days_remaining = self._days_until(goal.target_date)
            prompt_parts.append(f"TARGET DATE: {goal.target_date} ({days_remaining} days from now)")
        if goal.category:
            prompt_parts.append(f"CATEGORY: {goal.category}")

        prompt_parts.append("\nBreak this goal into achievable milestones.")
        user_prompt = "\n".join(prompt_parts)

        try:
            response, tokens, _, _ = self.ai._call_llm(
                system_prompt=self.SYSTEM_PROMPT_BREAKDOWN,
                user_prompt=user_prompt,
                temperature=0.7,
                max_tokens=800,
                feature="goal_breakdown"
            )

            # Parse JSON response
            start = response.find('{')
            end = response.rfind('}') + 1
            if start < 0 or end <= start:
                raise ValueError("No JSON found in response")

            result = json.loads(response[start:end])
            milestones_data = result.get("milestones", [])
            total_hours = result.get("total_estimated_hours", 0)

            # Create milestones
            created_milestones = []
            for m_data in milestones_data:
                milestone = Milestone(
                    goal_id=goal.id,
                    title=m_data.get("title", "Untitled milestone"),
                    description=m_data.get("description"),
                    order=m_data.get("order", len(created_milestones) + 1),
                    estimated_hours=m_data.get("estimated_hours"),
                    source="ai",
                    status="pending"
                )
                self.db.add(milestone)
                created_milestones.append({
                    "title": milestone.title,
                    "description": milestone.description,
                    "order": milestone.order,
                    "estimated_hours": milestone.estimated_hours
                })

            # Update goal with AI breakdown data
            goal.estimated_hours = total_hours
            goal.ai_breakdown = result
            goal.breakdown_generated_at = datetime.utcnow()

            self.db.commit()

            return BreakdownResult(
                success=True,
                milestones=created_milestones,
                estimated_hours=total_hours,
                message=f"Created {len(created_milestones)} milestones"
            )

        except Exception as e:
            return BreakdownResult(
                success=False,
                milestones=[],
                estimated_hours=0,
                message=f"AI breakdown failed: {str(e)}"
            )

    def add_milestone(
        self,
        goal_id: int,
        title: str,
        description: Optional[str] = None,
        estimated_hours: Optional[float] = None,
        target_date: Optional[str] = None
    ) -> Optional[Milestone]:
        """Add a manual milestone to a goal."""
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return None

        # Get next order number
        max_order = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).count()

        milestone = Milestone(
            goal_id=goal_id,
            title=title,
            description=description,
            order=max_order + 1,
            estimated_hours=estimated_hours,
            target_date=target_date,
            source="manual",
            status="pending"
        )
        self.db.add(milestone)
        self.db.commit()
        self.db.refresh(milestone)

        # Update goal estimated hours if this milestone has an estimate
        if estimated_hours and goal.estimated_hours:
            goal.estimated_hours += estimated_hours
            self.db.commit()

        return milestone

    def update_milestone_status(
        self,
        milestone_id: int,
        status: str,
        actual_hours: Optional[float] = None
    ) -> Optional[Milestone]:
        """
        Update milestone status and recalculate goal progress.

        Args:
            milestone_id: Milestone to update
            status: New status (pending, in_progress, completed, skipped)
            actual_hours: Hours actually spent (for completed milestones)

        Returns:
            Updated Milestone or None if not found
        """
        milestone = self.db.query(Milestone).filter(
            Milestone.id == milestone_id
        ).first()
        if not milestone:
            return None

        old_status = milestone.status
        milestone.status = status

        if status == "completed":
            milestone.completed_at = datetime.utcnow()
            if actual_hours is not None:
                milestone.actual_hours = actual_hours

        self.db.commit()

        # Recalculate goal progress
        self._recalculate_progress(milestone.goal_id)

        return milestone

    def log_progress(
        self,
        goal_id: int,
        hours: float,
        notes: Optional[str] = None
    ) -> Optional[Goal]:
        """
        Log hours worked on a goal.

        Args:
            goal_id: Goal to log progress for
            hours: Hours worked
            notes: Optional notes about work done

        Returns:
            Updated Goal or None if not found
        """
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return None

        goal.actual_hours = (goal.actual_hours or 0) + hours
        self.db.commit()

        # Recalculate velocity
        self._recalculate_velocity(goal_id)

        return goal

    def _recalculate_progress(self, goal_id: int):
        """Recalculate goal progress based on milestone completion."""
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return

        milestones = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).all()

        if not milestones:
            return

        completed = sum(1 for m in milestones if m.status == "completed")
        total = len(milestones)

        goal.progress = (completed / total) * 100 if total > 0 else 0

        # Check if all milestones completed
        if completed == total and total > 0:
            goal.status = "completed"

        self.db.commit()

        # Also recalculate velocity
        self._recalculate_velocity(goal_id)

    def _recalculate_velocity(self, goal_id: int):
        """Recalculate velocity and predicted completion date."""
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return

        milestones = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).all()

        if not milestones:
            return

        completed_milestones = [m for m in milestones if m.status == "completed"]
        if not completed_milestones:
            return

        # Calculate velocity (milestones per week)
        first_milestone = min(completed_milestones, key=lambda m: m.completed_at or datetime.max)
        last_milestone = max(completed_milestones, key=lambda m: m.completed_at or datetime.min)

        if first_milestone.completed_at and last_milestone.completed_at:
            days_elapsed = (last_milestone.completed_at - first_milestone.completed_at).days
            if days_elapsed > 0:
                weeks_elapsed = days_elapsed / 7
                velocity = len(completed_milestones) / max(weeks_elapsed, 0.1)
                goal.velocity = round(velocity, 2)

                # Predict completion
                remaining = len([m for m in milestones if m.status not in ("completed", "skipped")])
                if velocity > 0 and remaining > 0:
                    weeks_needed = remaining / velocity
                    predicted = datetime.utcnow() + timedelta(weeks=weeks_needed)
                    goal.predicted_completion = predicted.strftime("%Y-%m-%d")

        self.db.commit()

    def get_velocity_metrics(self, goal_id: int) -> Optional[VelocityMetrics]:
        """Get velocity metrics for a goal."""
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return None

        milestones = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).all()

        completed = len([m for m in milestones if m.status == "completed"])
        total = len(milestones)
        remaining = total - completed

        # Calculate hours per week
        hours_per_week = None
        if goal.actual_hours and goal.created_at:
            weeks_since_start = (datetime.utcnow() - goal.created_at).days / 7
            if weeks_since_start > 0:
                hours_per_week = goal.actual_hours / weeks_since_start

        # Determine if on track
        on_track = True
        weeks_remaining = None
        if goal.target_date:
            days_remaining = self._days_until(goal.target_date)
            weeks_remaining = days_remaining / 7

            if goal.velocity and remaining > 0:
                weeks_needed = remaining / goal.velocity
                on_track = weeks_needed <= weeks_remaining

        return VelocityMetrics(
            milestones_per_week=goal.velocity,
            hours_per_week=round(hours_per_week, 1) if hours_per_week else None,
            predicted_completion=goal.predicted_completion,
            on_track=on_track,
            weeks_remaining=round(weeks_remaining, 1) if weeks_remaining else None
        )

    def _days_until(self, date_str: str) -> int:
        """Calculate days until a date string (YYYY-MM-DD)."""
        try:
            target = datetime.strptime(date_str, "%Y-%m-%d")
            return (target - datetime.utcnow()).days
        except ValueError:
            return 0

    def get_goal_with_milestones(self, goal_id: int) -> Optional[Dict[str, Any]]:
        """Get goal with all its milestones."""
        goal = self.db.query(Goal).filter(Goal.id == goal_id).first()
        if not goal:
            return None

        milestones = self.db.query(Milestone).filter(
            Milestone.goal_id == goal_id
        ).order_by(Milestone.order).all()

        return {
            "goal": goal,
            "milestones": milestones
        }

    def list_goals(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50
    ) -> List[Goal]:
        """List goals with optional filters."""
        query = self.db.query(Goal)

        if status:
            query = query.filter(Goal.status == status)
        if category:
            query = query.filter(Goal.category == category)

        return query.order_by(Goal.created_at.desc()).limit(limit).all()
