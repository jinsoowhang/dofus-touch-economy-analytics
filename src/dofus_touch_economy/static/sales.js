"use strict";

const categorySelect = document.querySelector("#sale-category");
const itemSelect = document.querySelector("#sale-item");
const salePriceInput = document.querySelector("#sale-asking-price");
const salePriceSuggestion = document.querySelector("#sale-price-suggestion");

if (categorySelect && itemSelect) {
  const placeholder = itemSelect.options[0];
  const itemOptions = Array.from(itemSelect.options).slice(1);
  let typeaheadQuery = "";
  let lastTypeaheadAt = 0;

  const updateSalePriceSuggestion = (prefillPrice) => {
    if (!salePriceSuggestion) {
      return;
    }
    const selectedItem = itemSelect.selectedOptions[0];
    if (!selectedItem || selectedItem === placeholder) {
      salePriceSuggestion.hidden = true;
      salePriceSuggestion.textContent = "";
      if (prefillPrice && salePriceInput) {
        salePriceInput.value = "";
      }
      return;
    }

    salePriceSuggestion.hidden = false;
    const suggestedPrice = selectedItem.dataset.suggestedPrice || "";
    const soldCount = Number(selectedItem.dataset.soldCount || 0);
    if (!suggestedPrice) {
      salePriceSuggestion.textContent = "No completed sales for this item yet.";
      if (prefillPrice && salePriceInput) {
        salePriceInput.value = "";
      }
      return;
    }

    const saleLabel = soldCount === 1 ? "sale" : "sales";
    salePriceSuggestion.textContent =
      `Suggested Price: ${suggestedPrice} · Median of ${soldCount} completed ${saleLabel}.`;
    if (prefillPrice && salePriceInput) {
      salePriceInput.value = suggestedPrice;
    }
  };

  const moveItemToTop = (option) => {
    itemSelect.insertBefore(option, placeholder.nextElementSibling);
    option.selected = true;
    itemSelect.scrollTop = 0;
    updateSalePriceSuggestion(true);
  };

  const filterItems = () => {
    const selectedCategory = categorySelect.value;
    for (const option of itemOptions) {
      const matches = !selectedCategory || option.dataset.category === selectedCategory;
      option.hidden = !matches;
      option.disabled = !matches;
    }

    const selectedItem = itemSelect.selectedOptions[0];
    if (selectedItem && selectedItem.disabled) {
      itemSelect.value = "";
      updateSalePriceSuggestion(true);
    }

    const categoryLabel = categorySelect.selectedOptions[0]?.textContent?.trim();
    placeholder.textContent = selectedCategory
      ? `Choose a ${categoryLabel} item`
      : "Choose an item";
  };

  categorySelect.addEventListener("change", filterItems);
  itemSelect.addEventListener("change", () => {
    const selectedItem = itemSelect.selectedOptions[0];
    if (selectedItem && selectedItem !== placeholder) {
      moveItemToTop(selectedItem);
    } else {
      updateSalePriceSuggestion(true);
    }
  });
  itemSelect.addEventListener("keydown", (event) => {
    const isPrintable =
      event.key.length === 1 && !event.altKey && !event.ctrlKey && !event.metaKey;
    if (!isPrintable && event.key !== "Backspace") {
      return;
    }

    const now = Date.now();
    if (now - lastTypeaheadAt > 800) {
      typeaheadQuery = "";
    }
    lastTypeaheadAt = now;
    typeaheadQuery =
      event.key === "Backspace"
        ? typeaheadQuery.slice(0, -1)
        : `${typeaheadQuery}${event.key.toLocaleLowerCase()}`;

    const findMatch = (query) =>
      itemOptions.find(
        (option) =>
          !option.disabled &&
          (option.dataset.name || "").toLocaleLowerCase().startsWith(query),
      );
    let matchingItem = findMatch(typeaheadQuery);
    if (!matchingItem && isPrintable && typeaheadQuery.length > 1) {
      typeaheadQuery = event.key.toLocaleLowerCase();
      matchingItem = findMatch(typeaheadQuery);
    }
    if (matchingItem) {
      event.preventDefault();
      moveItemToTop(matchingItem);
    }
  });
  itemSelect.addEventListener("blur", () => {
    typeaheadQuery = "";
  });
  filterItems();
  updateSalePriceSuggestion(false);
}

for (const form of document.querySelectorAll(".price-edit-form")) {
  const input = form.querySelector(
    'input[name="asking_price"], input[name="unit_price"], input[name="current_price"]',
  );
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
