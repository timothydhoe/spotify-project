# MoodTune Design System

This document defines the visual language for MoodTune. Every value is concrete -- no interpretation needed. When implementing UI, use these exact values.

## Color Tokens

```css
:root {
  /* Backgrounds - warm dark, never pure black */
  --bg-base: #0f0f0f;
  --bg-surface: #1a1a1a;
  --bg-card: #1e1e1e;
  --bg-card-hover: #252525;
  --bg-elevated: #2a2a2a;
  --bg-input: #2c2c2c;
  --bg-glass: rgba(255, 255, 255, 0.04);
  --bg-glass-hover: rgba(255, 255, 255, 0.08);

  /* Text */
  --text-primary: #f5f5f5;
  --text-secondary: rgba(255, 255, 255, 0.65);
  --text-tertiary: rgba(255, 255, 255, 0.4);
  --text-accent: #22c55e;

  /* Accent */
  --accent: #22c55e;
  --accent-hover: #16a34a;
  --accent-muted: rgba(34, 197, 94, 0.15);
  --accent-glow: rgba(34, 197, 94, 0.25);

  /* Semantic */
  --energy-color: #f97316;
  --calm-color: #3b82f6;
  --neutral-color: #a855f7;

  /* Borders */
  --border-subtle: rgba(255, 255, 255, 0.06);
  --border-default: rgba(255, 255, 255, 0.10);
  --border-strong: rgba(255, 255, 255, 0.15);
}
```

## Typography

Use **DM Sans** for body and UI, **Sora** for display headings.
Import: `https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Sora:wght@600;700&display=swap`

```css
/* Display (page titles, hero text) */
font-family: 'Sora', sans-serif;
font-weight: 700;
font-size: 2rem;       /* 32px */
line-height: 1.2;
letter-spacing: -0.02em;

/* Heading (section titles) */
font-family: 'Sora', sans-serif;
font-weight: 600;
font-size: 1.25rem;    /* 20px */
line-height: 1.3;

/* Body */
font-family: 'DM Sans', sans-serif;
font-weight: 400;
font-size: 0.9375rem;  /* 15px */
line-height: 1.6;

/* Caption / Label */
font-family: 'DM Sans', sans-serif;
font-weight: 500;
font-size: 0.75rem;    /* 12px */
letter-spacing: 0.04em;
text-transform: uppercase;
color: var(--text-tertiary);

/* Metric (large numbers in stat cards) */
font-family: 'Sora', sans-serif;
font-weight: 700;
font-size: 2.5rem;     /* 40px */
line-height: 1;
color: var(--accent);
```

## Spacing Scale

```
4px  - xs   (icon padding, tight gaps)
8px  - sm   (within components)
12px - md   (between related elements)
16px - base (standard component padding)
24px - lg   (between sections within a card)
32px - xl   (between cards)
48px - 2xl  (between major page sections)
64px - 3xl  (page top/bottom margins)
```

## Surfaces & Cards

Every card uses this exact pattern:

```css
.card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
  padding: 24px;
  transition: all 0.2s ease;
}

.card:hover {
  background: var(--bg-card-hover);
  border-color: var(--border-default);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* Glass variant (for overlays, floating panels) */
.card-glass {
  background: var(--bg-glass);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-subtle);
  border-radius: 16px;
}

/* Stat card (KPI / metric display) */
.stat-card {
  background: var(--bg-card);
  border: 1px solid var(--border-subtle);
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  padding: 20px 24px;
}
```

## Layout Rules

### Sidebar Navigation (CRITICAL: not top navbar)

The app uses a **persistent left sidebar**, not a top navigation bar.

```
+--sidebar--+--------main-content---------+
|            |                             |
| Logo       |   Page content              |
| Nav items  |   max-width: 1200px         |
|            |   padding: 32px             |
|            |                             |
| w: 240px   |   flex: 1                   |
+------------+-----------------------------+
+----------now-playing-bar-----------------+
```

```css
.sidebar {
  width: 240px;
  height: 100vh;
  position: fixed;
  left: 0;
  top: 0;
  background: var(--bg-surface);
  border-right: 1px solid var(--border-subtle);
  padding: 24px 16px;
  display: flex;
  flex-direction: column;
  z-index: 100;
}

.sidebar-nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  color: var(--text-secondary);
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 0.9375rem;
  transition: all 0.15s ease;
  cursor: pointer;
}

.sidebar-nav-item:hover {
  background: var(--bg-glass-hover);
  color: var(--text-primary);
}

.sidebar-nav-item.active {
  background: var(--accent-muted);
  color: var(--accent);
}

.main-content {
  margin-left: 240px;
  padding: 32px;
  padding-bottom: 100px; /* space for now-playing bar */
  min-height: 100vh;
}
```

