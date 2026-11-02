/**
 * Platform Theme Interactivity
 */
document.addEventListener("DOMContentLoaded", function () {
  // Dynamic navbar scroll blur effect
  const navbar = document.querySelector(".navbar-custom");
  if (navbar) {
    window.addEventListener("scroll", function () {
      if (window.scrollY > 20) {
        navbar.style.borderBottomColor = "rgba(0, 240, 255, 0.25)";
        navbar.style.boxShadow = "0 8px 30px -4px rgba(0, 0, 0, 0.7)";
      } else {
        navbar.style.borderBottomColor = "rgba(148, 163, 184, 0.15)";
        navbar.style.boxShadow = "0 4px 20px -2px rgba(0, 0, 0, 0.5)";
      }
    });
  }

  // Interactive mouse-glow effect on challenge buttons and cards
  document.querySelectorAll(".card, .challenge-button").forEach(function (card) {
    card.addEventListener("mousemove", function (e) {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty("--mouse-x", `${x}px`);
      card.style.setProperty("--mouse-y", `${y}px`);
    });
  });
});
