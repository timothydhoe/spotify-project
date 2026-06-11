(function () {
  'use strict';
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) {
      if (e.isIntersecting) {
        e.target.classList.remove('mt-reveal');
        e.target.classList.add('mt-revealed');
        obs.unobserve(e.target);
      }
    });
  }, { threshold: 0.06 });
  function _attach() {
    document.querySelectorAll('.mt-section-card:not(.mt-revealed)').forEach(function (el) {
      el.classList.add('mt-reveal');
      obs.observe(el);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', _attach);
  } else {
    _attach();
  }
  // Re-attach when Shiny re-renders (tab switches, reactive updates)
  document.addEventListener('shiny:value', function () { setTimeout(_attach, 80); });
})();
