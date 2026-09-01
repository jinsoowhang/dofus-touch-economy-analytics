"use strict";

const recipeScrollStorageKey = "dofus-recipes-scroll-position";

window.addEventListener("load", () => {
  let savedScrollPosition = null;
  try {
    savedScrollPosition = window.sessionStorage.getItem(recipeScrollStorageKey);
    window.sessionStorage.removeItem(recipeScrollStorageKey);
  } catch {
    return;
  }
  if (savedScrollPosition === null) {
    return;
  }
  const scrollPosition = Number(savedScrollPosition);
  if (Number.isFinite(scrollPosition) && scrollPosition >= 0) {
    window.requestAnimationFrame(() => window.scrollTo(0, scrollPosition));
  }
});

for (const form of document.querySelectorAll(".recipe-current-price-form")) {
  const input = form.querySelector('input[name="current_price"]');
  if (!input) {
    continue;
  }

  const savePrice = () => {
    if (form.dataset.submitting === "true") {
      return;
    }
    if (input.value.trim() === input.dataset.initialValue) {
      return;
    }
    if (!input.reportValidity()) {
      return;
    }
    try {
      window.sessionStorage.setItem(recipeScrollStorageKey, String(window.scrollY));
    } catch {
      // The recipe-catalog fragment remains the fallback when storage is unavailable.
    }
    form.requestSubmit();
  };

  form.addEventListener("submit", () => {
    form.dataset.submitting = "true";
  });
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      savePrice();
    }
  });
  input.addEventListener("blur", savePrice);
}
