# Builder 2 Mission: AI Engine + Insights

## Your Focus
Build the intelligence layer: pattern detection, daily briefs, and AI-powered insights.

## Tasks

### 1. LiteLLM Integration
```python
# src/ai.py
from litellm import completion

class LifeOSAI:
    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.model = model
    
    async def generate_daily_brief(self, context: dict) -> str:
        """Generate morning brief based on sleep, calendar, etc."""
        
    async def analyze_patterns(self, data: list[DataPoint]) -> list[Insight]:
        """Find patterns in historical data"""
        
    async def get_energy_prediction(self, today_data: dict) -> dict:
        """Predict energy levels for the day"""
```

### 2. Daily Brief Generation

System prompt:
```
You are LifeOS, a personal AI assistant that helps optimize daily life.

Given the user's sleep data, calendar, and recent patterns, generate a brief, 
actionable morning summary. Be conversational, not clinical.

Focus on:
1. Sleep quality assessment (compare to their average)
2. Energy prediction for the day
3. One specific, actionable suggestion
4. Encouraging but honest tone

Keep it under 150 words. No bullet points - write naturally.
```

Context to include:
- Last night's sleep (duration, quality, deep sleep %)
- 7-day sleep average for comparison
- Today's calendar (meetings, blocks)
- Recent energy patterns
- Day of week patterns

### 3. Pattern Detection

Look for patterns like:
- Sleep quality vs meeting load
- Deep sleep vs screen time (if trackable)
- Energy dips on specific days
- Recovery patterns after poor sleep
- Weekend vs weekday differences

```python
async def detect_patterns(self, data: list[DataPoint], days: int = 30) -> list[Pattern]:
    """
    Analyze data for actionable patterns.
    Returns insights like:
    - "Deep sleep drops 35% on days with >4h meetings"
    - "Your best sleep follows days with morning exercise"
    """
```

### 4. Cron Jobs

Create scripts for:
```python
# Daily brief - runs at 7 AM
async def daily_brief_job():
    # Fetch last night's sleep
    # Get today's calendar
    # Generate brief
    # Store in insights table
    # (Optionally) send via Clawdbot

# Weekly review - runs Sunday 6 PM
async def weekly_review_job():
    # Aggregate week's data
    # Find patterns
    # Generate summary
    # Store insight
```

### 5. API Endpoints
```python
@app.get("/api/insights/brief")  # Get today's brief
@app.get("/api/insights/patterns")  # Get detected patterns
@app.post("/api/insights/generate")  # Force regenerate
@app.get("/api/predictions/energy")  # Today's energy prediction
```

## Prompt Engineering Tips

- Be specific about data format in prompts
- Include examples of good insights
- Ask for confidence levels
- Request actionable suggestions, not just observations

## Deliverables Checklist

- [ ] LiteLLM client working
- [ ] Daily brief generation tested
- [ ] Pattern detection logic
- [ ] Brief cron script
- [ ] Weekly review cron script
- [ ] API endpoints for insights
- [ ] Git commits for each milestone

## Sample Output

**Daily Brief Example:**
> Good morning! You got 6h 12m of sleep last night - about 50 minutes less than your usual. Your deep sleep was solid though (1h 45m), so you're not starting from zero.
>
> Looking at your calendar, you've got back-to-back meetings 2-5pm. Based on your patterns, you usually hit a wall around 3pm on short-sleep days. Consider moving that design review to tomorrow if possible, or at least grab a 15-minute walk beforehand.
>
> Today's a good day for reactive work - save the creative heavy lifting for when you've caught up on rest.
