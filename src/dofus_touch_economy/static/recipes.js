"use strict";

const minimumLevel = document.querySelector("#recipe-min-level");
const maximumLevel = document.querySelector("#recipe-max-level");
const minimumLevelNumber = document.querySelector("#recipe-min-level-number");
const maximumLevelNumber = document.querySelector("#recipe-max-level-number");
const levelRangeSlider = document.querySelector(".dual-range-slider");

if (
  minimumLevel &&
  maximumLevel &&
  minimumLevelNumber &&
  maximumLevelNumber &&
  levelRangeSlider
) {
  const renderTrack = (changedInput) => {
    const availableMinimum = Number(minimumLevel.min);
    const availableMaximum = Number(maximumLevel.max);
    const availableSpan = availableMaximum - availableMinimum;
    const minimumPosition =
      availableSpan === 0
        ? 0
        : ((Number(minimumLevel.value) - availableMinimum) / availableSpan) * 100;
    const maximumPosition =
      availableSpan === 0
        ? 100
        : ((Number(maximumLevel.value) - availableMinimum) / availableSpan) * 100;
    levelRangeSlider.style.setProperty("--range-minimum-position", `${minimumPosition}%`);
    levelRangeSlider.style.setProperty("--range-maximum-position", `${maximumPosition}%`);

    minimumLevel.setAttribute("aria-valuetext", `Minimum level ${minimumLevel.value}`);
    maximumLevel.setAttribute("aria-valuetext", `Maximum level ${maximumLevel.value}`);
    minimumLevel.style.zIndex = changedInput === minimumLevel ? "3" : "2";
    maximumLevel.style.zIndex = changedInput === maximumLevel ? "3" : "2";
  };

  const syncNumberInputs = () => {
    minimumLevelNumber.value = minimumLevel.value;
    maximumLevelNumber.value = maximumLevel.value;
  };

  const updateFromRange = (changedInput) => {
    if (Number(minimumLevel.value) > Number(maximumLevel.value)) {
      if (changedInput === minimumLevel) {
        maximumLevel.value = minimumLevel.value;
      } else {
        minimumLevel.value = maximumLevel.value;
      }
    }
    syncNumberInputs();
    renderTrack(changedInput);
  };

  const updateFromNumber = (numberInput, rangeInput, commit) => {
    if (numberInput.value === "" || !numberInput.checkValidity()) {
      return;
    }
    rangeInput.value = numberInput.value;
    if (commit) {
      if (
        rangeInput === minimumLevel &&
        Number(rangeInput.value) > Number(maximumLevel.value)
      ) {
        rangeInput.value = maximumLevel.value;
      }
      if (
        rangeInput === maximumLevel &&
        Number(rangeInput.value) < Number(minimumLevel.value)
      ) {
        rangeInput.value = minimumLevel.value;
      }
      numberInput.value = rangeInput.value;
    }
    renderTrack(rangeInput);
  };

  minimumLevel.addEventListener("input", () => updateFromRange(minimumLevel));
  maximumLevel.addEventListener("input", () => updateFromRange(maximumLevel));
  minimumLevelNumber.addEventListener("input", () =>
    updateFromNumber(minimumLevelNumber, minimumLevel, false),
  );
  maximumLevelNumber.addEventListener("input", () =>
    updateFromNumber(maximumLevelNumber, maximumLevel, false),
  );
  minimumLevelNumber.addEventListener("change", () =>
    updateFromNumber(minimumLevelNumber, minimumLevel, true),
  );
  maximumLevelNumber.addEventListener("change", () =>
    updateFromNumber(maximumLevelNumber, maximumLevel, true),
  );
  syncNumberInputs();
  renderTrack();
}

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
