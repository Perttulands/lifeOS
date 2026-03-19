"""LifeOS CLI — agent-first interface."""
import sys
import click
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@click.group()
def cli():
    """LifeOS — your personal operating system."""
    pass


@cli.command()
@click.option("--date", default=None, help="Date (YYYY-MM-DD), default today")
@click.option("--format", "fmt", type=click.Choice(["text", "json"]), default="text")
def brief(date, fmt):
    """Generate your daily brief."""
    from .formatters import format_json, format_error

    try:
        from ..database import SessionLocal, init_db
        from ..insights_service import InsightsService
        init_db()
        db = SessionLocal()
        try:
            svc = InsightsService(db)
            insight = svc.generate_daily_brief(date=date)

            if fmt == "json":
                data = {
                    "content": insight.content,
                    "date": insight.date,
                    "confidence": insight.confidence,
                    "tokens_used": insight.context.get("tokens_used", 0) if insight.context else 0,
                }
                click.echo(format_json(data))
            else:
                click.echo(insight.content)
        finally:
            db.close()
    except Exception as e:
        format_error(str(e))
        sys.exit(2)


@cli.command()
@click.argument("source", type=click.Choice(["oura", "calendar", "all"]), default="all")
def sync(source):
    """Sync data from external sources."""
    from .formatters import format_error

    try:
        from ..database import SessionLocal, init_db
        init_db()
        db = SessionLocal()
        total = 0
        try:
            if source in ("oura", "all"):
                from ..integrations.oura import OuraSyncService
                result = OuraSyncService(db).sync_all()
                count = sum(r.records_synced for r in result if r.success)
                total += count
                click.echo(f"Oura: synced {count} records")

            if source in ("calendar", "all"):
                from ..integrations.calendar import CalendarSyncService
                result = CalendarSyncService(db).sync()
                count = result.events_synced
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
