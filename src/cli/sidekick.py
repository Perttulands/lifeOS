"""
LifeOS Sidekick — gamified life coaching engine.

Tracks quests, XP, streaks, and adapts difficulty based on Oura readiness.
State persists to data/sidekick.json. No LLM calls — pure game logic.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict

STATE_FILE = Path(__file__).parent.parent.parent / "data" / "sidekick.json"

LEVELS = [
    (0, "Rookie Parent"),
    (100, "Sleepless Knight"),
    (300, "Chaos Absorber"),
    (600, "Flow State Finder"),
    (1000, "Life Optimizer"),
    (1500, "Baby Whisperer"),
    (2100, "Founder Dad"),
    (2800, "System Builder"),
    (3600, "Fully Operational"),
    (5000, "Legend"),
]

XP_VALUES = {
    "daily": (10, 25),
    "weekly": (50, 100),
    "epic": (250, 500),
    "streak_bonus": 5,       # per day in streak
    "oura_sleep_85": 10,
    "oura_readiness_90": 10,
    "oura_both": 25,
    "energy_log": 5,
    "brief_read": 5,
    "quest_chain_complete": 50,  # bonus for finishing all steps in an epic
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return datetime.now(timezone(timedelta(hours=2))).strftime("%Y-%m-%d")


def load_state() -> Dict[str, Any]:
    """Load sidekick state from disk."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return _default_state()


def save_state(state: Dict[str, Any]):
    """Save sidekick state to disk."""
    state["last_updated"] = _now()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def _default_state() -> Dict[str, Any]:
    return {
        "player": {
            "name": "Perttu",
            "xp": 0,
            "level": 1,
            "title": "Rookie Parent",
            "streaks": {"daily_quest": 0, "energy_log": 0, "brief_read": 0},
            "longest_streaks": {"daily_quest": 0, "energy_log": 0, "brief_read": 0},
        },
        "quests": {"daily": [], "weekly": [], "epic": []},
        "history": [],
        "completed_today": [],
        "last_updated": _now(),
    }


def get_level(xp: int) -> tuple:
    """Return (level_num, title, xp_for_next)."""
    for i in range(len(LEVELS) - 1, -1, -1):
        if xp >= LEVELS[i][0]:
            next_xp = LEVELS[i + 1][0] if i + 1 < len(LEVELS) else None
            return (i + 1, LEVELS[i][1], next_xp)
    return (1, LEVELS[0][1], LEVELS[1][0])


def award_xp(state: Dict, amount: int, reason: str) -> Dict:
    """Award XP and handle level ups. Returns state."""
    old_level = state["player"]["level"]
    state["player"]["xp"] += amount
    new_level, title, _ = get_level(state["player"]["xp"])
    state["player"]["level"] = new_level
    state["player"]["title"] = title
    state["history"].append({
        "date": _today(),
        "event": "xp_awarded",
        "xp": amount,
        "note": reason,
        "timestamp": _now(),
    })
    if new_level > old_level:
        state["history"].append({
            "date": _today(),
            "event": "level_up",
            "xp": 0,
            "note": f"Level {new_level}: {title}",
            "timestamp": _now(),
        })
    return state


def add_quest(state: Dict, title: str, quest_type: str = "daily",
              xp: int = None, tags: List[str] = None,
              parent_epic: str = None) -> Dict:
    """Add a quest. Returns (state, quest_id)."""
    if xp is None:
        lo, hi = XP_VALUES.get(quest_type, (10, 25))
        xp = lo  # conservative default
    quest = {
        "id": str(uuid.uuid4())[:8],
        "title": title,
        "type": quest_type,
        "xp": xp,
        "status": "active",
        "created": _now(),
        "completed": None,
        "parent_epic": parent_epic,
        "tags": tags or [],
    }
    state["quests"][quest_type].append(quest)
    return state, quest["id"]


def complete_quest(state: Dict, quest_id: str) -> Dict:
    """Complete a quest by ID. Awards XP."""
    for qtype in ["daily", "weekly", "epic"]:
        for quest in state["quests"][qtype]:
            if quest["id"] == quest_id and quest["status"] == "active":
                quest["status"] = "completed"
                quest["completed"] = _now()
                state = award_xp(state, quest["xp"], f"Completed: {quest['title']}")
                if "completed_today" not in state:
                    state["completed_today"] = []
                state["completed_today"].append(quest["id"])

                # Check if all children of parent epic are done
                if quest.get("parent_epic"):
                    _check_epic_chain(state, quest["parent_epic"])
                return state
    return state


def _check_epic_chain(state: Dict, epic_id: str):
    """Check if all sub-quests of an epic are complete."""
    children = []
    for qtype in ["daily", "weekly"]:
        for q in state["quests"][qtype]:
            if q.get("parent_epic") == epic_id:
                children.append(q)
    if children and all(c["status"] == "completed" for c in children):
        state = award_xp(state, XP_VALUES["quest_chain_complete"],
                        f"Quest chain complete!")


