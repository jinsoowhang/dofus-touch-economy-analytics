"use strict";

const categorySelect = document.querySelector("#sale-category");
const itemSelect = document.querySelector("#sale-item");

if (categorySelect && itemSelect) {
  const placeholder = itemSelect.options[0];
  const itemOptions = Array.from(itemSelect.options).slice(1);
  let typeaheadQuery = "";
  let lastTypeaheadAt = 0;

  const moveItemToTop = (option) => {
    itemSelect.insertBefore(option, placeholder.nextElementSibling);
    option.selected = true;
    itemSelect.scrollTop = 0;
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
