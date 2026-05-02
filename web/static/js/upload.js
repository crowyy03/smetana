// Drag-n-drop вложений + переключение между upload и paste-text.

(function () {
  "use strict";

  function init() {
    const dz = document.querySelector("[data-dropzone]");
    if (!dz) return;
    const fileInput = dz.querySelector("input[type=file]");
    const form = document.querySelector("[data-upload-form]");

    ["dragenter", "dragover"].forEach((evt) => {
      dz.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        dz.dataset.dragging = "true";
      });
    });

    ["dragleave", "drop"].forEach((evt) => {
      dz.addEventListener(evt, (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (evt === "dragleave" && dz.contains(e.relatedTarget)) return;
        dz.dataset.dragging = "false";
      });
    });

    dz.addEventListener("drop", (e) => {
      e.preventDefault();
      const files = e.dataTransfer && e.dataTransfer.files;
      if (!files || !files.length) return;
      fileInput.files = files;
      if (form) {
        form.requestSubmit();
      }
    });

    dz.addEventListener("click", (e) => {
      if (e.target.matches("input, button, a")) return;
      fileInput.click();
    });

    if (fileInput) {
      fileInput.addEventListener("change", () => {
        if (fileInput.files && fileInput.files.length && form) {
          form.requestSubmit();
        }
      });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