def expire_old_dailies(state: Dict) -> Dict:
    """Expire daily quests from previous days."""
    today = _today()
    for quest in state["quests"]["daily"]:
        if quest["status"] == "active":
            created_date = quest["created"][:10]
            if created_date < today:
                quest["status"] = "expired"
    state["completed_today"] = []
    return state


def update_streaks(state: Dict, completed_daily: bool, logged_energy: bool, read_brief: bool) -> Dict:
    """Update streak counters."""
    streaks = state["player"]["streaks"]
    longest = state["player"]["longest_streaks"]

    for key, did_it in [("daily_quest", completed_daily),
                         ("energy_log", logged_energy),
                         ("brief_read", read_brief)]:
        if did_it:
            streaks[key] += 1
            if streaks[key] > longest.get(key, 0):
                longest[key] = streaks[key]
            # Streak bonus
            if streaks[key] > 1:
                state = award_xp(state, XP_VALUES["streak_bonus"],
                                f"Streak bonus: {key} day {streaks[key]}")
        else:
            if streaks[key] > 0:
                state["history"].append({
                    "date": _today(),
                    "event": "streak_broken",
                    "xp": 0,
                    "note": f"{key} streak ended at {streaks[key]} days",
                    "timestamp": _now(),
                })
            streaks[key] = 0

    return state


def oura_bonus(state: Dict, sleep_score: float, readiness_score: float) -> Dict:
    """Award Oura-based bonuses."""
    sleep_good = sleep_score >= 85
    readiness_good = readiness_score >= 90

    if sleep_good and readiness_good:
        state = award_xp(state, XP_VALUES["oura_both"], f"Oura bonus: sleep {sleep_score} + readiness {readiness_score}")
    elif sleep_good:
        state = award_xp(state, XP_VALUES["oura_sleep_85"], f"Sleep bonus: {sleep_score}")
    elif readiness_good:
        state = award_xp(state, XP_VALUES["oura_readiness_90"], f"Readiness bonus: {readiness_score}")

    return state


def get_active_quests(state: Dict) -> Dict[str, List]:
    """Get all active quests by type."""
    result = {}
    for qtype in ["daily", "weekly", "epic"]:
        active = [q for q in state["quests"][qtype] if q["status"] == "active"]
        if active:
            result[qtype] = active
    return result


def get_quest_board(state: Dict) -> str:
    """Render the quest board as text."""
    player = state["player"]
    level, title, next_xp = get_level(player["xp"])

    lines = []
    lines.append(f"⚔️ **{player['name']}** — Lv.{level} {title}")

    # XP bar
    if next_xp:
        prev_xp = LEVELS[level - 1][0] if level > 0 else 0
        progress = (player["xp"] - prev_xp) / (next_xp - prev_xp)
        bar_len = 16
        filled = int(progress * bar_len)
        bar = "█" * filled + "░" * (bar_len - filled)
        lines.append(f"XP: {player['xp']}/{next_xp} {bar}")
    else:
        lines.append(f"XP: {player['xp']} — MAX LEVEL")

    # Streaks
    streak_parts = []
    for key, emoji in [("daily_quest", "⚔️"), ("energy_log", "🔋"), ("brief_read", "📜")]:
        val = player["streaks"].get(key, 0)
        if val > 0:
            streak_parts.append(f"{emoji}{val}")
    if streak_parts:
        lines.append(f"🔥 Streaks: {' '.join(streak_parts)}")

    # Active quests
    active = get_active_quests(state)
    if active:
        lines.append("")
        for qtype, quests in active.items():
            emoji = {"daily": "📋", "weekly": "📅", "epic": "🏔️"}.get(qtype, "•")
            lines.append(f"{emoji} **{qtype.title()} Quests:**")
            for q in quests[:5]:
                tags = f" [{', '.join(q['tags'])}]" if q.get("tags") else ""
                lines.append(f"  ☐ {q['title']} (+{q['xp']}xp){tags}")
    else:
        lines.append("\n*No active quests. Tell Hermes what you need to get done.*")

    return "\n".join(lines)


def adapt_quests_to_readiness(state: Dict, readiness: float) -> List[str]:
    """Suggest quest adjustments based on readiness. Returns suggestions."""
    suggestions = []
    active_dailies = [q for q in state["quests"]["daily"] if q["status"] == "active"]

    if readiness < 70:
        suggestions.append("Low readiness day. Consider deferring hard quests. Recovery IS a quest.")
        # Add a recovery quest if none exists
        recovery_exists = any("recovery" in q.get("tags", []) or "rest" in q["title"].lower()
                            for q in active_dailies)
        if not recovery_exists:
            state, _ = add_quest(state, "Recovery: 20min walk or nap", "daily",
                               xp=15, tags=["recovery", "health"])
            suggestions.append("Added a recovery quest. Your body asked for it.")

    elif readiness > 85:
        suggestions.append("High readiness. Push it today — tackle the hardest thing first.")

    return suggestions
