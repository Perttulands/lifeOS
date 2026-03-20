"""LifeOS CLI — agent-first interface.

Commands output data. Hermes composes the insights.
No LLM calls in the CLI — the agent IS the intelligence.
"""
import sys
import click
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@click.group()
def cli():
    """LifeOS — your personal operating system."""
    pass


@cli.command()
@click.option("--date", default=None, help="Date (YYYY-MM-DD), default today")
@click.option("--days", default=7, help="Days of history to include")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="json")
def brief(date, days, fmt):
    """Gather context for a daily brief (sleep, readiness, trends, calendar).

    Outputs structured data for Hermes to compose into a brief.
    No LLM calls — the agent is the intelligence.
    """
    from .formatters import format_json, format_error

    try:
        from datetime import datetime, timedelta, timezone
        from ..database import SessionLocal, init_db
        from ..models import DataPoint, JournalEntry, CalendarEvent, Goal
        init_db()
        db = SessionLocal()
        try:
            target_date = date or datetime.now().strftime("%Y-%m-%d")

            # Today's data
            today_data = {}
            for dp in db.query(DataPoint).filter(DataPoint.date == target_date).all():
                today_data[dp.type] = {
                    "value": dp.value,
                    "source": dp.source,
                    **(dp.extra_data or {})
                }

            # History
            history = []
            for i in range(1, days + 1):
                d = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=i)).strftime("%Y-%m-%d")
                day_data = {"date": d}
                for dp in db.query(DataPoint).filter(DataPoint.date == d).all():
                    day_data[dp.type] = {
                        "value": dp.value,
                        **(dp.extra_data or {})
                    }
                if len(day_data) > 1:  # has data beyond just date
                    history.append(day_data)

            # Compute averages from history
            sleep_vals = [h["sleep"]["value"] for h in history if "sleep" in h and h["sleep"].get("value")]
            deep_vals = [h["sleep"].get("deep_sleep_hours", 0) for h in history if "sleep" in h]
            readiness_vals = [h["readiness"]["value"] for h in history if "readiness" in h and h["readiness"].get("value")]

            averages = {}
            if sleep_vals:
                averages["sleep_hours_avg"] = round(sum(sleep_vals) / len(sleep_vals), 1)
            if deep_vals:
                averages["deep_sleep_avg"] = round(sum(deep_vals) / len(deep_vals), 1)
            if readiness_vals:
                averages["readiness_avg"] = round(sum(readiness_vals) / len(readiness_vals))

            # Recent energy logs
            recent_energy = db.query(JournalEntry).filter(
                JournalEntry.date >= (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=days)).strftime("%Y-%m-%d"),
                JournalEntry.energy.isnot(None)
            ).order_by(JournalEntry.date.desc()).limit(7).all()

            energy_logs = [{"date": e.date, "energy": e.energy, "notes": e.notes} for e in recent_energy]

            # Today's calendar
            cal_start = datetime.strptime(target_date, "%Y-%m-%d")
            cal_end = cal_start + timedelta(days=1)
            events = db.query(CalendarEvent).filter(
                CalendarEvent.start_time >= cal_start,
                CalendarEvent.start_time < cal_end,
                CalendarEvent.status != "cancelled"
            ).order_by(CalendarEvent.start_time).all()

            calendar = [{
                "summary": e.summary,
                "start": e.start_time.strftime("%H:%M") if e.start_time else None,
                "end": e.end_time.strftime("%H:%M") if e.end_time else None,
                "attendees": e.attendees_count
            } for e in events if not e.all_day]

            # Day of week
            day_name = datetime.strptime(target_date, "%Y-%m-%d").strftime("%A")

            # Active goals
            active_goals = db.query(Goal).filter(Goal.status == "active").all()
            goals_data = []
            for g in active_goals:
                days_rem = None
                if g.target_date:
                    try:
                        t = datetime.strptime(g.target_date, "%Y-%m-%d")
                        days_rem = (t - datetime.strptime(target_date, "%Y-%m-%d")).days
                    except ValueError:
                        pass
                # Determine flag
                flag = "on_track"
                if g.predicted_completion and g.target_date:
                    if g.predicted_completion > g.target_date:
                        flag = "behind"
                goals_data.append({
                    "id": g.id,
                    "title": g.title,
                    "progress": g.progress or 0,
                    "status": flag,
                    "days_remaining": days_rem,
                })

            result = {
                "date": target_date,
                "day": day_name,
                "today": today_data,
                "averages": averages,
                "history_days": len(history),
                "energy_logs": energy_logs,
                "calendar": calendar,
                "goals": goals_data,
            }

            if fmt == "json":
                click.echo(format_json(result))
            else:
                # Text summary for quick reading
                sleep = today_data.get("sleep", {})
                readiness = today_data.get("readiness", {})
                lines = [f"📅 {day_name} {target_date}"]
                if sleep.get("value"):
                    avg = averages.get("sleep_hours_avg", "?")
                    score_str = f" (score: {sleep['score']}/100)" if sleep.get("score") else ""
                    lines.append(f"💤 Sleep: {sleep['value']:.1f}h{score_str} (avg: {avg}h)")
                    if sleep.get("deep_sleep_hours"):
                        lines.append(f"   Deep: {sleep['deep_sleep_hours']:.1f}h | REM: {sleep.get('rem_sleep_hours', 0):.1f}h | Light: {sleep.get('light_sleep_hours', 0):.1f}h")
                    if sleep.get("hrv_average"):
                        lines.append(f"   HRV: {sleep['hrv_average']} avg | Resting HR: {sleep.get('hr_lowest', '?')}")
                if readiness.get("value"):
                    lines.append(f"⚡ Readiness: {int(readiness['value'])}/100")
                if calendar:
                    lines.append(f"📅 {len(calendar)} meetings today")
                if energy_logs:
                    latest = energy_logs[0]
                    lines.append(f"🔋 Last energy log: {latest['energy']}/5")
                click.echo("\n".join(lines))
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def status(fmt):
    """Quick status snapshot — last sleep, readiness, trends."""
    from .formatters import format_json, format_error

    try:
        from datetime import datetime, timedelta
        from ..database import SessionLocal, init_db
        from ..models import DataPoint, Goal, JournalEntry
        init_db()
        db = SessionLocal()
        try:
            today = datetime.now().strftime("%Y-%m-%d")

            # Latest sleep
            latest_sleep = db.query(DataPoint).filter(
                DataPoint.type == "sleep"
            ).order_by(DataPoint.date.desc()).first()

            # Latest readiness
            latest_readiness = db.query(DataPoint).filter(
                DataPoint.type == "readiness"
            ).order_by(DataPoint.date.desc()).first()

            # Active goals
            active_goals = db.query(Goal).filter(Goal.status == "active").count()

            # Recent energy
            recent_energy = db.query(JournalEntry).filter(
                JournalEntry.energy.isnot(None)
            ).order_by(JournalEntry.date.desc()).first()

            sleep_meta = (latest_sleep.extra_data or {}) if latest_sleep else {}
            result = {
                "date": today,
                "last_sleep": {
                    "date": latest_sleep.date if latest_sleep else None,
                    "hours": latest_sleep.value if latest_sleep else None,
                    "score": sleep_meta.get("score"),
                    "deep_sleep_hours": sleep_meta.get("deep_sleep_hours"),
                    "rem_sleep_hours": sleep_meta.get("rem_sleep_hours"),
                    "hrv_average": sleep_meta.get("hrv_average"),
                    "hr_lowest": sleep_meta.get("hr_lowest"),
                } if latest_sleep else None,
                "last_readiness": {
                    "date": latest_readiness.date if latest_readiness else None,
                    "score": int(latest_readiness.value) if latest_readiness else None,
                } if latest_readiness else None,
                "active_goals": active_goals,
                "last_energy": {
                    "date": recent_energy.date if recent_energy else None,
                    "level": recent_energy.energy if recent_energy else None,
                } if recent_energy else None,
            }

            if fmt == "json":
                click.echo(format_json(result))
            else:
                lines = [f"LifeOS Status — {today}"]
                if result["last_sleep"]:
                    s = result["last_sleep"]
                    score_str = f" (score: {s['score']})" if s.get("score") else ""
                    lines.append(f"💤 Last sleep: {s['hours']:.1f}h{score_str} on {s['date']}")
                    details = []
                    if s.get("deep_sleep_hours"):
                        details.append(f"Deep: {s['deep_sleep_hours']:.1f}h")
                    if s.get("rem_sleep_hours"):
                        details.append(f"REM: {s['rem_sleep_hours']:.1f}h")
                    if s.get("hrv_average"):
                        details.append(f"HRV: {s['hrv_average']}")
                    if details:
                        lines.append(f"   {' | '.join(details)}")
                if result["last_readiness"]:
                    r = result["last_readiness"]
                    lines.append(f"⚡ Readiness: {r['score']}/100 on {r['date']}")
                lines.append(f"🎯 Active goals: {active_goals}")
                if result["last_energy"]:
                    e = result["last_energy"]
                    lines.append(f"🔋 Last energy: {e['level']}/5 on {e['date']}")
                click.echo("\n".join(lines))
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.argument("source", type=click.Choice(["oura", "calendar", "all"]), default="all")
@click.option("--days", default=1, help="Days to sync (default: 1)")
def sync(source, days):
    """Sync data from external sources."""
    from .formatters import format_error

    try:
        from datetime import datetime, timedelta
        from ..database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        total = 0
        try:
            if source in ("oura", "all"):
                from ..integrations.oura import OuraSyncService
                today = datetime.now().strftime("%Y-%m-%d")
                start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
                result = OuraSyncService(db).sync_all(start_date=start, end_date=today)
                count = sum(r.records_synced for r in result if r.success)
                total += count
                click.echo(f"Oura: synced {count} records")

            if source in ("calendar", "all"):
                from ..integrations.calendar import CalendarSyncService
                result = CalendarSyncService(db).sync()
                count = result.events_synced if hasattr(result, 'events_synced') else 0
                total += count
                click.echo(f"Calendar: synced {count} records")

            click.echo(f"Total: synced {total} records")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.group()
