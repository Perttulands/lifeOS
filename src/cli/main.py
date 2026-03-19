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
        from ..models import DataPoint, JournalEntry, CalendarEvent
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

            result = {
                "date": target_date,
                "day": day_name,
                "today": today_data,
                "averages": averages,
                "history_days": len(history),
                "energy_logs": energy_logs,
                "calendar": calendar,
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
                    lines.append(f"💤 Sleep: {sleep['value']:.1f}h (avg: {avg}h)")
                    if sleep.get("deep_sleep_hours"):
                        lines.append(f"   Deep: {sleep['deep_sleep_hours']:.1f}h | REM: {sleep.get('rem_sleep_hours', 0):.1f}h")
                    if sleep.get("score"):
                        lines.append(f"   Score: {sleep['score']}/100")
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

            result = {
                "date": today,
                "last_sleep": {
                    "date": latest_sleep.date if latest_sleep else None,
                    "hours": latest_sleep.value if latest_sleep else None,
                    "score": (latest_sleep.extra_data or {}).get("score") if latest_sleep else None,
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
                    lines.append(f"💤 Last sleep: {s['hours']:.1f}h (score: {s['score']}) on {s['date']}")
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


if __name__ == "__main__":
    cli()