### Card Grid

Page content uses a responsive card grid, NOT full-width stacking:

```css
.card-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 24px;
}

/* For stat/KPI rows, use fixed columns */
.stat-row {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
```

## Components

### Pill Selector (Participant Picker)

```css
.pill {
  padding: 8px 18px;
  border-radius: 999px;
  border: 1px solid var(--border-default);
  background: transparent;
  color: var(--text-secondary);
  font-family: 'DM Sans', sans-serif;
  font-weight: 500;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.15s ease;
}

.pill:hover {
  border-color: var(--accent);
  color: var(--text-primary);
}

.pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: #0f0f0f;
  font-weight: 600;
}

.pill.disabled {
  opacity: 0.35;
  pointer-events: none;
}
```

### Track Row (Playlist Item)

```css
.track-row {
  display: grid;
  grid-template-columns: 32px 48px 1fr auto auto;
  align-items: center;
  gap: 16px;
  padding: 10px 16px;
  border-radius: 10px;
  transition: background 0.15s ease;
}

.track-row:hover {
  background: var(--bg-glass-hover);
}

.track-number {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
}

.track-art {
  width: 48px;
  height: 48px;
  border-radius: 6px;
  background: var(--bg-elevated);
}

.track-title {
  color: var(--text-primary);
  font-weight: 500;
}

.track-artist {
  color: var(--text-secondary);
  font-size: 0.875rem;
}

.track-duration {
  color: var(--text-tertiary);
  font-variant-numeric: tabular-nums;
  font-size: 0.875rem;
}
```

### Now Playing Bar

Fixed to the bottom of the viewport, full width:

```css
.now-playing {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  background: var(--bg-elevated);
  border-top: 1px solid var(--border-subtle);
  display: grid;
  grid-template-columns: 240px 1fr 200px;
  align-items: center;
  padding: 0 24px;
  z-index: 200;
}
```

### Badges (Playlist Type)

```css
.badge {
  display: inline-flex;
  align-items: center;
  padding: 4px 12px;
  border-radius: 999px;
  font-family: 'DM Sans', sans-serif;
  font-weight: 600;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}

.badge-energy {
  background: rgba(249, 115, 22, 0.15);
  color: #f97316;
}

.badge-calm {
  background: rgba(59, 130, 246, 0.15);
  color: #3b82f6;
}

.badge-neutral {
  background: rgba(168, 85, 247, 0.15);
  color: #a855f7;
}
```

## Charts & Data Visualization

All Plotly charts must use these overrides:

```python
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(
        family="DM Sans, sans-serif",
        color="rgba(255,255,255,0.65)",
        size=13,
    ),
    title_font=dict(
        family="Sora, sans-serif",
        size=18,
        color="#f5f5f5",
    ),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.1)",
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.06)",
        zerolinecolor="rgba(255,255,255,0.1)",
    ),
    margin=dict(l=48, r=24, t=48, b=40),
)

# Color sequence for traces
CHART_COLORS = ["#22c55e", "#3b82f6", "#f97316", "#a855f7", "#ec4899", "#eab308"]
```

## Shadows

```css
--shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.2);
--shadow-md: 0 4px 16px rgba(0, 0, 0, 0.25);
--shadow-lg: 0 8px 32px rgba(0, 0, 0, 0.35);
--shadow-glow: 0 0 24px var(--accent-glow);
```

## Transitions

All interactive elements: `transition: all 0.15s ease;`
Cards on hover: `transition: all 0.2s ease;`
Page content entry: `animation: fadeInUp 0.3s ease;`

```css
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

## Anti-Patterns (DO NOT USE)

- Top navigation bar (use sidebar)
- Pure black backgrounds `#000000` (use `#0f0f0f`)
- Default Shiny/Bootstrap styling
- Borders without `border-subtle` transparency
- Cards without border-radius
- Full-width sections without max-width constraint
- Em-dashes or en-dashes anywhere (use hyphens)
- Any text in English
