"use strict";

const recipeCartStorageKey = "dofus-recipe-calculator-cart-v1";
const recipeSelectionStorageKey = "dofus-recipe-calculator-selection-v1";
const recipeCartButtons = Array.from(document.querySelectorAll(".recipe-cart-add"));
const recipeCartCount = document.querySelector("#recipe-cart-count");
const recipeOpenCalculator = document.querySelector("#recipe-open-calculator");

if (recipeCartCount && recipeOpenCalculator) {
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

  const cart = readCart();

  const readSelection = () => {
    try {
      const stored = window.localStorage.getItem(recipeSelectionStorageKey);
      if (stored === null) {
        return new Set(Object.keys(cart));
      }
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) {
        return new Set(Object.keys(cart));
      }
      return new Set(
        parsed.filter(
          (itemUuid) => typeof itemUuid === "string" && Object.hasOwn(cart, itemUuid),
        ),
      );
    } catch {
      return new Set(Object.keys(cart));
    }
  };

  const selectedItems = readSelection();

  const writeCart = () => {
    try {
      window.localStorage.setItem(recipeCartStorageKey, JSON.stringify(cart));
    } catch {
      // The in-page cart still works when browser storage is unavailable.
    }
  };

  const writeSelection = () => {
    try {
      window.localStorage.setItem(
        recipeSelectionStorageKey,
        JSON.stringify(Array.from(selectedItems)),
      );
    } catch {
      // The calculator defaults to selecting cart items when storage is unavailable.
    }
  };

  const renderCart = () => {
    const count = Object.keys(cart).length;
    recipeCartCount.textContent = `${count} ${count === 1 ? "item" : "items"} in calculator`;
    for (const button of recipeCartButtons) {
      const isAdded = Object.hasOwn(cart, button.dataset.itemUuid);
      button.disabled = isAdded;
      button.textContent = isAdded ? "Added ✓" : button.dataset.addLabel || "Add";
    }
  };

  for (const button of recipeCartButtons) {
    button.addEventListener("click", () => {
      cart[button.dataset.itemUuid] = 1;
      selectedItems.add(button.dataset.itemUuid);
      writeCart();
      writeSelection();
      renderCart();
    });
  }

  recipeOpenCalculator.addEventListener("click", (event) => {
    const selectedEntries = Object.entries(cart).filter(([itemUuid]) =>
      selectedItems.has(itemUuid),
    );
    if (selectedEntries.length === 0) {
      return;
    }
    event.preventDefault();
    const form = document.createElement("form");
    form.method = "post";
    form.action = "/recipe-calculator";
    for (const [itemUuid, quantity] of selectedEntries) {
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
