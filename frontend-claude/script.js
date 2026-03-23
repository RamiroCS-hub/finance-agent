var WAITLIST_ENDPOINT = "https://formsubmit.co/ajax/ramirocarnicersouble8@gmail.com";

function isValidEmail(email) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function submitToWaitlist(email) {
  var body = new FormData();
  body.append("email", email);
  body.append("_replyto", email);
  body.append("_subject", "Nueva inscripcion en la waitlist de Anotamelo");
  body.append("_template", "table");
  body.append("_captcha", "false");
  body.append("origen", window.location.href);
  body.append("user_agent", navigator.userAgent || "");

  return fetch(WAITLIST_ENDPOINT, {
    method: "POST",
    headers: {
      Accept: "application/json"
    },
    body: body
  }).then(function (response) {
    return response.json().catch(function () {
      return {};
    }).then(function (data) {
      var failed = !response.ok || data.success === false || data.success === "false";
      if (failed) {
        throw new Error(data && data.message ? data.message : "No se pudo enviar tu inscripcion.");
      }
      return data;
    });
  });
}

function initWaitlistForm() {
  var form = document.getElementById("waitlist-form");
  if (!form) return;

  form.addEventListener("submit", function (event) {
    event.preventDefault();

    var emailInput = document.getElementById("email-input");
    var successDiv = document.getElementById("waitlist-success");
    var errorDiv = document.getElementById("waitlist-error");
    var btnText = form.querySelector(".btn-text");
    var btnLoading = form.querySelector(".btn-loading");
    var email = emailInput.value.trim().toLowerCase();

    errorDiv.hidden = true;
    errorDiv.textContent = "";

    if (!isValidEmail(email)) {
      errorDiv.hidden = false;
      errorDiv.textContent = "Ingresá un email válido.";
      emailInput.focus();
      return;
    }

    btnText.hidden = true;
    btnLoading.hidden = false;

    submitToWaitlist(email)
      .then(function () {
        form.hidden = true;
        successDiv.hidden = false;
      })
      .catch(function (error) {
        errorDiv.hidden = false;
        errorDiv.textContent = error.message || "No se pudo guardar tu email.";
      })
      .finally(function () {
        btnText.hidden = false;
        btnLoading.hidden = true;
      });
  });
}

function initSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach(function (link) {
    link.addEventListener("click", function (event) {
      var targetId = this.getAttribute("href");
      if (!targetId || targetId === "#") return;

      var target = document.querySelector(targetId);
      if (!target) return;

      event.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

function initMobileMenu() {
  var button = document.querySelector(".mobile-menu-btn");
  var links = document.querySelector(".nav-links");
  if (!button || !links) return;

  button.addEventListener("click", function () {
    var isOpen = links.classList.toggle("is-open");
    button.setAttribute("aria-expanded", String(isOpen));
  });

  links.querySelectorAll("a").forEach(function (link) {
    link.addEventListener("click", function () {
      links.classList.remove("is-open");
      button.setAttribute("aria-expanded", "false");
    });
  });
}

function initScrollAnimations() {
  var animated = document.querySelectorAll(".animate-on-scroll");
  if (!animated.length || typeof IntersectionObserver === "undefined") {
    animated.forEach(function (element) {
      element.classList.add("visible");
    });
    return;
  }

  var observer = new IntersectionObserver(function (entries) {
    entries.forEach(function (entry) {
      if (entry.isIntersecting) {
        entry.target.classList.add("visible");
        observer.unobserve(entry.target);
      }
    });
  }, {
    threshold: 0.15,
    rootMargin: "0px 0px -20px 0px"
  });

  animated.forEach(function (element) {
    observer.observe(element);
  });
}

document.addEventListener("DOMContentLoaded", function () {
  initWaitlistForm();
  initSmoothScroll();
  initMobileMenu();
  initScrollAnimations();
});
