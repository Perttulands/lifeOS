# Builder 1 Mission: Core + Oura Integration

## Your Focus
Build the foundation: project structure, Oura API integration, and data layer.

## Tasks

### 1. Project Structure
```
lifeOS/
├── src/
│   ├── __init__.py
│   ├── api.py           # FastAPI app
│   ├── models.py        # SQLAlchemy models
│   ├── oura.py          # Oura API adapter
│   ├── database.py      # SQLite connection
│   └── config.py        # Environment config
├── ui/                   # (Builder 3)
├── requirements.txt
├── .env.example
└── README.md
```

### 2. Oura API Adapter
```python
# src/oura.py
class OuraClient:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.ouraring.com/v2"
    
    async def get_sleep(self, start_date: str, end_date: str) -> list[SleepData]:
        """Fetch sleep data for date range"""
        
    async def get_daily_activity(self, start_date: str, end_date: str) -> list[ActivityData]:
        """Fetch daily activity data"""
        
    async def get_readiness(self, start_date: str, end_date: str) -> list[ReadinessData]:
        """Fetch readiness scores"""
```

Oura API docs: https://cloud.ouraring.com/docs/

### 3. Database Schema
```python
# src/models.py
class DataPoint(Base):
    id = Column(Integer, primary_key=True)
    source = Column(String)  # 'oura', 'manual', 'calendar'
    data_type = Column(String)  # 'sleep', 'activity', 'readiness', 'energy', 'mood'
    value = Column(JSON)  # Flexible storage
    timestamp = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

class Insight(Base):
    id = Column(Integer, primary_key=True)
    insight_type = Column(String)  # 'daily_brief', 'pattern', 'alert'
    content = Column(Text)
    context = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
```

### 4. API Endpoints
```python
# src/api.py
@app.get("/api/health")
@app.get("/api/data/sleep")
@app.get("/api/data/activity") 
@app.get("/api/data/readiness")
@app.post("/api/sync/oura")  # Trigger manual sync
@app.get("/api/insights/today")
```

### 5. Sync Script
Create cron-able script to sync Oura data:
```bash
python -m src.sync  # Syncs last 7 days of data
```

## Environment

Create `.env.example`:
```
OURA_TOKEN=
LITELLM_API_KEY=
DATABASE_URL=sqlite:///./lifeOS.db
```

## Deliverables Checklist

- [ ] Project structure created
- [ ] Requirements.txt with dependencies
- [ ] Oura client working (test with real token)
- [ ] SQLite database initialized
- [ ] API server runs on port 8080
- [ ] Sync script pulls last 7 days
- [ ] Git commits for each milestone

## Notes

- Keep it simple - SQLite is fine, no need for Postgres
- Async where sensible but don't over-engineer
- Test with real Oura data if token available