def quest():
    """Manage quests and XP."""
    pass


@quest.command("board")
def quest_board():
    """Show the quest board."""
    from .sidekick import load_state, get_quest_board
    state = load_state()
    click.echo(get_quest_board(state))


@quest.command("add")
@click.argument("title")
@click.option("--type", "qtype", type=click.Choice(["daily", "weekly", "epic"]), default="daily")
@click.option("--xp", type=int, default=None)
@click.option("--tag", multiple=True)
@click.option("--epic", "parent_epic", default=None, help="Parent epic quest ID")
def quest_add(title, qtype, xp, tag, parent_epic):
    """Add a quest."""
    from .sidekick import load_state, save_state, add_quest
    state = load_state()
    state, qid = add_quest(state, title, qtype, xp=xp, tags=list(tag), parent_epic=parent_epic)
    save_state(state)
    click.echo(f"Quest added: {qid} — {title} (+{xp or '?'}xp)")


@quest.command("done")
@click.argument("quest_id")
def quest_done(quest_id):
    """Complete a quest."""
    from .sidekick import load_state, save_state, complete_quest, get_level
    state = load_state()
    old_xp = state["player"]["xp"]
    state = complete_quest(state, quest_id)
    new_xp = state["player"]["xp"]
    save_state(state)
    gained = new_xp - old_xp
    level, title, _ = get_level(new_xp)
    click.echo(f"✅ Quest complete! +{gained}xp → {new_xp}xp (Lv.{level} {title})")


