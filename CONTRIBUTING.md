# Contributing to LifeOS

Thank you for your interest in contributing to LifeOS! This guide will help you get set up for development.

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- A code editor (VS Code recommended)

### Quick Start

```bash
# Clone the repository
git clone https://github.com/Perttulands/lifeOS.git
cd lifeOS

# Run setup
./setup.sh

# Create development environment file
cp .env.example .env
# Edit .env with your test API keys

# Activate virtual environment
source .venv/bin/activate

# Start development server with hot reload
python -m uvicorn src.api:app --reload --port 8080
```

### Project Structure

```
lifeOS/
├── src/                    # Backend Python code
│   ├── api.py             # FastAPI application entry point
│   ├── config.py          # Configuration and settings
│   ├── database.py        # SQLAlchemy setup
│   ├── models.py          # Database models
│   ├── schemas.py         # Pydantic schemas
│   ├── routers/           # API endpoint modules
│   │   ├── health.py      # Health checks
│   │   ├── insights.py    # Daily briefs and insights
│   │   ├── oura.py        # Oura integration
│   │   ├── calendar.py    # Google Calendar
│   │   ├── backfill.py    # Historical data import
│   │   └── ...
│   ├── integrations/      # External service clients
│   │   ├── oura.py        # Oura API client
│   │   ├── calendar.py    # Google Calendar client
│   │   └── ...
│   └── jobs/              # Background jobs
│       ├── daily_brief.py
│       └── weekly_review.py
├── ui/                     # Frontend code
│   ├── index.html         # Main dashboard
│   ├── css/               # Stylesheets
│   └── js/                # JavaScript modules
├── tests/                  # Test suite
├── docs/                   # Documentation
├── setup.sh               # Setup script
└── requirements.txt       # Python dependencies
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_api.py

# Run tests matching a pattern
pytest -k "test_oura"
```

### Code Style

We use standard Python conventions:

- **Formatting**: Follow PEP 8
- **Imports**: Use absolute imports, group by stdlib/third-party/local
- **Type hints**: Use type hints for function signatures
- **Docstrings**: Use Google-style docstrings

Example:

```python
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataPoint


def get_recent_data(
    db: Session,
    days: int = 7,
    data_type: Optional[str] = None
) -> List[DataPoint]:
    """
    Fetch recent data points from the database.

    Args:
        db: Database session
        days: Number of days to look back (default 7)
        data_type: Optional filter by data type

    Returns:
        List of DataPoint objects
    """
    ...
```

### Making Changes

1. **Create a branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Write code
   - Add tests
   - Update documentation if needed

3. **Test locally**
   ```bash
   pytest
   python -m uvicorn src.api:app --reload --port 8080
   ```

4. **Commit with a clear message**
   ```bash
   git commit -m "feat: add new insight type for sleep patterns"
   ```

   Commit message prefixes:
   - `feat:` New feature
   - `fix:` Bug fix
   - `docs:` Documentation only
   - `refactor:` Code refactoring
   - `test:` Adding tests
   - `chore:` Maintenance tasks

5. **Push and create PR**
   ```bash
   git push origin feature/your-feature-name
   ```

### API Development

When adding new API endpoints:

1. Create or modify a router in `src/routers/`
2. Register the router in `src/routers/__init__.py`
3. Add it to `src/api.py`
4. Add Pydantic schemas in `src/schemas.py` if needed
5. Add tests in `tests/`

Example router:

```python
# src/routers/example.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db

router = APIRouter(prefix="/api/example", tags=["example"])


@router.get("")
async def get_example(db: Session = Depends(get_db)):
    """Get example data."""
    return {"message": "Hello from example"}


@router.post("")
async def create_example(data: dict, db: Session = Depends(get_db)):
    """Create new example."""
    return {"created": True, "data": data}
```

### Frontend Development

The frontend uses vanilla JavaScript with ES6 modules:

- `ui/js/app.js` - Main application entry
- `ui/js/config.js` - Configuration
- `ui/js/utils.js` - Utility functions
- `ui/css/` - Modular CSS files

To modify the UI:

1. Edit files in `ui/`
2. Refresh the browser (hot reload works for the backend, manual refresh for frontend)
3. Use browser DevTools for debugging

### Database Migrations

We use SQLite with SQLAlchemy. For schema changes:

1. Modify models in `src/models.py`
2. Delete `lifeos.db` (development only!)
3. Run `./setup.sh` to recreate

For production, you'd use Alembic migrations (not yet set up).

### Environment Variables

See `.env.example` for all available options. Key ones for development:

```env
# Required for full functionality
OURA_TOKEN=your_test_token
LITELLM_API_KEY=your_api_key

# Useful for debugging
# Set these in your shell, not .env
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1
```

### Common Tasks

**Add a new data source:**
1. Create client in `src/integrations/`
2. Add models if needed in `src/models.py`
3. Create router in `src/routers/`
4. Add backfill support in `src/backfill.py`

**Add a new insight type:**
1. Add logic in `src/integrations/insights.py`
2. Update prompts if AI-generated
3. Add UI display in `ui/js/insights.js`

**Add a notification channel:**
1. Add client in `src/integrations/`
2. Register in `src/routers/notify.py`
3. Update `.env.example`

### Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue with reproduction steps
- **Features**: Open an Issue to discuss before implementing

### Code of Conduct

Be kind, be helpful, be constructive. We're all here to build something useful.

---

*Thanks for contributing to LifeOS!*
