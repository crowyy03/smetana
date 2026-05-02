// Клавиатурная навигация и подтверждение позиций сметы.

(function () {
  "use strict";

  function $$(sel, root) { return Array.from((root || document).querySelectorAll(sel)); }

  function rows() { return $$("[data-row-id]"); }

  function setActive(id) {
    rows().forEach((r) => {
      const isActive = r.dataset.rowId === String(id);
      r.dataset.active = isActive ? "true" : "false";
      if (isActive) {
        const input = r.querySelector("[data-price-input]");
        if (input) {
          input.focus({ preventScroll: false });
          input.select();
        }
        r.scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    });
  }

  function nextUnconfirmed(currentId) {
    const list = rows();
    const i = list.findIndex((r) => r.dataset.rowId === String(currentId));
    for (let j = i + 1; j < list.length; j++) {
      if (list[j].dataset.confirmed !== "true") return list[j].dataset.rowId;
    }
    for (let j = 0; j < i; j++) {
      if (list[j].dataset.confirmed !== "true") return list[j].dataset.rowId;
    }
    return null;
  }

  function neighbour(currentId, dir) {
    const list = rows();
    const i = list.findIndex((r) => r.dataset.rowId === String(currentId));
    const next = list[i + dir];
    return next ? next.dataset.rowId : null;
  }

  function rowOf(input) {
    return input.closest("[data-row-id]");
  }

  // делегирование клавиатуры
  document.addEventListener("keydown", function (ev) {
    const target = ev.target;
    if (!(target instanceof HTMLElement)) return;
    const row = rowOf(target);

    // Cmd/Ctrl+Enter — bulk-confirm всех auto-позиций
    if ((ev.metaKey || ev.ctrlKey) && ev.key === "Enter") {
      const btn = document.querySelector("[data-bulk-confirm]");
      if (btn) {
        ev.preventDefault();
        btn.click();
      }
      return;
    }

    if (!row) return;
    const id = row.dataset.rowId;

    if (ev.key === "Enter" && !ev.shiftKey) {
      // submit подтверждение текущей строки
      const form = row.querySelector("form[data-confirm-form]");
      if (form) {
        ev.preventDefault();
        form.requestSubmit();
      }
      return;
    }

    if (ev.key === "Escape") {
      ev.preventDefault();
      target.blur && target.blur();
      return;
    }

    if (ev.key === "ArrowDown" && !target.matches("textarea")) {
      const n = neighbour(id, +1);
      if (n) { ev.preventDefault(); setActive(n); }
    }
    if (ev.key === "ArrowUp" && !target.matches("textarea")) {
      const n = neighbour(id, -1);
      if (n) { ev.preventDefault(); setActive(n); }
    }
  });

  // клик по строке → активная
  document.addEventListener("click", function (ev) {
    const row = (ev.target instanceof HTMLElement) ? ev.target.closest("[data-row-id]") : null;
    if (row && !ev.target.closest("button, a, input, textarea")) {
      setActive(row.dataset.rowId);
    }
  });

  // после htmx swap для строки — оживляем settle-анимацию и активируем следующую неподтверждённую
  document.body.addEventListener("htmx:afterSwap", function (ev) {
    const targetEl = ev.target;
    if (!(targetEl instanceof HTMLElement)) return;
    const row = targetEl.closest("[data-row-id]") || targetEl.querySelector("[data-row-id]");
    if (row) {
      row.classList.remove("row-commit-settle");
      // force reflow to restart animation
      void row.offsetWidth;
      row.classList.add("row-commit-settle");
      if (row.dataset.confirmed === "true") {
        const next = nextUnconfirmed(row.dataset.rowId);
        if (next) setActive(next);
      }
      updateProgress();
    }
  });

  function updateProgress() {
    const all = rows();
    if (!all.length) return;
    const done = all.filter((r) => r.dataset.confirmed === "true").length;
    const pct = Math.round((done / all.length) * 100);
    const fill = document.querySelector("[data-progress-fill]");
    if (fill) fill.style.width = pct + "%";
    const counter = document.querySelector("[data-progress-counter]");
    if (counter) counter.textContent = `${done} из ${all.length}`;
    const finishBtn = document.querySelector("[data-finish-btn]");
    if (finishBtn) finishBtn.toggleAttribute("disabled", done < all.length);
  }

  document.addEventListener("DOMContentLoaded", () => {
    updateProgress();
    // активируем первую неподтверждённую при загрузке
    const list = rows();
    const first = list.find((r) => r.dataset.confirmed !== "true");
    if (first) setActive(first.dataset.rowId);

    // submit-state у кнопки финализации (PDF может рендериться 5-10 сек)
    const form = document.querySelector("[data-finalize-form]");
    if (form) {
      form.addEventListener("submit", () => {
        const btn = form.querySelector("[data-finish-btn]");
        if (btn) btn.setAttribute("disabled", "");
        const label = form.querySelector("[data-finish-label]");
        const busy = form.querySelector("[data-finish-busy]");
        if (label) label.hidden = true;
        if (busy) busy.hidden = false;
      });
    }
  });
})();
