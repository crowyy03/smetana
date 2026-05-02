// Shadow-loom theme switcher.
// Светлая «бумага» ↔ тёмная «тушь и металл» с радиальным reveal от точки клика.

(function () {
  "use strict";

  const STORAGE_KEY = "vilins-theme";
  const COOKIE_KEY = "vilins_theme";
  const root = document.documentElement;

  function readSystem() {
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "night" : "day";
  }

  function readPersisted() {
    try {
      const v = localStorage.getItem(STORAGE_KEY);
      if (v === "day" || v === "night" || v === "system") return v;
    } catch (e) { /* SSR / privacy mode */ }
    return null;
  }

  function persist(value) {
    try { localStorage.setItem(STORAGE_KEY, value); } catch (e) { /* ignore */ }
    document.cookie = `${COOKIE_KEY}=${value}; Path=/; Max-Age=${60 * 60 * 24 * 365}; SameSite=Lax`;
  }

  function effective(value) {
    return value === "system" ? readSystem() : value;
  }

  function apply(value) {
    const eff = effective(value);
    root.setAttribute("data-theme", eff);
    // обновляем aria и иконки у всех toggle-кнопок
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.setAttribute("aria-pressed", eff === "night" ? "true" : "false");
      const sun = btn.querySelector("[data-theme-icon='sun']");
      const moon = btn.querySelector("[data-theme-icon='moon']");
      if (sun && moon) {
        sun.style.display = eff === "night" ? "none" : "";
        moon.style.display = eff === "night" ? "" : "none";
      }
    });
  }

  function prefersReducedMotion() {
    return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  function loomTo(next, originX, originY) {
    // координаты передаём в CSS, чтобы маска расходилась от точки клика.
    root.style.setProperty("--theme-x", originX + "px");
    root.style.setProperty("--theme-y", originY + "px");

    const supportsVT = typeof document.startViewTransition === "function";

    if (!supportsVT || prefersReducedMotion()) {
      apply(next);
      return;
    }

    root.classList.add("is-theme-switching");
    const tx = document.startViewTransition(() => apply(next));
    tx.finished.finally(() => {
      root.classList.remove("is-theme-switching");
    });
  }

  function init() {
    // первичное применение — на случай если cookie/SSR упустил.
    const stored = readPersisted();
    const initial = stored || "system";
    apply(initial);

    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", (ev) => {
        const rect = btn.getBoundingClientRect();
        const x = rect.left + rect.width / 2;
        const y = rect.top + rect.height / 2;
        const current = effective(readPersisted() || "system");
        const next = current === "night" ? "day" : "night";
        persist(next);
        loomTo(next, x, y);
      });
    });

    // если пользователь выбрал "system" и системная тема меняется — реагируем.
    if (window.matchMedia) {
      const mq = window.matchMedia("(prefers-color-scheme: dark)");
      const onChange = () => {
        if (readPersisted() === "system") apply("system");
      };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
      else if (mq.addListener) mq.addListener(onChange);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
