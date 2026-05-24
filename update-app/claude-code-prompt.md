# MoodTune UI Overhaul

## Your Role

You are implementing a visual overhaul of an existing Shiny for Python app called MoodTune. The functionality is already built and working. Your job is purely **design and layout** -- making the app look and feel like a polished consumer product, not an academic prototype.

## Available Tools

- **Context7 MCP**: Use this to fetch up-to-date Shiny for Python docs before assuming any API signatures. Always verify component APIs (especially `ui.sidebar`, `ui.nav_panel`, layout functions) against current docs.
- **Playwright MCP**: Use this to visually verify every change. Screenshot the page after each modification. Compare against the reference mockup.

## Critical References

Before writing ANY code, read these files:

1. `docs/design-system.md` -- contains exact CSS values (colors, typography, spacing, shadows, component specs). Use these values verbatim. Do not improvise colors, fonts, or spacing.
2. `docs/homepage-mockup.html` -- open this in Playwright to see the exact visual target for the homepage. Every other page should match this aesthetic.
3. `UPGRADE_PLAN.md` -- the existing task plan. Follow its structure but apply the design system to every task.

## Design Rules (non-negotiable)

1. **Sidebar navigation, not top navbar.** The app must use a persistent left sidebar (240px wide) with navigation links and participant selector. Remove the current top `ui.page_navbar` and replace with a sidebar layout. See `docs/design-system.md` for exact specs.

2. **All CSS values come from the design system.** Do not invent colors, border-radius values, font sizes, or shadows. Every visual property must trace back to a token in `design-system.md`.

3. **All text in Flemish/Dutch.** No em-dashes, no en-dashes. Use plain hyphens.

4. **Cards, not full-width sections.** Content lives in cards with `border-radius: 16px`, `background: var(--bg-card)`, `border: 1px solid var(--border-subtle)`. Cards are arranged in grids, not stacked full-width.

5. **Typography hierarchy.** Display headings use Sora 700. Section headings use Sora 600. Body uses DM Sans 400. Metrics use Sora 700 at 2.5rem in accent color. Import both fonts.

## Workflow

Work **one page at a time** in this order:

### Phase 0: Layout Shell
Convert the app from `ui.page_navbar` (top nav) to a sidebar layout:
- Fixed left sidebar (240px) with logo, nav links, divider, participant selector
- Main content area with `margin-left: 240px`
- Fixed bottom now-playing bar (80px)
- Apply the global CSS from `design-system.md` into `www/styles.css`
- **Verify**: Use Playwright to screenshot. The shell should match the layout structure of `docs/homepage-mockup.html` (sidebar + main + bottom bar).

### Phase 1: Homepage (`modules/home.py`)
Rewrite the homepage to match `docs/homepage-mockup.html` exactly:
- Playlist header card with cover art area, title, subtitle, metadata row, badge
- Stats row (4 stat cards in a grid)
- Track list in a card with header row and track rows
- ISO direction indicator at the bottom of the track list
- Now-playing bar populated with the first track
- **Verify**: Screenshot with Playwright and compare side-by-side with the mockup.

### Phase 2: Each remaining page
For each page (Wetenschap, Pipeline, Circadiaan, Aanbevelen, Afspelen, Resultaten, Model):
1. Read the page's section in `UPGRADE_PLAN.md` for functional requirements
2. Apply the design system: cards with proper border-radius, stat cards for KPIs, proper typography, chart styling (transparent backgrounds, DM Sans font, subtle grid lines)
3. Replace any remaining English text with Dutch
4. **Verify**: Screenshot with Playwright after completing each page. Check: sidebar visible, cards have proper styling, typography hierarchy is correct, no default Bootstrap elements remain.

### Phase 3: Polish
- Verify all pages use consistent pill selectors (same component, same styling)
- Add `fadeInUp` animation to main content sections
- Ensure Plotly charts use the `PLOTLY_LAYOUT` config from the design system
- Test all interactive elements still work (sliders, dropdowns, pills)
- Final screenshot pass of every page

## Shiny for Python Implementation Notes

The sidebar layout in Shiny for Python can be achieved with `ui.page_sidebar()` or a custom layout using `ui.div()` with CSS classes. Use Context7 to verify the current API.

For custom CSS, place everything in `www/styles.css`. The design system's CSS variables should be defined in `:root` at the top of this file.

For the now-playing bar, use a `ui.div()` with `position: fixed` styling -- it's a UI element, not a Shiny output.

## What "Done" Looks Like

- Opening the app feels like opening Spotify or a modern SaaS product
- The sidebar is always visible with clear active-page indication
- Every card has depth (border, subtle background, rounded corners)
- Typography has clear hierarchy (you can tell headings from body from captions at a glance)
- Charts blend into the dark theme (no white plot backgrounds, no default fonts)
- All text is in Dutch/Flemish
- No default Shiny/Bootstrap styling is visible anywhere
