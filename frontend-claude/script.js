/* ========================================
   Tesorero Landing — Waitlist Logic
   ======================================== */

var STORAGE_KEY = 'waitlist_submissions';

// ---- Helpers ----

function getSubmissions() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch (e) {
    return [];
  }
}

function saveSubmissions(submissions) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(submissions));
}

function updateCount() {
  var el = document.getElementById('submissions-count');
  if (el) el.textContent = getSubmissions().length;
}

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

// ---- Waitlist Form ----

function initWaitlistForm() {
  var form = document.getElementById('waitlist-form');
  if (!form) return;

  updateCount();

  form.addEventListener('submit', function (e) {
    e.preventDefault();

    var emailInput = document.getElementById('email-input');
    var successDiv = document.getElementById('waitlist-success');
    var errorDiv = document.getElementById('waitlist-error');
    var btnText = form.querySelector('.btn-text');
    var btnLoading = form.querySelector('.btn-loading');

    errorDiv.hidden = true;
    errorDiv.textContent = '';

    var email = emailInput.value.trim().toLowerCase();

    if (!isValidEmail(email)) {
      errorDiv.textContent = 'Ingresá un email válido.';
      errorDiv.hidden = false;
      return;
    }

    // Check duplicates
    var submissions = getSubmissions();
    if (submissions.some(function (s) { return s.email === email; })) {
      errorDiv.textContent = 'Este email ya está en la waitlist.';
      errorDiv.hidden = false;
      return;
    }

    // Simulate saving (tiny delay for UX)
    btnText.hidden = true;
    btnLoading.hidden = false;

    setTimeout(function () {
      submissions.push({
        email: email,
        timestamp: new Date().toISOString(),
      });
      saveSubmissions(submissions);
      updateCount();

      // Show success, hide form
      form.hidden = true;
      successDiv.hidden = false;

      btnText.hidden = false;
      btnLoading.hidden = true;
    }, 600);
  });
}

// ---- Smooth scroll ----

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener('click', function (e) {
      var targetId = this.getAttribute('href');
      if (targetId === '#') return;

      var target = document.querySelector(targetId);
      if (!target) return;

      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  });
}

// ---- Mobile menu ----

function initMobileMenu() {
  var btn = document.querySelector('.mobile-menu-btn');
  var links = document.querySelector('.nav-links');
  if (!btn || !links) return;

  btn.addEventListener('click', function () {
    var isOpen = links.style.display === 'flex';
    links.style.display = isOpen ? 'none' : 'flex';
    links.style.flexDirection = 'column';
    links.style.position = 'absolute';
    links.style.top = '64px';
    links.style.right = '24px';
    links.style.background = 'white';
    links.style.padding = '16px 24px';
    links.style.borderRadius = '12px';
    links.style.boxShadow = '0 8px 32px rgba(0,0,0,0.12)';
    links.style.gap = '12px';

    if (isOpen) {
      links.removeAttribute('style');
      if (window.innerWidth <= 768) {
        links.style.display = 'none';
      }
    }
  });

  // Close on link click
  links.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.innerWidth <= 768) {
        links.removeAttribute('style');
        links.style.display = 'none';
      }
    });
  });
}

// ---- Scroll animations ----

function initScrollAnimations() {
  var observer = new IntersectionObserver(
    function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
        }
      });
    },
    { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
  );

  document.querySelectorAll(
    '.feature-card, .step, .demo-card, .waitlist-card, .groups-feature-item, .groups-visual'
  ).forEach(function (el) {
    el.classList.add('animate-on-scroll');
    observer.observe(el);
  });
}

// CSS for scroll animations (injected)
(function () {
  var style = document.createElement('style');
  style.textContent =
    '.animate-on-scroll { opacity: 0; transform: translateY(20px); transition: opacity 0.5s ease, transform 0.5s ease; }' +
    '.animate-on-scroll.visible { opacity: 1; transform: translateY(0); }';
  document.head.appendChild(style);
})();

// ---- Init ----

document.addEventListener('DOMContentLoaded', function () {
  initWaitlistForm();
  initSmoothScroll();
  initMobileMenu();
  initScrollAnimations();
});
