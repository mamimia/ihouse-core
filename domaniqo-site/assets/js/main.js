/* ═══════════════════════════════════════════════════════════
   DOMANIQO — domaniqo.com
   Main JavaScript — Splash Animation + Scroll Reveal
   ═══════════════════════════════════════════════════════════ */

(function () {
  'use strict';

  // ── SPLASH ANIMATION ──
  // Exact timing from domaniqo-splash-v3.jsx
  var sp  = document.getElementById('splash');
  var sm  = document.getElementById('smono');
  var sr  = document.getElementById('srot');
  var bo  = document.getElementById('bo');
  var bv  = document.getElementById('bv');
  var bh  = document.getElementById('bh');
  var ba  = document.getElementById('ba');
  var wl  = document.querySelectorAll('.wl');
  var tr  = document.querySelectorAll('.tr');
  var sbn = document.getElementById('sbn');
  var sdv = document.getElementById('sdv');
  var stg = document.getElementById('stg');
  var ssp = document.getElementById('ssp');

  // Phase 0 (150ms): Fade in — D visible rotated as house
  setTimeout(function () {
    sm.classList.add('v');
  }, 150);

  // Phase 1 (900ms): Windows show — house hold begins
  setTimeout(function () {
    wl.forEach(function (w) { w.classList.add('s'); });
  }, 900);

  // Phase 2 (2700ms): Morph — windows fade, rotation begins, traces start
  setTimeout(function () {
    wl.forEach(function (w) { w.classList.remove('s'); });
    sr.classList.add('morph');
    tr.forEach(function (t) { t.classList.add('a'); });
  }, 2700);

  // Phase 3 (4200ms): Settled — base D full, settle glow
  setTimeout(function () {
    bo.style.opacity = '1';
    bv.style.opacity = '1';
    bh.style.opacity = '1';
    ba.style.opacity = '1';
    sr.classList.add('set');
  }, 4200);

  // Phase 4 (5200ms): Brand reveal
  setTimeout(function () {
    sbn.classList.add('s');
    sdv.classList.add('s');
    stg.classList.add('s');
    ssp.classList.add('s');
  }, 5200);

  // Phase 5 (6800ms): Fade out splash, reveal page
  setTimeout(function () {
    sp.classList.add('out');
    document.body.classList.remove('splash-active');
    document.getElementById('mn').classList.add('v');
  }, 6800);

  // Remove splash from DOM after fade, trigger hero reveals
  setTimeout(function () {
    sp.style.display = 'none';
    document.querySelectorAll('.hero .rv').forEach(function (el, i) {
      setTimeout(function () { el.classList.add('v'); }, i * 150);
    });
  }, 7400);


  // ── SCROLL REVEAL ──
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('v');
        }
      });
    },
    { threshold: 0.12, rootMargin: '0px 0px -50px 0px' }
  );

  document.querySelectorAll('.rv:not(.hero .rv)').forEach(function (el) {
    observer.observe(el);
  });


  // ── SMOOTH SCROLL ──
  document.querySelectorAll('a[href^="#"]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var target = document.querySelector(a.getAttribute('href'));
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    });
  });

})();
