(function () {
  const storageKey = "household-finance-theme";

  function preferredTheme() {
    try {
      const savedTheme = window.localStorage.getItem(storageKey);
      if (savedTheme === "light" || savedTheme === "dark") {
        return savedTheme;
      }
    } catch (error) {
      // Storage can be unavailable in strict privacy modes.
    }

    return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches
      ? "dark"
      : "light";
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
  }

  applyTheme(preferredTheme());

  document.addEventListener("DOMContentLoaded", function () {
    const toggle = document.getElementById("themeToggle");
    if (!toggle) {
      return;
    }

    function updateToggle() {
      const darkMode = document.documentElement.getAttribute("data-theme") === "dark";
      const icon = toggle.querySelector("i");
      const label = toggle.querySelector("span");

      toggle.setAttribute("aria-pressed", String(darkMode));
      icon.className = darkMode ? "fas fa-sun fa-sm" : "fas fa-moon fa-sm";
      label.textContent = darkMode ? "Light mode" : "Dark mode";
    }

    toggle.addEventListener("click", function () {
      const currentTheme = document.documentElement.getAttribute("data-theme");
      const nextTheme = currentTheme === "dark" ? "light" : "dark";
      applyTheme(nextTheme);

      try {
        window.localStorage.setItem(storageKey, nextTheme);
      } catch (error) {
        // The visual toggle still works when storage is unavailable.
      }

      updateToggle();
    });

    updateToggle();
  });
})();
