/**
 * TRUST Protocol Landing Page
 * Ring draw animation + scroll-triggered section reveals
 */
(function () {
  'use strict';

  var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /**
   * Ring draw animation using stroke-dasharray/stroke-dashoffset.
   * Each ring draws in sequentially from NOVICE (innermost) to SACRED (outermost).
   * The fingerprint/eye fades in after the last ring completes.
   */
  function initRingAnimation() {
    var rings = document.querySelectorAll('.tp-ring');
    var fingerprint = document.querySelector('.tp-fingerprint');

    if (!rings.length) return;

    // Delays for sequential draw (seconds)
    var delays = [0, 0.3, 0.6, 0.9, 1.2];

    rings.forEach(function (ring, i) {
      var len;
      try {
        len = ring.getTotalLength();
      } catch (e) {
        // Fallback: estimate from arc parameters
        len = 500;
      }

      ring.style.strokeDasharray = len;

      if (prefersReducedMotion) {
        ring.style.strokeDashoffset = '0';
      } else {
        ring.style.strokeDashoffset = len;
        ring.style.transition = 'stroke-dashoffset 1.8s cubic-bezier(0.16, 1, 0.3, 1) ' + delays[i] + 's';
      }
    });

    if (prefersReducedMotion) {
      if (fingerprint) fingerprint.style.opacity = '0.9';
      return;
    }

    // Trigger animation after paint
    requestAnimationFrame(function () {
      setTimeout(function () {
        rings.forEach(function (ring) {
          ring.style.strokeDashoffset = '0';
        });
        if (fingerprint) {
          setTimeout(function () {
            fingerprint.style.transition = 'opacity 0.8s ease-in';
            fingerprint.style.opacity = '0.9';
          }, 2000);
        }
      }, 300);
    });
  }

  /**
   * Scroll-triggered fade-in for content sections.
   * Uses IntersectionObserver for performance.
   */
  function initScrollReveal() {
    if (prefersReducedMotion) return;

    var sections = document.querySelectorAll('.tp-section');
    if (!sections.length) return;

    sections.forEach(function (section) {
      section.style.opacity = '0';
      section.style.transform = 'translateY(24px)';
      section.style.transition = 'opacity 0.6s ease-out, transform 0.6s ease-out';
    });

    if (!('IntersectionObserver' in window)) {
      // Fallback: show everything
      sections.forEach(function (section) {
        section.style.opacity = '1';
        section.style.transform = 'translateY(0)';
      });
      return;
    }

    var observer = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.08, rootMargin: '0px 0px -40px 0px' }
    );

    sections.forEach(function (section) {
      observer.observe(section);
    });
  }

  // Initialize when DOM is ready
  function init() {
    initRingAnimation();
    initScrollReveal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
