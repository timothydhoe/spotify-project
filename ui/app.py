"""MoodTune — Shiny for Python entrypoint."""
from pathlib import Path

from shiny import App, reactive, render, ui

from modules import (
    circadian, home, model, music_browser, pipeline,
    recommendation, recovery, results, science, session_replay,
)
from utils.data_loader import APP_DATA, PARTICIPANTS

_FRUIT_EMOJI = {
    "bosbes":      "🫐",
    "kokosnoot":   "🥥",
    "limoen":      "🍋",
    "peer":        "🍐",
    "kiwi":        "🥝",
    "watermeloen": "🍉",
}

# Data-availability tooltip text per participant
_DATA_LEVEL_TIP = {
    "bosbes":      "Volledige biometrische data",
    "kokosnoot":   "Volledige biometrische data",
    "limoen":      "Gedeeltelijke data (geen stresssensor)",
    "peer":        "Gedeeltelijke data (geen biometrie)",
    "kiwi":        "Alleen stemming-check-ins",
    "watermeloen": "Alleen stemming-check-ins",
}


# ---------------------------------------------------------------------------
# Custom navbar
# ---------------------------------------------------------------------------

def _build_navbar() -> ui.Tag:
    """
    Three-column CSS-grid navbar:
      Left  — logo (links to Home tab)
      Center — Profiel analyse ▾  |  Muziekadvies  |  Hoe het werkt ▾
      Right  — Deelnemer: <select>  + hamburger (mobile)
    """

    def _dropdown_link(label: str, section: str, sub: str) -> ui.Tag:
        return ui.tags.a(
            label,
            href="#",
            onclick=f"mtNavTo('{section}','{sub}'); return false;",
        )

    # Participant <select> options (reused for desktop + mobile)
    def _participant_opts(select_id: str, extra_style: str = "") -> ui.Tag:
        opts = [
            ui.tags.option(
                f"{_FRUIT_EMOJI[p]} {p.capitalize()}",
                value=p,
                selected=(p == "bosbes"),
                title=_DATA_LEVEL_TIP.get(p, ""),
            )
            for p in PARTICIPANTS
        ]
        return ui.tags.select(
            *opts,
            id=select_id,
            class_="mt-nav-participant-select",
            style=extra_style,
            onchange=(
                "mtSelectParticipant(this.value);"
                # Keep desktop + mobile selects in sync
                + ("document.getElementById('mt-p-desktop').value=this.value;" if "mobile" in select_id else
                   "document.getElementById('mt-p-mobile').value=this.value;")
            ),
        )

    inline_js = ui.HTML("""
<script>
(function () {
'use strict';

/* ── Navigation ──────────────────────────────────────────────────────────── */
window.mtNavTo = function (section, sub) {
  if (window.Shiny && Shiny.setInputValue) {
    Shiny.setInputValue('mt_nav_goto', {section: section, sub: sub || null}, {priority: 'event'});
  }
  // Highlight the matching trigger
  document.querySelectorAll('.mt-nav-trigger').forEach(function (el) {
    el.classList.toggle('active', el.getAttribute('data-section') === section);
  });
  // Close any open dropdown
  _mtCloseDropdowns();
};

/* ── Dropdown toggle (click-based for keyboard/touch) ────────────────────── */
window.mtToggleDropdown = function (btn) {
  var parent = btn.closest('.mt-nav-dropdown');
  var wasOpen = parent.classList.contains('open');
  _mtCloseDropdowns();
  if (!wasOpen) {
    parent.classList.add('open');
    btn.setAttribute('aria-expanded', 'true');
  }
};

function _mtCloseDropdowns() {
  document.querySelectorAll('.mt-nav-dropdown.open').forEach(function (el) {
    el.classList.remove('open');
    var btn = el.querySelector('.mt-nav-trigger');
    if (btn) btn.setAttribute('aria-expanded', 'false');
  });
}

// Close on outside click or Escape
document.addEventListener('click', function (e) {
  if (!e.target.closest('.mt-nav-dropdown')) _mtCloseDropdowns();
});
document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape') _mtCloseDropdowns();
});

/* ── Participant selector ────────────────────────────────────────────────── */
var _MT_EMOJI = {bosbes:'🫐',kokosnoot:'🥥',limoen:'🍋',peer:'🍐',kiwi:'🥝',watermeloen:'🍉'};

window.mtSelectParticipant = function (val) {
  if (window.Shiny && Shiny.setInputValue) {
    Shiny.setInputValue('mt_participant_nav', val, {priority: 'event'});
  }
  // Update giant emoji background
  var el = document.getElementById('home-emoji-bg');
  if (el) {
    el.textContent = _MT_EMOJI[val] || '🎵';
    el.classList.remove('pop-in');
    void el.offsetWidth; // force reflow to retrigger animation
    el.classList.add('pop-in');
  }
};

/* ── Mobile hamburger ───────────────────────────────────────────────────── */
window.mtToggleMobileMenu = function () {
  var menu = document.getElementById('mt-mobile-menu');
  var btn  = document.getElementById('mt-hamburger-btn');
  if (!menu || !btn) return;
  var open = menu.classList.toggle('open');
  btn.classList.toggle('open', open);
  btn.setAttribute('aria-expanded', open ? 'true' : 'false');
};

window.mtCloseMobileMenu = function () {
  var menu = document.getElementById('mt-mobile-menu');
  var btn  = document.getElementById('mt-hamburger-btn');
  if (menu) menu.classList.remove('open');
  if (btn)  { btn.classList.remove('open'); btn.setAttribute('aria-expanded', 'false'); }
};

/* ── Sync active state when Bootstrap tab changes ───────────────────────── */
document.addEventListener('DOMContentLoaded', function () {
  // Home is the default tab — activate dark theme immediately
  document.body.classList.add('mt-home-active');
  // Inject emoji as direct body child so position:fixed escapes all stacking contexts
  var initSel = document.getElementById('mt-p-desktop');
  var initVal = initSel ? initSel.value : 'bosbes';
  var initEl  = document.getElementById('home-emoji-bg');
  if (!initEl) {
    initEl = document.createElement('div');
    initEl.id = 'home-emoji-bg';
    initEl.className = 'mt-home-emoji-bg';
    document.body.insertBefore(initEl, document.body.firstChild);
  }
  initEl.textContent = _MT_EMOJI[initVal] || '🫐';
  initEl.classList.add('pop-in');

  document.addEventListener('shown.bs.tab', function (e) {
    if (!e.target) return;
    var revMap = {
      'Home': 'home', 'Jouw Profiel': 'profiel',
      'Aanbevelingen': 'aanbevelingen', 'Achtergrond': 'achtergrond',
    };
    var label = e.target.textContent.trim();
    var sec   = revMap[label];
    if (sec) {
      document.querySelectorAll('.mt-nav-trigger').forEach(function (el) {
        el.classList.toggle('active', el.getAttribute('data-section') === sec);
      });
    }
    // Dark theme is permanent — body.mt-home-active set at DOMContentLoaded and never removed
  });
});

/* ── Emoji scroll-fade ────────────────────────────────────────────────────── */
(function () {
  var FADE_END     = 450;  // px of scroll to reach fully transparent (~4-5 wheel ticks)
  var BASE_OPACITY = 0.16; // matches emojiSpring 100% keyframe in CSS
  var _prevY       = -1;

  function _applyFade(y) {
    var el = document.getElementById('home-emoji-bg');
    if (!el) return;
    var t = Math.min(1, Math.max(0, y / FADE_END));
    // Use setProperty('important') to always beat animation-fill-mode:forwards
    el.style.setProperty('opacity', String(BASE_OPACITY * (1 - t)), 'important');
  }

  // rAF loop — runs at 60fps, only touches the DOM when scroll position changed.
  // This is the primary mechanism and works regardless of which element fires scroll.
  function _tick() {
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    if (y !== _prevY) { _prevY = y; _applyFade(y); }
    requestAnimationFrame(_tick);
  }
  requestAnimationFrame(_tick);

  // Scroll event as supplementary trigger (fires even between rAF frames)
  window.addEventListener('scroll', function () {
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    _applyFade(y);
  }, { passive: true });

  // On any Bootstrap tab shown: scroll to top so emoji is fully visible
  document.addEventListener('shown.bs.tab', function () {
    window.scrollTo({ top: 0, behavior: 'instant' });
    _prevY = 0;
    _applyFade(0);
  });
})();

})();
</script>
""")

    return ui.tags.div(
        # ── Navbar strip ──────────────────────────────────────────────────────
        ui.tags.nav(
            # Left: logo / home
            ui.tags.button(
                ui.tags.img(
                    src="logo/MoodTune-logo.svg",
                    alt="MoodTune",
                    class_="mt-navbar-logo-img",
                ),
                ui.tags.span("MoodTune"),
                class_="mt-navbar-brand",
                type="button",
                onclick="mtNavTo('home')",
                **{"aria-label": "Ga naar home"},
            ),

            # Center: navigation
            ui.tags.div(
                # Profiel analyse ▾
                ui.tags.div(
                    ui.tags.button(
                        "Profiel analyse",
                        ui.tags.span("▾", class_="mt-nav-chevron"),
                        class_="mt-nav-trigger",
                        type="button",
                        onclick="mtToggleDropdown(this)",
                        **{"data-section": "profiel", "aria-haspopup": "true",
                           "aria-expanded": "false"},
                    ),
                    ui.tags.div(
                        _dropdown_link("Circadiaans ritme", "profiel", "Circadiaans ritme"),
                        _dropdown_link("Sessie-replay",     "profiel", "Sessie-replay"),
                        _dropdown_link("Sessie-inzichten",  "profiel", "Sessie-inzichten"),
                        _dropdown_link("Jouw Muziek",       "profiel", "Jouw Muziek"),
                        class_="mt-nav-dropdown-menu",
                        role="menu",
                    ),
                    class_="mt-nav-item mt-nav-dropdown",
                ),

                # Muziekadvies (standalone)
                ui.tags.button(
                    "Muziekadvies",
                    class_="mt-nav-trigger",
                    type="button",
                    onclick="mtNavTo('aanbevelingen')",
                    **{"data-section": "aanbevelingen"},
                ),

                # Hoe het werkt ▾
                ui.tags.div(
                    ui.tags.button(
                        "Hoe het werkt",
                        ui.tags.span("▾", class_="mt-nav-chevron"),
                        class_="mt-nav-trigger",
                        type="button",
                        onclick="mtToggleDropdown(this)",
                        **{"data-section": "achtergrond", "aria-haspopup": "true",
                           "aria-expanded": "false"},
                    ),
                    ui.tags.div(
                        _dropdown_link("Wetenschap",   "achtergrond", "Wetenschap"),
                        _dropdown_link("Model & Data", "achtergrond", "Model & Data"),
                        _dropdown_link("Pipeline",     "achtergrond", "Pipeline"),
                        class_="mt-nav-dropdown-menu",
                        role="menu",
                    ),
                    class_="mt-nav-item mt-nav-dropdown",
                ),

                class_="mt-navbar-center",
            ),

            # Right: participant selector + hamburger
            ui.tags.div(
                ui.tags.label(
                    "Deelnemer:",
                    **{"for": "mt-p-desktop"},
                    class_="mt-nav-participant-label",
                ),
                _participant_opts("mt-p-desktop"),
                ui.tags.button(
                    ui.tags.span("☰", class_="mt-hamburger-icon"),
                    class_="mt-hamburger",
                    id="mt-hamburger-btn",
                    type="button",
                    onclick="mtToggleMobileMenu()",
                    **{"aria-label": "Menu openen", "aria-expanded": "false",
                       "aria-controls": "mt-mobile-menu"},
                ),
                class_="mt-navbar-right",
            ),

            class_="mt-navbar",
            id="mt-custom-navbar",
            **{"aria-label": "Hoofdnavigatie"},
        ),

        # ── Mobile full-screen menu ────────────────────────────────────────
        ui.tags.div(
            ui.tags.div("Jouw profiel", class_="mt-mobile-section-header"),
            *[
                ui.tags.a(
                    lbl, href="#", class_="mt-mobile-link",
                    onclick=f"mtNavTo('profiel','{lbl}'); mtCloseMobileMenu(); return false;",
                )
                for lbl in [
                    "Circadiaans ritme", "Sessie-replay",
                    "Sessie-inzichten", "Jouw Muziek",
                ]
            ],
            ui.tags.hr(class_="mt-mobile-divider"),
            ui.tags.a(
                "Muziekadvies", href="#", class_="mt-mobile-link",
                onclick="mtNavTo('aanbevelingen'); mtCloseMobileMenu(); return false;",
            ),
            ui.tags.hr(class_="mt-mobile-divider"),
            ui.tags.div("Hoe het werkt", class_="mt-mobile-section-header"),
            *[
                ui.tags.a(
                    lbl, href="#", class_="mt-mobile-link",
                    onclick=f"mtNavTo('achtergrond','{lbl}'); mtCloseMobileMenu(); return false;",
                )
                for lbl in ["Wetenschap", "Model & Data", "Pipeline"]
            ],
            ui.tags.hr(class_="mt-mobile-divider"),
            ui.tags.div(
                ui.tags.label("Deelnemer:", class_="mt-nav-participant-label"),
                _participant_opts("mt-p-mobile", extra_style="width:100%;"),
                class_="mt-mobile-participant-row",
            ),
            class_="mt-mobile-menu",
            id="mt-mobile-menu",
            role="dialog",
            **{"aria-label": "Mobiel menu"},
        ),

        # Inline JS (once, outside the nav element)
        inline_js,
    )


