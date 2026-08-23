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

const activeSalesBulkForm = document.querySelector("#active-sales-bulk-form");
const activeSalesSelectAll = document.querySelector("#select-all-active-sales");
const activeSaleCheckboxes = Array.from(
  document.querySelectorAll(".active-sale-checkbox"),
);

if (activeSalesBulkForm && activeSalesSelectAll && activeSaleCheckboxes.length > 0) {
  const bulkButtons = Array.from(
    activeSalesBulkForm.querySelectorAll('button[name="action"]'),
  );
  const selectionCount = document.querySelector("#active-sales-selection-count");

  const updateBulkSelection = () => {
    const selectedCount = activeSaleCheckboxes.filter((checkbox) => checkbox.checked).length;
    activeSalesSelectAll.checked = selectedCount === activeSaleCheckboxes.length;
    activeSalesSelectAll.indeterminate =
      selectedCount > 0 && selectedCount < activeSaleCheckboxes.length;
    for (const button of bulkButtons) {
      button.disabled = selectedCount === 0;
    }
    if (selectionCount) {
      selectionCount.textContent = `${selectedCount} selected`;
    }
  };

  activeSalesSelectAll.addEventListener("change", () => {
    for (const checkbox of activeSaleCheckboxes) {
      checkbox.checked = activeSalesSelectAll.checked;
    }
    updateBulkSelection();
  });
  for (const checkbox of activeSaleCheckboxes) {
    checkbox.addEventListener("change", updateBulkSelection);
  }
  activeSalesBulkForm.addEventListener("submit", (event) => {
    if (
      event.submitter?.value === "delete" &&
      !window.confirm("Delete the selected sales rows? This cannot be undone.")
    ) {
      event.preventDefault();
    }
  });
  updateBulkSelection();
}

const salesScrollStorageKey = "dofus-sales-scroll-y";

for (const form of document.querySelectorAll("form[data-preserve-scroll]")) {
  form.addEventListener("submit", (event) => {
    if (event.defaultPrevented) {
      return;
    }
    try {
      window.sessionStorage.setItem(salesScrollStorageKey, String(window.scrollY));
      window.queueMicrotask(() => {
        if (event.defaultPrevented) {
          window.sessionStorage.removeItem(salesScrollStorageKey);
        }
      });
    } catch {
      // The server-side section anchor remains the fallback when storage is unavailable.
    }
  });
}

window.addEventListener("load", () => {
  let savedScrollPosition = null;
  try {
    savedScrollPosition = window.sessionStorage.getItem(salesScrollStorageKey);
    window.sessionStorage.removeItem(salesScrollStorageKey);
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
