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
  initSmoothScroll();
  initMobileMenu();
  initScrollAnimations();
});
