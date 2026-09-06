"use strict";

const salesRecipeCartStorageKey = "dofus-recipe-calculator-cart-v1";
const salesRecipeSelectionStorageKey = "dofus-recipe-calculator-selection-v1";
const recipeCalculatorPendingSalesStorageKey =
  "dofus-recipe-calculator-pending-sales-v1";

const removeCompletedRecipeCalculatorSales = () => {
  const parameters = new URLSearchParams(window.location.search);
  if (parameters.get("notice") !== "listings-added") {
    return;
  }

  let pendingSales = null;
  try {
    pendingSales = window.sessionStorage.getItem(recipeCalculatorPendingSalesStorageKey);
    window.sessionStorage.removeItem(recipeCalculatorPendingSalesStorageKey);
  } catch {
    return;
  }
  if (pendingSales === null) {
    return;
  }

  try {
    const itemUuids = new Set(
      JSON.parse(pendingSales).filter((itemUuid) => typeof itemUuid === "string"),
    );
    const cart = JSON.parse(window.localStorage.getItem(salesRecipeCartStorageKey) || "{}");
    if (!cart || typeof cart !== "object" || Array.isArray(cart)) {
      return;
    }
    for (const itemUuid of itemUuids) {
      delete cart[itemUuid];
    }
    window.localStorage.setItem(salesRecipeCartStorageKey, JSON.stringify(cart));

    const storedSelection = window.localStorage.getItem(salesRecipeSelectionStorageKey);
    if (storedSelection !== null) {
      const selection = JSON.parse(storedSelection);
      if (Array.isArray(selection)) {
        window.localStorage.setItem(
          salesRecipeSelectionStorageKey,
          JSON.stringify(selection.filter((itemUuid) => !itemUuids.has(itemUuid))),
        );
      }
    }
  } catch {
    // Successful listings remain authoritative when browser storage is unavailable.
  }
};

removeCompletedRecipeCalculatorSales();

const salePriceInput = document.querySelector("#sale-asking-price");
const chartSeriesToggles = Array.from(
  document.querySelectorAll(".chart-series-toggle"),
);

if (chartSeriesToggles.length > 0) {
  const updateChartSeriesVisibility = () => {
    const checkedToggles = chartSeriesToggles.filter((toggle) => toggle.checked);
    for (const toggle of chartSeriesToggles) {
      const seriesKey = toggle.dataset.chartSeries;
      for (const element of document.querySelectorAll(
        `.chart-series--${seriesKey}, .chart-point--${seriesKey}`,
      )) {
        element.classList.toggle("is-hidden", !toggle.checked);
      }
      toggle.disabled = checkedToggles.length === 1 && toggle.checked;
    }
  };
  for (const toggle of chartSeriesToggles) {
    toggle.addEventListener("change", updateChartSeriesVisibility);
  }
  updateChartSeriesVisibility();
}

const initializeSaleItemPicker = () => {
  const itemSelect = document.querySelector("#sale-item");
  const salePriceSuggestion = document.querySelector("#sale-price-suggestion");
  if (!itemSelect || !salePriceSuggestion) {
    return;
  }
  const updateSalePriceSuggestion = (prefillPrice) => {
    const selectedItem = itemSelect.selectedOptions[0];
    salePriceSuggestion.hidden = !itemSelect.value;
    if (!itemSelect.value) {
      salePriceSuggestion.textContent = "";
      return;
    }
    const suggestedPrice = selectedItem.dataset.suggestedPrice || "";
    const soldCount = Number(selectedItem.dataset.soldCount || 0);
    const saleLabel = soldCount === 1 ? "sale" : "sales";
    salePriceSuggestion.textContent = suggestedPrice
      ? `Suggested Price: ${suggestedPrice} · Median of ${soldCount} completed ${saleLabel}.`
      : "No completed sales for this item yet.";
    if (prefillPrice && salePriceInput) {
      salePriceInput.value = suggestedPrice;
    }
  };
  itemSelect.addEventListener("change", () => updateSalePriceSuggestion(true));
  updateSalePriceSuggestion(false);
};

initializeSaleItemPicker();

// Clear a stale selection immediately, including during the search debounce.
for (const control of document.querySelectorAll("#sale-item-query, #sale-category")) {
  control.addEventListener(control.id === "sale-category" ? "change" : "input", () => {
    document.querySelector("#sale-item").value = "";
    document.querySelector("#sale-item").disabled = true;
    document.querySelector(".sales-form button[type=submit]").disabled = true;
    document.querySelector("#sale-price-suggestion").hidden = true;
    document.querySelector("#sale-item-error").hidden = true;
  });
}
document.body.addEventListener("htmx:beforeRequest", (event) => {
  if (event.detail.target?.id === "sale-item-results") {
    document.querySelector("#sale-item").disabled = true;
    document.querySelector(".sales-form button[type=submit]").disabled = true;
  }
});
const isCurrentItemSearch = (event) => {
  const parameters = event.detail.requestConfig.parameters;
  return parameters.q === document.querySelector("#sale-item-query").value
    && parameters.category === document.querySelector("#sale-category").value;
};
document.body.addEventListener("htmx:beforeSwap", (event) => {
  if (event.detail.target?.id === "sale-item-results" && !isCurrentItemSearch(event)) {
    event.detail.shouldSwap = false;
  }
});
document.querySelector(".sales-form")?.addEventListener("submit", (event) => {
  if (document.querySelector("#sale-item").disabled) {
    event.preventDefault();
  }
});
document.body.addEventListener("htmx:afterRequest", (event) => {
  if (event.detail.target?.id === "sale-item-results" && isCurrentItemSearch(event)) {
    document.querySelector("#sale-item").disabled = false;
    document.querySelector(".sales-form button[type=submit]").disabled = false;
    document.querySelector("#sale-item-error").hidden = !event.detail.failed;
  }
});
document.body.addEventListener("htmx:afterSwap", (event) => {
  if (event.detail.target?.id === "sale-item-results") {
    initializeSaleItemPicker();
  }
});

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

window.addEventListener("pageshow", () => {
  let savedScrollPosition = null;
  try {
    savedScrollPosition = window.sessionStorage.getItem(salesScrollStorageKey);
  } catch {
    return;
  }
  if (savedScrollPosition === null) {
    return;
  }
  const scrollPosition = Number(savedScrollPosition);
  if (Number.isFinite(scrollPosition) && scrollPosition >= 0) {
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        window.scrollTo(0, scrollPosition);
        try {
          window.sessionStorage.removeItem(salesScrollStorageKey);
        } catch {
          // The restored position is already applied.
        }
      });
    });
  } else {
    try {
      window.sessionStorage.removeItem(salesScrollStorageKey);
    } catch {
      // Ignore unavailable browser storage.
    }
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