# ---------------------------------------------------------------------------
# App UI
# ---------------------------------------------------------------------------

app_ui = ui.page_navbar(
    ui.nav_panel("Home", home.ui("home")),
    ui.nav_panel("Jouw Profiel",
        ui.navset_pill(
            ui.nav_panel("Circadiaans ritme", circadian.ui("circadian")),
            ui.nav_panel("Sessie-replay",     session_replay.ui("replay")),
            ui.nav_panel("Sessie-inzichten",
                ui.div(
                    results.ui("results"),
                    ui.tags.hr(style=(
                        "border:none; border-top:1px solid var(--border-subtle); "
                        "margin:0 var(--page-margin) 8px;"
                    )),
                    recovery.ui("recovery"),
                ),
            ),
            ui.nav_panel("Jouw Muziek",       music_browser.ui("music")),
            id="profiel_pills",
        ),
    ),
    ui.nav_panel("Aanbevelingen", recommendation.ui("rec")),
    ui.nav_panel("Achtergrond",
        ui.navset_pill(
            ui.nav_panel("Wetenschap",   science.ui("science")),
            ui.nav_panel("Model & Data", model.ui("model")),
            ui.nav_panel("Pipeline",     pipeline.ui("pipeline")),
            id="achtergrond_pills",
        ),
    ),
    id="main_nav",
    title=ui.span(),           # Custom navbar provides the brand
    header=ui.div(
        ui.tags.head(
            ui.tags.link(
                rel="icon", type="image/svg+xml",
                # Inline data URI — bypasses browser favicon caching entirely.
                # Vector eighth-note path on transparent background.
                href=(
                    "data:image/svg+xml,"
                    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
                    "%3Cpath fill='%2316a34a' d="
                    "'M20 2v15.27A5 5 0 1 0 23 21V8h4V2H20z'"
                    "/%3E"
                    "%3C/svg%3E"
                ),
            ),
            ui.tags.link(rel="stylesheet", href="styles.css"),
            ui.busy_indicators.use(spinners=True, pulse=True),
        ),
        _build_navbar(),
    ),
    footer=ui.div(
        ui.div(
            ui.output_ui("now_playing_title"),
            class_="now-playing-bar",
        ),
    ),
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

def server(input, output, session):
    selected_participant = reactive.Value("bosbes")
    now_playing          = reactive.Value(None)

    # ── Custom navbar: section + sub-page navigation ──────────────────────
    @reactive.Effect
    @reactive.event(input.mt_nav_goto)
    def _handle_nav():
        nav = input.mt_nav_goto()
        if not nav or not isinstance(nav, dict):
            return
        section = nav.get("section")
        sub     = nav.get("sub")

        _SECTION_TO_TAB = {
            "home":          "Home",
            "profiel":       "Jouw Profiel",
            "aanbevelingen": "Aanbevelingen",
            "achtergrond":   "Achtergrond",
        }
        tab_name = _SECTION_TO_TAB.get(section)
        if tab_name:
            ui.update_navs("main_nav", selected=tab_name, session=session)
        if sub:
            if section == "profiel":
                if sub in ("Resultaten", "Herstelanalyse"):
                    ui.update_navs("profiel_pills", selected="Sessie-inzichten", session=session)
                else:
                    ui.update_navs("profiel_pills", selected=sub, session=session)
            elif section == "achtergrond":
                ui.update_navs("achtergrond_pills", selected=sub, session=session)

    # ── Custom navbar: participant selector ───────────────────────────────
    @reactive.Effect
    @reactive.event(input.mt_participant_nav)
    def _handle_participant():
        p = input.mt_participant_nav()
        if p and p in PARTICIPANTS:
            selected_participant.set(p)

    # ── Module servers ─────────────────────────────────────────────────────
    home.server("home",         app_data=APP_DATA, now_playing=now_playing,
                                selected_participant=selected_participant)
    science.server("science")
    pipeline.server("pipeline",     app_data=APP_DATA)
    circadian.server("circadian",   app_data=APP_DATA, selected_participant=selected_participant)
    recommendation.server("rec",    app_data=APP_DATA, selected_participant=selected_participant)
    session_replay.server("replay", app_data=APP_DATA, selected_participant=selected_participant)
    results.server("results",       app_data=APP_DATA, selected_participant=selected_participant)
    model.server("model",           app_data=APP_DATA)
    recovery.server("recovery",     app_data=APP_DATA, selected_participant=selected_participant)
    music_browser.server("music",   app_data=APP_DATA, selected_participant=selected_participant)

    # ── Now-playing bar ────────────────────────────────────────────────────
    @output
    @render.ui
    def now_playing_title():
        import pandas as pd
        state = now_playing()
        if state is None:
            p        = selected_participant()
            emoji    = _FRUIT_EMOJI.get(p, "🎵")
            data_tip = _DATA_LEVEL_TIP.get(p, "")
            return ui.TagList(
                ui.HTML('<script>(function(){ var b = document.querySelector(".now-playing-bar"); if(b) b.removeAttribute("data-playlist"); })();</script>'),
                ui.div(
                    ui.div(
                        style="width:44px; height:44px; border-radius:6px; flex-shrink:0; "
                              "background:var(--bg-card); border:1px solid var(--border-subtle);",
                    ),
                    ui.HTML('<div class="now-playing-wave"><span></span><span></span><span></span></div>'),
                    ui.div(
                        ui.div("PROJECT R.E.M. · MoodTune", class_="now-playing-title"),
                        ui.div(
                            "Muziek als hulpmiddel voor stressregulatie",
                            class_="now-playing-artist",
                        ),
                        style="min-width:0;",
                    ),
                    class_="now-playing-track",
                ),
                # Center: quick nav links
                ui.div(
                    ui.HTML(
                        '<a href="#" onclick="mtNavTo(\'achtergrond\',\'Wetenschap\'); return false;" '
                        'style="color:var(--text-tertiary); font-size:0.75rem; text-decoration:none; '
                        'margin:0 8px; transition:color 0.15s;" '
                        'onmouseover="this.style.color=\'var(--text-secondary)\'" '
                        'onmouseout="this.style.color=\'var(--text-tertiary)\'">Wetenschap</a>'
                        '<span style="color:var(--border-default);">·</span>'
                        '<a href="#" onclick="mtNavTo(\'achtergrond\',\'Model & Data\'); return false;" '
                        'style="color:var(--text-tertiary); font-size:0.75rem; text-decoration:none; '
                        'margin:0 8px; transition:color 0.15s;" '
                        'onmouseover="this.style.color=\'var(--text-secondary)\'" '
                        'onmouseout="this.style.color=\'var(--text-tertiary)\'">Model & Data</a>'
                        '<span style="color:var(--border-default);">·</span>'
                        '<a href="#" onclick="mtNavTo(\'achtergrond\',\'Pipeline\'); return false;" '
                        'style="color:var(--text-tertiary); font-size:0.75rem; text-decoration:none; '
                        'margin:0 8px; transition:color 0.15s;" '
                        'onmouseover="this.style.color=\'var(--text-secondary)\'" '
                        'onmouseout="this.style.color=\'var(--text-tertiary)\'">Pipeline</a>'
                    ),
                    style="display:flex; align-items:center; gap:2px; justify-content:center;",
                ),
                ui.div(
                    ui.div(
                        ui.span(
                            f"{emoji} {p.capitalize()}",
                            style="font-weight:600; color:var(--text-primary); margin-right:8px;",
                        ),
                        ui.span(data_tip, style="font-size:0.75rem; color:var(--text-tertiary);"),
                        style="margin-bottom:2px;",
                    ),
                    ui.div(
                        ui.HTML(
                            '<span style="font-size:0.75rem; color:var(--text-tertiary);">Geanonimiseerde data · </span>'
                            '<a href="mailto:rem.studie@gmail.com" style="font-size:0.75rem; color:var(--text-tertiary); text-decoration:none;" '
                            'onmouseover="this.style.color=\'var(--text-secondary)\'" onmouseout="this.style.color=\'var(--text-tertiary)\'">rem.studie@gmail.com</a>'
                        ),
                    ),
                    style="text-align:right; flex-shrink:0; align-self:center;",
                ),
            )

        pl_type    = state["playlist_type"]
        pl_lower   = pl_type.lower()
        playlist_nl = {
            "Calm":    "Kalme afspeellijst",
            "Neutral": "Neutrale afspeellijst",
            "Energy":  "Energieke afspeellijst",
        }.get(pl_type, pl_type)

        _COVER_GRAD = {
            "Calm":    "linear-gradient(135deg, #1a2a4a, #0a1525)",
            "Neutral": "linear-gradient(135deg, #2a1a4a, #160a2f)",
            "Energy":  "linear-gradient(135deg, #4a2a1a, #2f1508)",
        }
        _PL_COLORS = {"calm": "#56B4E9", "neutral": "#009E73", "energy": "#E69F00"}

        df = state.get("df")
        if df is not None and not df.empty:
            n_tracks = len(df)
            try:
                total_min = int(pd.to_numeric(df["duration_ms"], errors="coerce").sum() / 60000)
                meta_str  = f"{n_tracks} nrs · {total_min} min"
            except Exception:
                meta_str  = f"{n_tracks} nrs"
        else:
            meta_str = ""

        art_style = (
            f"width:44px; height:44px; border-radius:6px; flex-shrink:0; "
            f"background:{_COVER_GRAD.get(pl_type, _COVER_GRAD['Calm'])}; "
            f"display:flex; align-items:center; justify-content:center; font-size:1.25rem;"
        )
        pl_color = _PL_COLORS.get(pl_lower, "#16a34a")

        js_attr = ui.HTML(
            f'<script>(function(){{ var b = document.querySelector(".now-playing-bar"); '
            f'if(b) b.setAttribute("data-playlist", "{pl_lower}"); }})();</script>'
        )

        return ui.TagList(
            js_attr,
            ui.div(
                ui.span("🎵", style=art_style),
                ui.HTML('<div class="now-playing-wave"><span></span><span></span><span></span></div>'),
                ui.div(
                    ui.div(
                        ui.span(playlist_nl, class_="now-playing-title",
                                style=f"color:{pl_color}; font-weight:600;"),
                    ),
                    ui.div(
                        f"{_FRUIT_EMOJI.get(state['participant'], '')} "
                        f"{state['participant'].capitalize()}"
                        + (f"  ·  {meta_str}" if meta_str else ""),
                        class_="now-playing-artist",
                    ),
                    style="min-width:0;",
                ),
                class_="now-playing-track",
            ),
            ui.div(
                ui.span(
                    f"{_FRUIT_EMOJI.get(state['participant'], '')} "
                    f"{state['participant'].capitalize()}",
                    style="font-size:0.8125rem; color:var(--text-secondary);",
                ),
                style="text-align:right; align-self:center; flex-shrink:0;",
            ),
        )


app = App(app_ui, server, static_assets=Path(__file__).parent / "www")