@quest.command("list")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def quest_list(fmt):
    """List active quests."""
    from .sidekick import load_state, get_active_quests
    from .formatters import format_json
    state = load_state()
    active = get_active_quests(state)
    if fmt == "json":
        click.echo(format_json({"player": state["player"], "active_quests": active}))
    else:
        if not active:
            click.echo("No active quests.")
            return
        for qtype, quests in active.items():
            click.echo(f"\n{qtype.upper()}:")
            for q in quests:
                click.echo(f"  [{q['id']}] {q['title']} (+{q['xp']}xp)")


@quest.command("state")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="json")
def quest_state(fmt):
    """Full sidekick state dump."""
    from .sidekick import load_state
    from .formatters import format_json
    state = load_state()
    if fmt == "json":
        click.echo(format_json(state))
    else:
        p = state["player"]
        click.echo(f"{p['name']} — Lv.{p['level']} {p['title']} ({p['xp']}xp)")
        click.echo(f"Streaks: {p['streaks']}")
        click.echo(f"History: {len(state['history'])} events")


@cli.group()
def goal():
    """Track and review goals."""
    pass


@goal.command("list")
@click.option("--status", type=click.Choice(["active", "all"]), default="active")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def goal_list(status, fmt):
    """List goals."""
    from .formatters import format_json, format_error

    try:
        from ..database import SessionLocal, init_db
        from ..models import Goal
        init_db()
        db = SessionLocal()
        try:
            query = db.query(Goal)
            if status == "active":
                query = query.filter(Goal.status == "active")
            goals = query.order_by(Goal.created_at.desc()).all()

            goals_data = [{
                "id": g.id,
                "title": g.title,
                "progress": g.progress or 0,
                "status": g.status,
                "category": g.category,
                "target_date": g.target_date,
            } for g in goals]

            if fmt == "json":
                click.echo(format_json({"goals": goals_data}))
            else:
                if not goals_data:
                    click.echo("No goals found.")
                    return
                for g in goals_data:
                    pct = int(g["progress"])
                    target = f" -> {g['target_date']}" if g["target_date"] else ""
                    click.echo(f"  [{g['id']}] {g['title']} ({pct}%){target}")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@goal.command("add")
@click.argument("title")
@click.option("--target-date", default=None, help="Target date YYYY-MM-DD")
@click.option("--description", default=None)
@click.option("--category", default=None)
def goal_add(title, target_date, description, category):
    """Add a new goal (creates an epic quest too)."""
    from .formatters import format_error
    from .sidekick import load_state, save_state, add_quest

    try:
        from ..database import SessionLocal, init_db
        from ..models import Goal
        init_db()
        db = SessionLocal()
        try:
            g = Goal(
                title=title,
                description=description,
                target_date=target_date,
                category=category,
                status="active",
                progress=0.0,
                actual_hours=0.0,
                tags=[],
            )
            db.add(g)
            db.commit()
            db.refresh(g)

            # Create epic quest in sidekick
            state = load_state()
            state, quest_id = add_quest(
                state, f"Goal: {title}", "epic",
                xp=300, tags=[category or "goal"],
            )
            # Store quest_id on the goal for later completion
            g.extra_data = {"quest_id": quest_id}
            db.commit()
            save_state(state)

            click.echo(f"Goal created: [{g.id}] {title}")
            click.echo(f"Epic quest: {quest_id} (+300xp on completion)")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@goal.command("update")
@click.argument("goal_id", type=int)
@click.option("--progress", type=int, default=None, help="Progress 0-100")
@click.option("--status", "new_status", type=click.Choice(["active", "completed", "paused"]), default=None)
@click.option("--note", default=None)
def goal_update(goal_id, progress, new_status, note):
    """Update goal progress or status."""
    from .formatters import format_error
    from .sidekick import load_state, save_state, complete_quest

    try:
        from datetime import datetime, timezone
        from ..database import SessionLocal, init_db
        from ..models import Goal
        init_db()
        db = SessionLocal()
        try:
            g = db.query(Goal).filter(Goal.id == goal_id).first()
            if not g:
                click.echo(f"Goal {goal_id} not found.", err=True)
                sys.exit(1)

            if progress is not None:
                g.progress = float(progress)
            if new_status is not None:
                g.status = new_status
            if note:
                meta = g.extra_data or {}
                notes = meta.get("notes", [])
                notes.append({"text": note, "at": datetime.now(timezone.utc).isoformat()})
                meta["notes"] = notes
                g.extra_data = meta

            # Auto-complete if progress hits 100 or status set to completed
            completed = (progress is not None and progress >= 100) or new_status == "completed"
            if completed:
                g.status = "completed"
                g.progress = 100.0
                # Complete the linked epic quest
                quest_id = (g.extra_data or {}).get("quest_id")
                if quest_id:
                    state = load_state()
                    state = complete_quest(state, quest_id)
                    save_state(state)
                    click.echo("Epic quest completed! XP awarded.")

            db.commit()
            click.echo(f"Goal [{g.id}] updated: {g.title} ({int(g.progress)}%, {g.status})")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@goal.command("show")
