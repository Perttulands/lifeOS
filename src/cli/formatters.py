"""Output formatters for LifeOS CLI."""
import json
import sys
from datetime import datetime, timezone
from typing import Any, Dict


def format_json(data: Dict[str, Any], status: str = "ok") -> str:
    """Format data as JSON with standard envelope."""
    envelope = {
        "status": status,
        "data": data,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(envelope, indent=2, default=str)


def format_error(message: str) -> None:
    """Print error to stderr."""
    print(f"Error: {message}", file=sys.stderr)
