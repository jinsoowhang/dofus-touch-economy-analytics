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
  const updateTrack = (changedInput) => {
    if (Number(minimumLevel.value) > Number(maximumLevel.value)) {
      if (changedInput === minimumLevel) {
        maximumLevel.value = minimumLevel.value;
      } else {
        minimumLevel.value = maximumLevel.value;
      }
    }
    minimumLevelNumber.value = minimumLevel.value;
    maximumLevelNumber.value = maximumLevel.value;

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

  const updateFromNumber = (numberInput, rangeInput) => {
    if (numberInput.value === "" || !numberInput.checkValidity()) {
      return;
    }
    rangeInput.value = numberInput.value;
    updateTrack(rangeInput);
  };

  minimumLevel.addEventListener("input", () => updateTrack(minimumLevel));
  maximumLevel.addEventListener("input", () => updateTrack(maximumLevel));
  minimumLevelNumber.addEventListener("input", () =>
    updateFromNumber(minimumLevelNumber, minimumLevel),
  );
  maximumLevelNumber.addEventListener("input", () =>
    updateFromNumber(maximumLevelNumber, maximumLevel),
  );
  updateTrack();
}

const recipeCartStorageKey = "dofus-recipe-calculator-cart-v1";
const recipeCartButtons = Array.from(document.querySelectorAll(".recipe-cart-add"));
const recipeCartCount = document.querySelector("#recipe-cart-count");
const recipeOpenCalculator = document.querySelector("#recipe-open-calculator");

if (recipeCartButtons.length > 0 && recipeCartCount && recipeOpenCalculator) {
  const readCart = () => {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(recipeCartStorageKey) || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return {};
      }
      return Object.fromEntries(
        Object.entries(parsed).filter(
          ([itemUuid, quantity]) =>
            /^[0-9a-f-]{36}$/i.test(itemUuid) &&
            Number.isInteger(quantity) &&
            quantity >= 1 &&
            quantity <= 1000,
        ),
      );
    } catch {
      return {};
    }
  };

  let cart = readCart();

  const writeCart = () => {
    try {
      window.localStorage.setItem(recipeCartStorageKey, JSON.stringify(cart));
    } catch {
      // The in-page cart still works when browser storage is unavailable.
    }
  };

  const renderCart = () => {
    const count = Object.keys(cart).length;
    recipeCartCount.textContent = `${count} ${count === 1 ? "item" : "items"} in calculator`;
    for (const button of recipeCartButtons) {
      const isAdded = Object.hasOwn(cart, button.dataset.itemUuid);
      button.disabled = isAdded;
      button.textContent = isAdded ? "Added ✓" : "Add";
    }
  };

  for (const button of recipeCartButtons) {
    button.addEventListener("click", () => {
      cart[button.dataset.itemUuid] = 1;
      writeCart();
      renderCart();
    });
  }

  recipeOpenCalculator.addEventListener("click", (event) => {
    if (Object.keys(cart).length === 0) {
      return;
    }
    event.preventDefault();
    const form = document.createElement("form");
    form.method = "post";
    form.action = "/recipe-calculator";
    for (const [itemUuid, quantity] of Object.entries(cart)) {
      const selectedItem = document.createElement("input");
      selectedItem.type = "hidden";
      selectedItem.name = "selected_item_uuid";
      selectedItem.value = itemUuid;
      const craftQuantity = document.createElement("input");
      craftQuantity.type = "hidden";
      craftQuantity.name = `quantity_${itemUuid}`;
      craftQuantity.value = String(quantity);
      form.append(selectedItem, craftQuantity);
    }
    document.body.append(form);
    form.requestSubmit();
  });

  renderCart();
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