@click.argument("goal_id", type=int)
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def goal_show(goal_id, fmt):
    """Show goal details."""
    from .formatters import format_json, format_error

    try:
        from ..database import SessionLocal, init_db
        from ..models import Goal, Milestone
        init_db()
        db = SessionLocal()
        try:
            g = db.query(Goal).filter(Goal.id == goal_id).first()
            if not g:
                click.echo(f"Goal {goal_id} not found.", err=True)
                sys.exit(1)

            milestones = db.query(Milestone).filter(
                Milestone.goal_id == goal_id
            ).order_by(Milestone.order).all()

            data = {
                "id": g.id,
                "title": g.title,
                "description": g.description,
                "progress": g.progress or 0,
                "status": g.status,
                "category": g.category,
                "target_date": g.target_date,
                "velocity": g.velocity,
                "predicted_completion": g.predicted_completion,
                "created_at": str(g.created_at),
                "milestones": [{
                    "id": m.id,
                    "title": m.title,
                    "status": m.status,
                    "order": m.order,
                } for m in milestones],
            }

            if fmt == "json":
                click.echo(format_json(data))
            else:
                click.echo(f"[{g.id}] {g.title}")
                click.echo(f"  Status: {g.status} | Progress: {int(g.progress or 0)}%")
                if g.target_date:
                    click.echo(f"  Target: {g.target_date}")
                if g.category:
                    click.echo(f"  Category: {g.category}")
                if g.description:
                    click.echo(f"  {g.description}")
                if milestones:
                    click.echo("  Milestones:")
                    for m in milestones:
                        mark = "x" if m.status == "completed" else " "
                        click.echo(f"    [{mark}] {m.title}")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@goal.command("review")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def goal_review(fmt):
    """Review active goals — velocity, predictions, status flags. No LLM."""
    from .formatters import format_json, format_error

    try:
        from datetime import datetime, timedelta, timezone
        from ..database import SessionLocal, init_db
        from ..models import Goal
        init_db()
        db = SessionLocal()
        try:
            goals = db.query(Goal).filter(Goal.status == "active").order_by(Goal.created_at).all()

            if not goals:
                click.echo("No active goals.")
                return

            now = datetime.now(timezone.utc)
            reviews = []

            for g in goals:
                progress = g.progress or 0.0
                created = g.created_at
                if created and created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)

                # Weeks elapsed since creation
                weeks_elapsed = (now - created).days / 7 if created else 0
                velocity_pct = progress / max(weeks_elapsed, 0.1)  # %/week

                # Days remaining
                days_remaining = None
                if g.target_date:
                    try:
                        target = datetime.strptime(g.target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        days_remaining = (target - now).days
                    except ValueError:
                        pass

                # Predicted completion
                predicted = None
                if velocity_pct > 0 and progress < 100:
                    weeks_to_go = (100 - progress) / velocity_pct
                    predicted_date = now + timedelta(weeks=weeks_to_go)
                    predicted = predicted_date.strftime("%Y-%m-%d")

                # Status flag
                flag = "on_track"
                if days_remaining is not None and predicted:
                    try:
                        pred_dt = datetime.strptime(predicted, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        target_dt = datetime.strptime(g.target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                        if pred_dt > target_dt:
                            flag = "behind"
                    except ValueError:
                        pass
                elif velocity_pct == 0 and progress == 0:
                    flag = "not_started"

                # Last update
                updated = g.updated_at
                if updated and updated.tzinfo is None:
                    updated = updated.replace(tzinfo=timezone.utc)
                days_since_update = (now - updated).days if updated else None

                review = {
                    "id": g.id,
                    "title": g.title,
                    "progress": round(progress, 1),
                    "target_date": g.target_date,
                    "days_remaining": days_remaining,
                    "velocity_pct_per_week": round(velocity_pct, 1),
                    "predicted_completion": predicted,
                    "flag": flag,
                    "days_since_update": days_since_update,
                }
                reviews.append(review)

            if fmt == "json":
                click.echo(format_json({"reviews": reviews}))
            else:
                for r in reviews:
                    target_str = f" -> target {r['target_date']}" if r["target_date"] else ""
                    click.echo(f"\n  [{r['id']}] {r['title']} ({r['progress']}%{target_str})")
                    click.echo(f"    Velocity: {r['velocity_pct_per_week']}%/week", nl=False)
                    if r["predicted_completion"]:
                        flag_icon = {"on_track": "OK", "behind": "BEHIND", "not_started": "NEW"}.get(r["flag"], "?")
                        click.echo(f" -> predicted {r['predicted_completion']} [{flag_icon}]")
                    else:
                        click.echo(" -> no prediction yet")
                    if r["days_since_update"] and r["days_since_update"] > 7:
                        click.echo(f"    Last update: {r['days_since_update']} days ago — stalled?")
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def weekly(fmt):
    """Weekly review — data-driven summary of the past 7 days. No LLM."""
    from .formatters import format_json, format_error
    from .sidekick import load_state, save_state, check_achievements, get_level

    try:
        from datetime import datetime, timedelta, timezone as tz
        from ..database import SessionLocal, init_db
        from ..models import DataPoint, JournalEntry
        init_db()
        db = SessionLocal()
        try:
            today = datetime.now(tz.utc).strftime("%Y-%m-%d")
            week_start = (datetime.now(tz.utc) - timedelta(days=7)).strftime("%Y-%m-%d")

            # --- Sleep ---
            sleep_rows = db.query(DataPoint).filter(
                DataPoint.type == "sleep",
                DataPoint.date >= week_start,
                DataPoint.date <= today,
            ).all()
            sleep_scores = []
            for dp in sleep_rows:
                score = (dp.extra_data or {}).get("score")
                if score is not None:
                    sleep_scores.append({"date": dp.date, "score": score})
            sleep_scores.sort(key=lambda x: x["score"])
            sleep_avg = round(sum(s["score"] for s in sleep_scores) / len(sleep_scores)) if sleep_scores else None
            sleep_best = sleep_scores[-1] if sleep_scores else None
            sleep_worst = sleep_scores[0] if sleep_scores else None
            sleep_trend = None
            if len(sleep_scores) >= 4:
                first_half = sum(s["score"] for s in sleep_scores[:len(sleep_scores)//2]) / (len(sleep_scores)//2)
                second_half = sum(s["score"] for s in sleep_scores[len(sleep_scores)//2:]) / (len(sleep_scores) - len(sleep_scores)//2)
                sleep_trend = "improving" if second_half > first_half + 2 else ("declining" if first_half > second_half + 2 else "stable")

            # --- Readiness ---
            readiness_rows = db.query(DataPoint).filter(
                DataPoint.type == "readiness",
                DataPoint.date >= week_start,
                DataPoint.date <= today,
            ).all()
            readiness_scores = [{"date": dp.date, "score": int(dp.value)} for dp in readiness_rows if dp.value]
            readiness_scores.sort(key=lambda x: x["score"])
            readiness_avg = round(sum(r["score"] for r in readiness_scores) / len(readiness_scores)) if readiness_scores else None
            readiness_best = readiness_scores[-1] if readiness_scores else None
            readiness_worst = readiness_scores[0] if readiness_scores else None
            readiness_trend = None
            if len(readiness_scores) >= 4:
                first_half = sum(r["score"] for r in readiness_scores[:len(readiness_scores)//2]) / (len(readiness_scores)//2)
                second_half = sum(r["score"] for r in readiness_scores[len(readiness_scores)//2:]) / (len(readiness_scores) - len(readiness_scores)//2)
                readiness_trend = "improving" if second_half > first_half + 2 else ("declining" if first_half > second_half + 2 else "stable")

            # --- Energy ---
            energy_rows = db.query(JournalEntry).filter(
                JournalEntry.date >= week_start,
                JournalEntry.date <= today,
                JournalEntry.energy.isnot(None),
            ).all()
            energy_entries = [{"date": e.date, "energy": e.energy} for e in energy_rows]
            energy_entries.sort(key=lambda x: x["energy"])
            energy_avg = round(sum(e["energy"] for e in energy_entries) / len(energy_entries), 1) if energy_entries else None
            energy_best = energy_entries[-1] if energy_entries else None
            energy_worst = energy_entries[0] if energy_entries else None

            # --- Quest summary ---
            state = load_state()
            completed_this_week = []
            xp_this_week = 0
            for qtype in ["daily", "weekly", "epic"]:
                for q in state["quests"][qtype]:
                    if q["status"] == "completed" and q.get("completed"):
                        comp_date = q["completed"][:10]
                        if comp_date >= week_start:
                            completed_this_week.append(q)
            for h in state["history"]:
                if h.get("date", "") >= week_start and h["event"] == "xp_awarded":
                    xp_this_week += h.get("xp", 0)
            level, title, next_xp = get_level(state["player"]["xp"])
            progress_to_next = None
            if next_xp:
                from .sidekick import LEVELS
                prev_xp = LEVELS[level - 1][0]
                progress_to_next = round((state["player"]["xp"] - prev_xp) / (next_xp - prev_xp) * 100)

            # --- Week score ---
            sleep_component = (sleep_avg / 100 * 40) if sleep_avg else 0
            readiness_component = (readiness_avg / 100 * 30) if readiness_avg else 0
            active_count = sum(
                1 for qtype in ["daily", "weekly", "epic"]
                for q in state["quests"][qtype] if q["status"] == "active"
            )
            total_quest_pool = len(completed_this_week) + active_count
            quest_rate = (len(completed_this_week) / total_quest_pool) if total_quest_pool > 0 else 0
            quest_component = quest_rate * 15
            energy_days = len(set(e["date"] for e in energy_entries))
            energy_component = (energy_days / 7) * 15
            week_score = round(sleep_component + readiness_component + quest_component + energy_component)

            # --- Check achievements ---
            newly_unlocked = check_achievements(state, week_score=week_score)
            save_state(state)

            result = {
                "week": {"start": week_start, "end": today},
                "sleep": {
                    "avg_score": sleep_avg,
                    "best": sleep_best,
                    "worst": sleep_worst,
                    "trend": sleep_trend,
                    "nights_tracked": len(sleep_scores),
                },
                "readiness": {
                    "avg_score": readiness_avg,
                    "best": readiness_best,
                    "worst": readiness_worst,
                    "trend": readiness_trend,
                    "days_tracked": len(readiness_scores),
                },
                "energy": {
                    "avg_rating": energy_avg,
                    "best": energy_best,
                    "worst": energy_worst,
                    "logs_count": len(energy_entries),
                },
                "quests": {
                    "completed": len(completed_this_week),
                    "xp_earned": xp_this_week,
                    "level": level,
                    "title": title,
                    "progress_to_next": progress_to_next,
                    "streak": state["player"]["streaks"],
                },
                "achievements_unlocked": newly_unlocked,
                "week_score": week_score,
            }

            if fmt == "json":
                click.echo(format_json(result))
            else:
                lines = [f"Weekly Review — {week_start} to {today}"]
                lines.append(f"Week Score: {week_score}/100")
                lines.append("")
                if sleep_avg:
                    lines.append(f"Sleep: avg {sleep_avg}/100 | trend: {sleep_trend or 'n/a'} | {len(sleep_scores)} nights")
                    if sleep_best:
                        lines.append(f"  Best: {sleep_best['date']} ({sleep_best['score']})")
                    if sleep_worst:
                        lines.append(f"  Worst: {sleep_worst['date']} ({sleep_worst['score']})")
                else:
                    lines.append("Sleep: no data")
                if readiness_avg:
                    lines.append(f"Readiness: avg {readiness_avg}/100 | trend: {readiness_trend or 'n/a'} | {len(readiness_scores)} days")
                    if readiness_best:
                        lines.append(f"  Best: {readiness_best['date']} ({readiness_best['score']})")
                    if readiness_worst:
                        lines.append(f"  Worst: {readiness_worst['date']} ({readiness_worst['score']})")
                else:
                    lines.append("Readiness: no data")
                if energy_avg:
                    lines.append(f"Energy: avg {energy_avg}/5 | {len(energy_entries)} logs")
                    if energy_best:
                        lines.append(f"  Best: {energy_best['date']} ({energy_best['energy']}/5)")
                    if energy_worst:
                        lines.append(f"  Worst: {energy_worst['date']} ({energy_worst['energy']}/5)")
                else:
                    lines.append("Energy: no logs")
                lines.append(f"Quests: {len(completed_this_week)} completed | +{xp_this_week}xp")
                lines.append(f"Level: {level} {title} | progress: {progress_to_next or 0}%")
                if newly_unlocked:
                    lines.append(f"New achievements: {', '.join(newly_unlocked)}")
                click.echo("\n".join(lines))
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def achievements(fmt):
    """Show achievement status — unlocked and locked."""
    from .formatters import format_json
    from .sidekick import load_state, ACHIEVEMENTS, get_achievements_display

    state = load_state()
    if fmt == "json":
        unlocked = set(state["player"].get("achievements", []))
        data = {
            "unlocked": [
                {"id": aid, **info} for aid, info in ACHIEVEMENTS.items() if aid in unlocked
            ],
            "locked": [
                {"id": aid, **info} for aid, info in ACHIEVEMENTS.items() if aid not in unlocked
            ],
            "progress": f"{len(unlocked)}/{len(ACHIEVEMENTS)}",
        }
        click.echo(format_json(data))
    else:
        click.echo(get_achievements_display(state))


@cli.command()
@click.argument("entry_type", type=click.Choice(["energy", "mood", "note"]))
@click.argument("value")
@click.option("--note", default=None)
def log(entry_type, value, note):
    """Log energy, mood, or a note."""
    from .formatters import format_error
    from .sidekick import load_state, save_state, award_xp

    try:
        from datetime import datetime, timezone as tz
        from ..database import SessionLocal, init_db
        from ..models import JournalEntry
        init_db()
        db = SessionLocal()
        try:
            today = datetime.now(tz.utc).strftime("%Y-%m-%d")
            now_time = datetime.now(tz.utc).strftime("%H:%M")

            if entry_type == "energy":
                val = int(value)
                if not 1 <= val <= 5:
                    click.echo("Energy must be 1-5", err=True)
                    sys.exit(1)
                entry = JournalEntry(date=today, time=now_time, energy=val, notes=note)
                db.add(entry)
                db.commit()
                # XP for logging
                state = load_state()
                state = award_xp(state, 5, f"Logged energy: {val}/5")
                save_state(state)
                click.echo(f"🔋 Energy logged: {val}/5 (+5xp)")

            elif entry_type == "mood":
                val = int(value)
                if not 1 <= val <= 5:
                    click.echo("Mood must be 1-5", err=True)
                    sys.exit(1)
                entry = JournalEntry(date=today, time=now_time, mood=val, notes=note)
                db.add(entry)
                db.commit()
                state = load_state()
                state = award_xp(state, 5, f"Logged mood: {val}/5")
                save_state(state)
                click.echo(f"😊 Mood logged: {val}/5 (+5xp)")

            elif entry_type == "note":
                from ..models import Note
                n = Note(content=value, source="cli", raw_input=value)
                db.add(n)
                db.commit()
                click.echo(f"📝 Note saved: {value[:50]}")

        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--days", default=14, help="Days of history to analyze")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="json")
def trends(days, fmt):
    """Trend analysis — sleep, readiness, energy over time.

    Pure statistics, no scipy needed. Shows direction, day-of-week
    patterns, and flags. Useful for Hermes coaching insights.
    """
    from .formatters import format_json, format_error

    try:
        from datetime import datetime, timedelta
        from collections import defaultdict
        from ..database import SessionLocal, init_db
        from ..models import DataPoint, JournalEntry
        init_db()
        db = SessionLocal()
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")

            data_points = db.query(DataPoint).filter(
                DataPoint.date >= cutoff, DataPoint.date <= today,
            ).order_by(DataPoint.date).all()

            energy_entries = db.query(JournalEntry).filter(
                JournalEntry.date >= cutoff, JournalEntry.date <= today,
                JournalEntry.energy.isnot(None),
            ).order_by(JournalEntry.date).all()

            by_date = defaultdict(dict)
            for dp in data_points:
                by_date[dp.date][dp.type] = {"value": dp.value, "extra": dp.extra_data or {}}
            for ej in energy_entries:
                by_date[ej.date].setdefault("energy_log", [])
                by_date[ej.date]["energy_log"].append(ej.energy)

            dates_sorted = sorted(by_date.keys())
            metrics = _extract_metric_series(by_date, dates_sorted)

            trend_results = {}
            for name, series in metrics.items():
                if len(series) >= 4:
                    trend_results[name] = _compute_trend(series)

            result = {
                "period_days": days,
                "data_points": len(dates_sorted),
                "trends": trend_results,
                "day_of_week": _day_of_week_analysis(by_date),
                "flags": _compute_flags(metrics),
            }

            if fmt == "json":
                click.echo(format_json(result))
            else:
                click.echo(_format_trends_text(result))
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.option("--days", default=30, help="Days of history to analyze")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="json")
def pattern(days, fmt):
    """Pattern detection — correlations, trends, day-of-week effects.

    Uses PatternAnalyzer (scipy) if available, falls back to basic
    trend analysis otherwise. Returns patterns for Hermes coaching.
    """
    from .formatters import format_json, format_error

    try:
        from datetime import datetime, timedelta
        from collections import defaultdict
        from ..database import SessionLocal, init_db
        from ..models import DataPoint, JournalEntry
        init_db()
        db = SessionLocal()
        try:
            cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            today = datetime.now().strftime("%Y-%m-%d")

            data_points = db.query(DataPoint).filter(
                DataPoint.date >= cutoff, DataPoint.date <= today,
            ).order_by(DataPoint.date).all()

            energy_entries = db.query(JournalEntry).filter(
                JournalEntry.date >= cutoff, JournalEntry.date <= today,
                JournalEntry.energy.isnot(None),
            ).order_by(JournalEntry.date).all()

            analyzer_data = []
            for dp in data_points:
                analyzer_data.append({"date": dp.date, "type": dp.type, "value": dp.value, "metadata": dp.extra_data or {}})
            energy_by_date = defaultdict(list)
            for ej in energy_entries:
                energy_by_date[ej.date].append(ej.energy)
            for edate, evals in energy_by_date.items():
                analyzer_data.append({"date": edate, "type": "energy", "value": sum(evals) / len(evals), "metadata": {"log_count": len(evals)}})

            patterns_list = []
            engine_used = "basic"

            try:
                from ..pattern_analyzer import PatternAnalyzer as PA
                analyzer = PA()
                detected = analyzer.analyze_all(analyzer_data, min_days=5)
                engine_used = "scipy"
                for p in detected:
                    patterns_list.append({"name": p.name, "description": p.description, "type": p.pattern_type, "strength": round(p.strength, 3), "confidence": round(p.confidence, 3), "sample_size": p.sample_size, "actionable": p.actionable, "variables": p.variables})
            except ImportError:
                by_fb = defaultdict(dict)
                for dp in data_points:
                    by_fb[dp.date][dp.type] = {"value": dp.value, "extra": dp.extra_data or {}}
                for ej in energy_entries:
                    by_fb[ej.date].setdefault("energy_log", [])
                    by_fb[ej.date]["energy_log"].append(ej.energy)
                dates_fb = sorted(by_fb.keys())
                metrics_fb = _extract_metric_series(by_fb, dates_fb)
                for mname, series in metrics_fb.items():
                    if len(series) < 4:
                        continue
                    t = _compute_trend(series)
                    if t["direction"] != "stable":
                        patterns_list.append({"name": f"{'Improving' if t['direction'] == 'improving' else 'Declining'} {mname}", "description": f"{mname} {t['direction']}: {t['recent_avg']:.1f} vs {t['prior_avg']:.1f} ({t['change_pct']:+.1f}%)", "type": "trend", "strength": round(abs(t["change_pct"]) / 100, 3), "confidence": min(0.9, len(series) / 30), "sample_size": len(series), "actionable": True, "variables": [mname]})

            by_t = defaultdict(dict)
            for dp in data_points:
                by_t[dp.date][dp.type] = {"value": dp.value, "extra": dp.extra_data or {}}
            for ej in energy_entries:
                by_t[ej.date].setdefault("energy_log", [])
                by_t[ej.date]["energy_log"].append(ej.energy)
            dates_t = sorted(by_t.keys())
            metrics_t = _extract_metric_series(by_t, dates_t)
            trend_results = {}
            for mname, series in metrics_t.items():
                if len(series) >= 4:
                    trend_results[mname] = _compute_trend(series)

            result = {"period_days": days, "data_points": len(set(dp.date for dp in data_points)), "engine": engine_used, "patterns": patterns_list, "trends": trend_results, "day_of_week": _day_of_week_analysis(by_t), "flags": _compute_flags(metrics_t)}

            if fmt == "json":
                click.echo(format_json(result))
            else:
                click.echo(_format_pattern_text(result))
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


def _extract_metric_series(by_date, dates_sorted):
    metrics = {}
    sleep_scores, readiness_vals, energy_vals, sleep_dur = [], [], [], []
    for d in dates_sorted:
        day = by_date[d]
        if "sleep" in day:
            score = day["sleep"]["extra"].get("score")
            if score is not None:
                sleep_scores.append((d, float(score)))
            if day["sleep"]["value"] is not None:
                sleep_dur.append((d, float(day["sleep"]["value"])))
        if "readiness" in day:
            readiness_vals.append((d, float(day["readiness"]["value"])))
        if "energy_log" in day:
            vals = day["energy_log"]
            energy_vals.append((d, sum(vals) / len(vals)))
    if sleep_scores:
        metrics["sleep_score"] = sleep_scores
    if sleep_dur:
        metrics["sleep_hours"] = sleep_dur
    if readiness_vals:
        metrics["readiness"] = readiness_vals
    if energy_vals:
        metrics["energy"] = energy_vals
    return metrics


def _compute_trend(series):
    values = [v for _, v in series]
    n = len(values)
    mid = n // 2
    prior = values[:mid]
    recent = values[mid:]
    prior_avg = sum(prior) / len(prior) if prior else 0
    recent_avg = sum(recent) / len(recent) if recent else 0
    change_pct = ((recent_avg - prior_avg) / prior_avg) * 100 if prior_avg > 0 else 0.0
    if abs(change_pct) < 3:
        direction = "stable"
    elif change_pct > 0:
        direction = "improving"
    else:
        direction = "declining"
    x_mean = (n - 1) / 2
    y_mean = sum(values) / n
    numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
    denominator = sum((i - x_mean) ** 2 for i in range(n))
    slope = numerator / denominator if denominator else 0.0
    return {"direction": direction, "recent_avg": round(recent_avg, 1), "prior_avg": round(prior_avg, 1), "change_pct": round(change_pct, 1), "slope": round(slope, 3), "sample_size": n}


def _day_of_week_analysis(by_date):
    from collections import defaultdict
    from datetime import datetime as dt
    dow_values = defaultdict(lambda: defaultdict(list))
    for d, day_data in by_date.items():
        try:
            day_name = dt.strptime(d, "%Y-%m-%d").strftime("%A")
        except ValueError:
            continue
        if "sleep" in day_data and isinstance(day_data["sleep"], dict):
            score = day_data["sleep"]["extra"].get("score")
            if score is not None:
                dow_values["sleep_score"][day_name].append(float(score))
        if "readiness" in day_data and isinstance(day_data["readiness"], dict):
            val = day_data["readiness"]["value"]
            if val is not None:
                dow_values["readiness"][day_name].append(float(val))
    result = {}
    for metric, day_data in dow_values.items():
        avgs = {day: sum(vals) / len(vals) for day, vals in day_data.items() if vals}
        if len(avgs) >= 2:
            best = max(avgs, key=avgs.get)
            worst = min(avgs, key=avgs.get)
            result[f"best_{metric}_day"] = best
            result[f"worst_{metric}_day"] = worst
            result[f"{metric}_by_day"] = {k: round(v, 1) for k, v in avgs.items()}
    return result


def _compute_flags(metrics):
    flags = []
    for metric_name, series in metrics.items():
        if len(series) < 3:
            continue
        values = [v for _, v in series]
        consecutive_drops = 0
        for i in range(1, len(values)):
            if values[i] < values[i - 1]:
                consecutive_drops += 1
            else:
                consecutive_drops = 0
            if consecutive_drops >= 3:
                flags.append(f"{metric_name} declining {consecutive_drops + 1} consecutive days")
                break
        avg = sum(values) / len(values)
        latest = values[-1]
        if avg > 0 and latest < avg * 0.85:
            pct = round((1 - latest / avg) * 100)
            flags.append(f"{metric_name} currently {pct}% below average")
    return flags


def _format_trends_text(result):
    lines = [f"📊 Trends — last {result['period_days']} days ({result['data_points']} data points)", ""]
    for metric, t in result.get("trends", {}).items():
        icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(t["direction"], "•")
        lines.append(f"{icon} {metric}: {t['direction']} ({t['recent_avg']} vs {t['prior_avg']}, {t['change_pct']:+.1f}%)")
    dow = result.get("day_of_week", {})
    if dow:
        lines.append("")
        lines.append("📅 Day-of-week:")
        for key, val in dow.items():
            if key.startswith("best_") or key.startswith("worst_"):
                lines.append(f"  {key.replace('_', ' ')}: {val}")
    flags = result.get("flags", [])
    if flags:
        lines.append("")
        lines.append("⚠️ Flags:")
        for f in flags:
            lines.append(f"  • {f}")
    return "\n".join(lines)


def _format_pattern_text(result):
    lines = [f"🔍 Patterns — last {result['period_days']} days ({result['data_points']} data points, engine: {result['engine']})", ""]
    patterns = result.get("patterns", [])
    if patterns:
        for p in patterns:
            strength_bar = "●" * max(1, int(abs(p.get("strength", 0)) * 5))
            lines.append(f"  {strength_bar} {p['name']}")
            lines.append(f"    {p['description']}")
    else:
        lines.append("  No significant patterns detected yet.")
    lines.append("")
    for metric, t in result.get("trends", {}).items():
        icon = {"improving": "📈", "declining": "📉", "stable": "➡️"}.get(t["direction"], "•")
        lines.append(f"{icon} {metric}: {t['direction']} ({t['recent_avg']} vs {t['prior_avg']}, {t['change_pct']:+.1f}%)")
    dow = result.get("day_of_week", {})
    if dow:
        lines.append("")
        lines.append("📅 Day-of-week:")
        for key, val in dow.items():
            if key.startswith("best_") or key.startswith("worst_"):
                lines.append(f"  {key.replace('_', ' ')}: {val}")
    flags = result.get("flags", [])
    if flags:
        lines.append("")
        lines.append("⚠️ Flags:")
        for f in flags:
            lines.append(f"  • {f}")
    return "\n".join(lines)


if __name__ == "__main__":
    cli()
