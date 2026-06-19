(function () {
'use strict';

/* ── Sub-nav configuration ───────────────────────────────────────────────── */
var _MT_SUBNAV = {
  profiel:     ['Circadiaans ritme', 'Sessie-replay', 'Sessie-inzichten', 'Jouw Muziek'],
  achtergrond: ['Wetenschap', 'Model & Data', 'Pipeline'],
};
var _curSection = 'home';
var _curSub     = null;

/* ── Navigation ──────────────────────────────────────────────────────────── */
window.mtNavTo = function (section, sub) {
  if (window.Shiny && Shiny.setInputValue) {
    Shiny.setInputValue('mt_nav_goto', {section: section, sub: sub || null}, {priority: 'event'});
  }
  // Highlight the matching trigger
  document.querySelectorAll('.mt-nav-trigger').forEach(function (el) {
    el.classList.toggle('active', el.getAttribute('data-section') === section);
  });
  _mtCloseDropdowns();
  // Track state and update embedded sub-nav
  _curSection = section;
  _curSub     = sub || (_MT_SUBNAV[section] ? _MT_SUBNAV[section][0] : null);
  _mtUpdateSubnav(section, _curSub);
  // Home class only needed for home-specific transparent-container overrides
  document.body.classList.toggle('mt-home-active', section === 'home');
  // Suppress emoji on "Hoe het werkt" section
  document.body.classList.toggle('mt-no-emoji', section === 'achtergrond');
  // Re-trigger emoji pop-in on every non-achtergrond page change
  if (section !== 'achtergrond') {
    var emojiEl = document.getElementById('home-emoji-bg');
    if (emojiEl) {
      emojiEl.classList.remove('pop-in');
      void emojiEl.offsetWidth;
      emojiEl.classList.add('pop-in');
    }
  }
};

/* ── Dropdown trigger — click navigates to first sub-page ────────────────── */
window.mtToggleDropdown = function (btn) {
  var section = btn.getAttribute('data-section');
  var subs    = _MT_SUBNAV[section];
  if (subs && subs.length) {
    mtNavTo(section, subs[0]);
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

/* ── Sub-nav row management ──────────────────────────────────────────────── */
function _mtUpdateSubnav(section, activeSub) {
  var subnav = document.getElementById('mt-subnav');
  if (!subnav) return;
  var hasSubnav = !!_MT_SUBNAV[section];

  // Show/hide correct group; update active pill within it
  subnav.querySelectorAll('.mt-subnav-group').forEach(function (g) {
    var match = g.getAttribute('data-section') === section;
    g.classList.toggle('active', match);
    if (match && activeSub) {
      g.querySelectorAll('.mt-subnav-pill').forEach(function (p) {
        p.classList.toggle('active', p.getAttribute('data-sub') === activeSub);
      });
    }
  });

  // Toggle subnav visibility + body class (body class drives content offset + hides Bootstrap pills)
  subnav.classList.toggle('visible', hasSubnav);
  document.body.classList.toggle('mt-subnav-active', hasSubnav);
}

/* ── Participant selector ────────────────────────────────────────────────── */
var _MT_EMOJI = {bosbes:'🫐',kokosnoot:'🥥',limoen:'🍋',peer:'🍐',kiwi:'🥝',watermeloen:'🍉'};

window.mtSelectParticipant = function (val) {
  if (window.Shiny && Shiny.setInputValue) {
    Shiny.setInputValue('mt_participant_nav', val, {priority: 'event'});
  }
  var el = document.getElementById('home-emoji-bg');
  if (el) {
    el.textContent = _MT_EMOJI[val] || '🎵';
    el.classList.remove('pop-in');
    void el.offsetWidth;
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
  document.body.classList.add('mt-home-active');

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

  // Ensure sub-nav starts hidden (home page default)
  _mtUpdateSubnav('home', null);

  // Reverse map: sub-tab label → section
  var _SUB_TO_SECTION = {};
  Object.keys(_MT_SUBNAV).forEach(function (sec) {
    _MT_SUBNAV[sec].forEach(function (sub) { _SUB_TO_SECTION[sub] = sec; });
  });

  var _MAIN_TAB = {
    'Home': 'home', 'Jouw Profiel': 'profiel',
    'Aanbevelingen': 'aanbevelingen', 'Achtergrond': 'achtergrond',
  };

  document.addEventListener('shown.bs.tab', function (e) {
    if (!e.target) return;
    var label = e.target.textContent.trim();

    if (_MAIN_TAB[label]) {
      // Main section tab changed
      var sec = _MAIN_TAB[label];
      document.querySelectorAll('.mt-nav-trigger').forEach(function (el) {
        el.classList.toggle('active', el.getAttribute('data-section') === sec);
      });
      _curSection = sec;
      // Only reset sub if the current sub doesn't belong to this section
      if (!_curSub || _SUB_TO_SECTION[_curSub] !== sec) {
        _curSub = _MT_SUBNAV[sec] ? _MT_SUBNAV[sec][0] : null;
      }
      _mtUpdateSubnav(sec, _curSub);
      document.body.classList.toggle('mt-home-active', sec === 'home');
      document.body.classList.toggle('mt-no-emoji', sec === 'achtergrond');
      // Re-trigger emoji pop-in on all non-achtergrond sections
      if (sec !== 'achtergrond') {
        var _emojiEl = document.getElementById('home-emoji-bg');
        if (_emojiEl) { _emojiEl.classList.remove('pop-in'); void _emojiEl.offsetWidth; _emojiEl.classList.add('pop-in'); }
      }

    } else if (_SUB_TO_SECTION[label]) {
      // Sub-tab changed (e.g., from Bootstrap pills or Shiny update_navset)
      _curSub = label;
      _mtUpdateSubnav(_curSection, label);
    }
  });
});

/* ── Emoji scroll-fade ────────────────────────────────────────────────────── */
(function () {
  var FADE_END     = 450;
  var BASE_OPACITY = 0.12;   /* matches emojiSpring keyframe target opacity */
  var _prevY       = -1;

  function _applyFade(y) {
    var el = document.getElementById('home-emoji-bg');
    if (!el) return;
    /* Suppress emoji on "Hoe het werkt" section */
    if (document.body.classList.contains('mt-no-emoji')) {
      el.style.setProperty('opacity', '0', 'important');
      return;
    }
    var t = Math.min(1, Math.max(0, y / FADE_END));
    el.style.setProperty('opacity', String(BASE_OPACITY * (1 - t)), 'important');
  }

  function _tick() {
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    if (y !== _prevY) { _prevY = y; _applyFade(y); }
    requestAnimationFrame(_tick);
  }
  requestAnimationFrame(_tick);

  window.addEventListener('scroll', function () {
    var y = window.scrollY || document.documentElement.scrollTop || 0;
    _applyFade(y);
  }, { passive: true });

  document.addEventListener('shown.bs.tab', function () {
    window.scrollTo({ top: 0, behavior: 'instant' });
    _prevY = 0;
    // Defer until after the mt-home-active toggle (listener registration order)
    requestAnimationFrame(function () { _applyFade(0); });
  });
})();

})();
