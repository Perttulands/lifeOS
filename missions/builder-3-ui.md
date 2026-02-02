# Builder 3 Mission: Dashboard UI

## Your Focus
Build a beautiful, joyful dashboard that makes checking in feel rewarding.

## Design Principles

1. **Glanceable** - Key info visible in 2 seconds
2. **Dark mode first** - Easy on the eyes, especially morning
3. **Minimal but warm** - Not cold/clinical, not cluttered
4. **Mobile-friendly** - Works on phone without app
5. **No build step** - Vanilla HTML/CSS/JS, single file deployable

## Tasks

### 1. Dashboard Layout

```
┌────────────────────────────────────────────────────────────┐
│  LifeOS                                    ☾ Sun, Feb 2    │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Daily Brief                        │   │
│  │  "Good morning! You got 6h 12m of sleep..."         │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                 │
│  │  Sleep   │  │ Readiness│  │  Energy  │                 │
│  │   6h12m  │  │    72    │  │  ⚡ 3/5  │                 │
│  │  ▃▅▇▅▃   │  │   Good   │  │  (self)  │                 │
│  └──────────┘  └──────────┘  └──────────┘                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  7-Day Sleep Trend                                   │   │
│  │  ▁▃▅▇▅▃▁                                            │   │
│  │  M  T  W  T  F  S  S                                │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │  Quick Log                                           │   │
│  │  How's your energy? [1] [2] [3] [4] [5]             │   │
│  │  [                    Note...                     ]  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

### 2. Color Palette

```css
:root {
    --bg-primary: #0f0f1a;      /* Deep space */
    --bg-card: #1a1a2e;         /* Card background */
    --accent: #6366f1;          /* Indigo accent */
    --accent-glow: #818cf8;     /* Lighter for glow */
    --text-primary: #f1f5f9;    /* Off-white */
    --text-muted: #94a3b8;      /* Muted text */
    --success: #10b981;         /* Good scores */
    --warning: #f59e0b;         /* Medium scores */
    --error: #ef4444;           /* Low scores */
}
```

### 3. Components

**Score Card:**
```html
<div class="score-card">
    <div class="score-label">Sleep</div>
    <div class="score-value">6h 12m</div>
    <div class="score-trend">▃▅▇▅▃</div>
    <div class="score-delta">-48m vs avg</div>
</div>
```

**Daily Brief Card:**
```html
<div class="brief-card">
    <div class="brief-header">
        <span class="brief-icon">🌅</span>
        <span class="brief-time">Generated 7:00 AM</span>
    </div>
    <div class="brief-content">
        <!-- AI-generated text -->
    </div>
</div>
```

**Quick Log:**
```html
<div class="quick-log">
    <div class="energy-buttons">
        <button data-value="1">1</button>
        <button data-value="2">2</button>
        <button data-value="3" class="selected">3</button>
        <button data-value="4">4</button>
        <button data-value="5">5</button>
    </div>
    <textarea placeholder="Optional note..."></textarea>
    <button class="log-submit">Log</button>
</div>
```

### 4. Animations

Subtle, not distracting:
- Cards fade in on load (staggered)
- Score numbers count up
- Trend sparklines draw in
- Button press feedback (scale)

### 5. API Integration

```javascript
// Fetch and display data
async function loadDashboard() {
    const [sleep, brief, insights] = await Promise.all([
        fetch('/api/data/sleep?days=7').then(r => r.json()),
        fetch('/api/insights/brief').then(r => r.json()),
        fetch('/api/insights/patterns').then(r => r.json())
    ]);
    
    renderSleepCard(sleep);
    renderBrief(brief);
    renderInsights(insights);
}

// Quick log submission
async function submitLog(energy, note) {
    await fetch('/api/log', {
        method: 'POST',
        body: JSON.stringify({ energy, note, timestamp: new Date() })
    });
    showToast('Logged! 🎉');
}
```

### 6. Responsive

Works on:
- Desktop (1200px+): 3-column grid
- Tablet (768px-1199px): 2-column
- Mobile (<768px): Single column stack

## Deliverables Checklist

- [ ] index.html with full structure
- [ ] style.css with dark theme
- [ ] app.js with API integration
- [ ] Responsive across devices
- [ ] Loading states
- [ ] Error states
- [ ] Quick log working
- [ ] Git commits for each milestone

## Inspiration

- Linear's dark UI
- Raycast dashboard
- Oura app (but less busy)
- Notion's clean typography

## Files

```
ui/
├── index.html    # Single page app
├── style.css     # All styles
└── app.js        # All logic
```

Make it something you'd want to look at every morning.
