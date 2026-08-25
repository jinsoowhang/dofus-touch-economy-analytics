"use strict";

const calculatorSearch = document.querySelector("#calculator-search");
const calculatorChoiceData = document.querySelector("#calculator-choice-data");
const calculatorSearchResults = document.querySelector("#calculator-search-results");
const calculatorSuggestionResults = document.querySelector(
  "#calculator-suggestion-results",
);
const calculatorSelectedItems = document.querySelector("#calculator-selected-items");
const calculatorEmptySelection = document.querySelector("#calculator-empty-selection");
const calculatorSelectAll = document.querySelector("#calculator-select-all");
const calculatorSelectNone = document.querySelector("#calculator-select-none");
const calculatorRemoveAll = document.querySelector("#calculator-remove-all");
const calculatorSelectedCount = document.querySelector("#calculator-selected-count");
const calculatorForm = document.querySelector("#recipe-calculator-form");
const calculatorSalesForm = document.querySelector(".calculator-sales-form");
const calculatorSaleSelectAll = document.querySelector("#calculator-sale-select-all");
const recipeCartStorageKey = "dofus-recipe-calculator-cart-v1";
const recipeSelectionStorageKey = "dofus-recipe-calculator-selection-v1";
const recipeCalculatorPendingSalesStorageKey =
  "dofus-recipe-calculator-pending-sales-v1";
const recipeCalculatorScrollStorageKey = "dofus-recipe-calculator-scroll-position";
const recipeCalculatorShoppingListSortStorageKey =
  "dofus-recipe-calculator-shopping-list-sort";
const calculatorKamaFormatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 20,
});

try {
  window.sessionStorage.removeItem(recipeCalculatorPendingSalesStorageKey);
} catch {
  // A failed prior submission cannot leave a stale cart-removal request.
}

const parseCalculatorSalePrice = (value) => {
  const rawValue = value.trim();
  if (!/^\+?\d+$/.test(rawValue) && !/^\+?\d{1,3}(?:,\d{3})+$/.test(rawValue)) {
    return null;
  }
  const parsed = Number(rawValue.replaceAll(",", ""));
  return Number.isFinite(parsed) && Number.isInteger(parsed) && parsed > 0 ? parsed : null;
};

const updateCalculatorEstimatedProfit = (input) => {
  const profitCell = input.closest("tr")?.querySelector(".calculator-estimated-profit");
  const output = profitCell?.querySelector("output");
  if (!profitCell || !output) {
    return;
  }
  const salePrice = parseCalculatorSalePrice(input.value);
  const craftQuantity = Number(profitCell.dataset.craftQuantity);
  const rawRecipeCost = profitCell.dataset.totalRecipeCost;
  const totalRecipeCost = Number(rawRecipeCost);
  const estimatedProfit =
    salePrice === null ||
    !Number.isInteger(craftQuantity) ||
    craftQuantity < 1 ||
    rawRecipeCost === "" ||
    !Number.isFinite(totalRecipeCost)
      ? null
      : salePrice * craftQuantity - totalRecipeCost;
  if (estimatedProfit === null || !Number.isFinite(estimatedProfit)) {
    output.textContent = "—";
    profitCell.dataset.sortValue = "";
    return;
  }
  output.textContent = calculatorKamaFormatter.format(estimatedProfit);
  profitCell.dataset.sortValue = String(estimatedProfit);
};

const saveRecipeCalculatorShoppingListSort = () => {
  const table = document.querySelector(".calculator-shopping-list-table");
  const headers = Array.from(table?.tHead?.rows[0]?.cells || []);
  const columnIndex = headers.findIndex((header) =>
    ["ascending", "descending"].includes(header.getAttribute("aria-sort")),
  );
  try {
    if (columnIndex < 0) {
      window.sessionStorage.removeItem(recipeCalculatorShoppingListSortStorageKey);
      return;
    }
    window.sessionStorage.setItem(
      recipeCalculatorShoppingListSortStorageKey,
      JSON.stringify({
        columnIndex,
        direction: headers[columnIndex].getAttribute("aria-sort"),
      }),
    );
  } catch {
    // The recalculated shopping list keeps its server-provided order without storage.
  }
};

const restoreRecipeCalculatorShoppingListSort = () => {
  let savedSortState = null;
  try {
    savedSortState = window.sessionStorage.getItem(
      recipeCalculatorShoppingListSortStorageKey,
    );
    window.sessionStorage.removeItem(recipeCalculatorShoppingListSortStorageKey);
  } catch {
    return;
  }
  if (savedSortState === null) {
    return;
  }

  try {
    const sortState = JSON.parse(savedSortState);
    if (
      !Number.isInteger(sortState.columnIndex) ||
      !["ascending", "descending"].includes(sortState.direction)
    ) {
      return;
    }
    const table = document.querySelector(".calculator-shopping-list-table");
    const header = table?.tHead?.rows[0]?.cells[sortState.columnIndex];
    const button = header?.querySelector(".client-sort-header");
    if (!button) {
      return;
    }
    button.click();
    if (sortState.direction === "descending") {
      button.click();
    }
  } catch {
    // Ignore stale or malformed transient sort state.
  }
};

if (
  calculatorSearch &&
  calculatorChoiceData &&
  calculatorSearchResults &&
  calculatorSuggestionResults &&
  calculatorSelectedItems &&
  calculatorEmptySelection &&
  calculatorSelectAll &&
  calculatorSelectNone &&
  calculatorRemoveAll &&
  calculatorSelectedCount &&
  calculatorForm
) {
  const choices = JSON.parse(calculatorChoiceData.textContent);
  const choicesByUuid = new Map(choices.map((choice) => [choice.item_uuid, choice]));
  let suggestionRefreshTimer = null;
  let suggestionRequestController = null;

  const renderSuggestionMessage = (message) => {
    const paragraph = document.createElement("p");
    paragraph.textContent = message;
    calculatorSuggestionResults.replaceChildren(paragraph);
  };

  const refreshSuggestions = async () => {
    const itemUuids = Array.from(
      calculatorSelectedItems.querySelectorAll("[data-item-uuid]"),
      (row) => row.dataset.itemUuid,
    );
    suggestionRequestController?.abort();
    suggestionRequestController = null;
    if (itemUuids.length < 2) {
      renderSuggestionMessage("Add at least two craftable items to see suggestions.");
      return;
    }

    renderSuggestionMessage("Finding crafts with similar ingredients…");
    const formData = new FormData();
    for (const itemUuid of itemUuids) {
      formData.append("item_uuid", itemUuid);
    }
    const requestController = new AbortController();
    suggestionRequestController = requestController;
    try {
      const response = await fetch("/recipe-calculator/suggestions", {
        method: "POST",
        headers: { Accept: "application/json" },
        body: formData,
        signal: requestController.signal,
      });
      const payload = await response.json();
      if (!response.ok) {
        throw new Error(payload.errors?.join(" ") || "Could not load suggestions.");
      }
      if (suggestionRequestController !== requestController) {
        return;
      }

      calculatorSuggestionResults.replaceChildren();
      const cartItemUuids = new Set(itemUuids);
      let renderedSuggestionCount = 0;
      for (const suggestion of payload.suggestions || []) {
        const choice = choicesByUuid.get(suggestion.item_uuid);
        if (!choice || cartItemUuids.has(suggestion.item_uuid)) {
          continue;
        }
        const button = document.createElement("button");
        button.type = "button";
        button.className = "calculator-search-result calculator-suggestion-result";
        button.dataset.itemUuid = suggestion.item_uuid;
        const level =
          suggestion.profession_level === null
            ? "unknown level"
            : `level ${suggestion.profession_level}`;
        const selectedItemLabel =
          suggestion.matching_selected_item_count === 1 ? "cart item" : "cart items";
        const itemLabel = document.createElement("span");
        itemLabel.className = "calculator-suggestion-item";
        itemLabel.textContent = suggestion.display_name;
        const professionLabel = document.createElement("span");
        professionLabel.textContent = `${suggestion.profession}, ${level}`;
        const ingredientsLabel = document.createElement("span");
        ingredientsLabel.textContent =
          `${suggestion.shared_ingredient_count} of ${suggestion.ingredient_count} ` +
          `shared (${suggestion.overlap_percent}%) across ` +
          `${suggestion.matching_selected_item_count} ${selectedItemLabel}`;
        const salesLabel = document.createElement("span");
        salesLabel.textContent =
          `${suggestion.active_listing_count} currently selling · ` +
          `${suggestion.completed_sale_count} sold`;
        const addLabel = document.createElement("span");
        addLabel.className = "calculator-suggestion-add";
        addLabel.textContent = "Add";
        button.append(itemLabel, professionLabel, ingredientsLabel, salesLabel, addLabel);
        button.setAttribute("aria-label", `Add suggested craft ${suggestion.display_name}`);
        calculatorSuggestionResults.append(button);
        renderedSuggestionCount += 1;
      }
      if (renderedSuggestionCount === 0) {
        renderSuggestionMessage("No additional crafts share ingredients with this cart.");
      }
    } catch (error) {
      if (error.name !== "AbortError") {
        renderSuggestionMessage(error.message || "Could not load suggestions. Try again.");
      }
    } finally {
      if (suggestionRequestController === requestController) {
        suggestionRequestController = null;
      }
    }
  };

  const scheduleSuggestionRefresh = () => {
    window.clearTimeout(suggestionRefreshTimer);
    suggestionRequestController?.abort();
    suggestionRequestController = null;
    suggestionRefreshTimer = window.setTimeout(() => {
      refreshSuggestions();
    }, 150);
  };

  const readCart = () => {
    try {
      const parsed = JSON.parse(window.localStorage.getItem(recipeCartStorageKey) || "{}");
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return {};
      }
      return Object.fromEntries(
        Object.entries(parsed).filter(
          ([itemUuid, quantity]) =>
            choicesByUuid.has(itemUuid) &&
            Number.isInteger(quantity) &&
            quantity >= 1 &&
            quantity <= 1000,
        ),
      );
    } catch {
      return {};
    }
  };

  const storedCart = readCart();

  const readSelection = () => {
    try {
      const stored = window.localStorage.getItem(recipeSelectionStorageKey);
      if (stored === null) {
        return new Set(Object.keys(storedCart));
      }
      const parsed = JSON.parse(stored);
      if (!Array.isArray(parsed)) {
        return new Set(Object.keys(storedCart));
      }
      return new Set(
        parsed.filter(
          (itemUuid) => typeof itemUuid === "string" && Object.hasOwn(storedCart, itemUuid),
        ),
      );
    } catch {
      return new Set(Object.keys(storedCart));
    }
  };

  const storedSelection = readSelection();

  const persistCart = () => {
    const cart = {};
    for (const row of calculatorSelectedItems.querySelectorAll("[data-item-uuid]")) {
      const quantity = Number(row.querySelector(".calculator-quantity")?.value);
      if (Number.isInteger(quantity) && quantity >= 1 && quantity <= 1000) {
        cart[row.dataset.itemUuid] = quantity;
      }
    }
    try {
      window.localStorage.setItem(recipeCartStorageKey, JSON.stringify(cart));
    } catch {
      // The server-rendered calculator remains usable without browser storage.
    }
  };

  const persistSelection = () => {
    const selectedItemUuids = Array.from(
      calculatorSelectedItems.querySelectorAll(".calculator-item-checkbox:checked"),
      (checkbox) => checkbox.value,
    );
    try {
      window.localStorage.setItem(
        recipeSelectionStorageKey,
        JSON.stringify(selectedItemUuids),
      );
    } catch {
      // The checked controls remain authoritative for the current browser request.
    }
  };

  const updateSelectedCount = () => {
    const selectedCount = calculatorSelectedItems.querySelectorAll(
      ".calculator-item-checkbox:checked",
    ).length;
    calculatorSelectedCount.textContent = `${selectedCount} selected`;
    calculatorEmptySelection.hidden = calculatorSelectedItems.children.length > 0;
  };

  const updateRowState = (row) => {
    const isCalculationSelected = row.querySelector(".calculator-item-checkbox").checked;
    row.classList.toggle("is-unselected", !isCalculationSelected);
    row.querySelector(".calculator-quantity").disabled = !isCalculationSelected;
  };

  const createCell = (text, className = "") => {
    const cell = document.createElement("td");
    cell.textContent = text;
    cell.className = className;
    return cell;
  };

  const addChoice = (choice, craftQuantity = 1, isSelected = true, shouldPersist = true) => {
    if (calculatorSelectedItems.querySelector(`[data-item-uuid="${choice.item_uuid}"]`)) {
      return;
    }

    const row = document.createElement("tr");
    row.dataset.itemUuid = choice.item_uuid;
    row.classList.toggle("is-unselected", !isSelected);
    const selectionCell = document.createElement("td");
    selectionCell.className = "selection-column";
    const selection = document.createElement("input");
    selection.className = "calculator-item-checkbox";
    selection.type = "checkbox";
    selection.name = "selected_item_uuid";
    selection.value = choice.item_uuid;
    selection.checked = isSelected;
    selection.setAttribute("aria-label", `Include ${choice.display_name} in calculation`);
    selectionCell.append(selection);
    row.append(selectionCell);
    const itemCell = document.createElement("td");
    const itemLabel = document.createElement("a");
    itemLabel.className = "item-label";
    itemLabel.href = `/items/${choice.item_uuid}`;
    if (choice.icon_url) {
      const icon = document.createElement("img");
      icon.className = "item-icon";
      icon.src = choice.icon_url;
      icon.alt = "";
      icon.loading = "lazy";
      itemLabel.append(icon);
    }
    const name = document.createElement("span");
    name.textContent = choice.display_name;
    itemLabel.append(name);
    itemCell.append(itemLabel);
    row.append(itemCell);
    row.append(createCell(choice.category || "Uncategorized"));
    row.append(createCell(choice.profession));
    row.append(
      createCell(choice.profession_level === null ? "—" : String(choice.profession_level), "numeric"),
    );

    const quantityCell = document.createElement("td");
    quantityCell.className = "numeric";
    const quantityLabel = document.createElement("label");
    quantityLabel.className = "visually-hidden";
    quantityLabel.htmlFor = `calculator-quantity-${choice.item_uuid}`;
    quantityLabel.textContent = `Craft quantity for ${choice.display_name}`;
    const quantity = document.createElement("input");
    quantity.id = quantityLabel.htmlFor;
    quantity.className = "calculator-quantity";
    quantity.name = `quantity_${choice.item_uuid}`;
    quantity.type = "number";
    quantity.inputMode = "numeric";
    quantity.min = "1";
    quantity.max = "1000";
    quantity.value = String(craftQuantity);
    quantity.required = true;
    quantity.disabled = !isSelected;
    quantityCell.append(quantityLabel, quantity);
    row.append(quantityCell);

    const actionCell = document.createElement("td");
    const removeButton = document.createElement("button");
    removeButton.type = "button";
    removeButton.className = "calculator-remove-item secondary-button";
    removeButton.setAttribute("aria-label", `Remove ${choice.display_name}`);
    removeButton.textContent = "Remove";
    actionCell.append(removeButton);
    row.append(actionCell);
    calculatorSelectedItems.append(row);
    updateRowState(row);
    updateSelectedCount();
    if (shouldPersist) {
      persistCart();
      persistSelection();
    }
    scheduleSuggestionRefresh();
  };

  const renderSearchResults = () => {
    const query = calculatorSearch.value.trim().toLocaleLowerCase();
    calculatorSearchResults.replaceChildren();
    if (!query) {
      const help = document.createElement("p");
      help.textContent = "Type to find craftable items.";
      calculatorSearchResults.append(help);
      return;
    }
    const matches = choices
      .filter((choice) =>
        `${choice.display_name} ${choice.category || ""} ${choice.profession}`
          .toLocaleLowerCase()
          .includes(query),
      )
      .slice(0, 50);
    if (matches.length === 0) {
      const empty = document.createElement("p");
      empty.textContent = "No craftable items match that search.";
      calculatorSearchResults.append(empty);
      return;
    }
    for (const choice of matches) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "calculator-search-result";
      button.dataset.itemUuid = choice.item_uuid;
      const isInCart = calculatorSelectedItems.querySelector(
        `[data-item-uuid="${choice.item_uuid}"]`,
      );
      button.disabled = Boolean(isInCart);
      button.textContent = `${choice.display_name} — ${choice.profession} — ${choice.category || "Uncategorized"}${isInCart ? " — In cart" : ""}`;
      calculatorSearchResults.append(button);
    }
  };

  calculatorSearch.addEventListener("input", renderSearchResults);

  calculatorSearchResults.addEventListener("click", (event) => {
    const button = event.target.closest(".calculator-search-result");
    if (!button) {
      return;
    }
    const choice = choicesByUuid.get(button.dataset.itemUuid);
    if (choice) {
      addChoice(choice);
      renderSearchResults();
    }
  });

  calculatorSuggestionResults.addEventListener("click", (event) => {
    const button = event.target.closest(".calculator-suggestion-result");
    if (!button) {
      return;
    }
    const choice = choicesByUuid.get(button.dataset.itemUuid);
    if (choice) {
      button.disabled = true;
      addChoice(choice);
      renderSearchResults();
    }
  });

  calculatorSelectedItems.addEventListener("click", (event) => {
    const button = event.target.closest(".calculator-remove-item");
    if (!button) {
      return;
    }
    button.closest("tr").remove();
    updateSelectedCount();
    persistCart();
    persistSelection();
    renderSearchResults();
    scheduleSuggestionRefresh();
  });

  calculatorSelectedItems.addEventListener("input", (event) => {
    if (event.target.matches(".calculator-quantity")) {
      persistCart();
    }
  });

  calculatorSelectedItems.addEventListener("change", (event) => {
    if (!event.target.matches(".calculator-item-checkbox")) {
      return;
    }
    const row = event.target.closest("tr");
    updateRowState(row);
    updateSelectedCount();
    persistSelection();
  });

  const setAllSelected = (isSelected) => {
    for (const checkbox of calculatorSelectedItems.querySelectorAll(
      ".calculator-item-checkbox",
    )) {
      checkbox.checked = isSelected;
      updateRowState(checkbox.closest("tr"));
    }
    updateSelectedCount();
    persistSelection();
  };

  calculatorSelectAll.addEventListener("click", () => setAllSelected(true));
  calculatorSelectNone.addEventListener("click", () => setAllSelected(false));

  calculatorRemoveAll.addEventListener("click", () => {
    calculatorSelectedItems.replaceChildren();
    updateSelectedCount();
    persistCart();
    persistSelection();
    renderSearchResults();
    scheduleSuggestionRefresh();
  });

  for (const row of calculatorSelectedItems.querySelectorAll("[data-item-uuid]")) {
    const quantity = Number(row.querySelector(".calculator-quantity")?.value);
    if (Number.isInteger(quantity) && quantity >= 1 && quantity <= 1000) {
      storedCart[row.dataset.itemUuid] = quantity;
      if (row.querySelector(".calculator-item-checkbox").checked) {
        storedSelection.add(row.dataset.itemUuid);
      } else {
        storedSelection.delete(row.dataset.itemUuid);
      }
    }
    updateRowState(row);
  }
  for (const [itemUuid, quantity] of Object.entries(storedCart)) {
    const choice = choicesByUuid.get(itemUuid);
    if (choice && !calculatorSelectedItems.querySelector(`[data-item-uuid="${itemUuid}"]`)) {
      addChoice(choice, quantity, storedSelection.has(itemUuid), false);
    }
  }
  persistCart();
  persistSelection();
  updateSelectedCount();
  scheduleSuggestionRefresh();

  window.addEventListener("pageshow", (event) => {
    if (!event.persisted) {
      return;
    }
    const cart = readCart();
    const hasRemovedCartItem = Array.from(
      calculatorSelectedItems.querySelectorAll("[data-item-uuid]"),
    ).some((row) => !Object.hasOwn(cart, row.dataset.itemUuid));
    if (hasRemovedCartItem) {
      window.location.reload();
    }
  });

  calculatorForm.addEventListener("submit", () => {
    persistCart();
    persistSelection();
  });

  for (const input of document.querySelectorAll(".calculator-sale-price")) {
    updateCalculatorEstimatedProfit(input);
    input.addEventListener("input", () => updateCalculatorEstimatedProfit(input));
  }

  if (calculatorSalesForm) {
    const calculatorSaleCheckboxes = Array.from(
      calculatorSalesForm.querySelectorAll(".calculator-sale-checkbox"),
    );

    const updateCalculatorSaleSelectAll = () => {
      if (!calculatorSaleSelectAll) {
        return;
      }
      const selectedCount = calculatorSaleCheckboxes.filter(
        (checkbox) => checkbox.checked,
      ).length;
      calculatorSaleSelectAll.checked = selectedCount === calculatorSaleCheckboxes.length;
      calculatorSaleSelectAll.indeterminate =
        selectedCount > 0 && selectedCount < calculatorSaleCheckboxes.length;
    };

    if (calculatorSaleSelectAll && calculatorSaleCheckboxes.length > 0) {
      calculatorSaleSelectAll.addEventListener("change", () => {
        for (const checkbox of calculatorSaleCheckboxes) {
          checkbox.checked = calculatorSaleSelectAll.checked;
        }
        updateCalculatorSaleSelectAll();
      });
      for (const checkbox of calculatorSaleCheckboxes) {
        checkbox.addEventListener("change", updateCalculatorSaleSelectAll);
      }
      updateCalculatorSaleSelectAll();
    }

    calculatorSalesForm.addEventListener("submit", (event) => {
      if (calculatorSalesForm.dataset.submitting === "true") {
        event.preventDefault();
        return;
      }
      calculatorSalesForm.dataset.submitting = "true";
      const submitButton = calculatorSalesForm.querySelector('button[type="submit"]');
      if (submitButton) {
        submitButton.disabled = true;
        submitButton.textContent = "Adding to Sales…";
      }
      const saleItemUuids = Array.from(
        calculatorSalesForm.querySelectorAll('input[name="sale_item_uuid"]:checked'),
        (checkbox) => checkbox.value,
      );
      try {
        window.sessionStorage.setItem(
          recipeCalculatorPendingSalesStorageKey,
          JSON.stringify(saleItemUuids),
        );
      } catch {
        // Listings still submit when transient browser storage is unavailable.
      }
    });
  }

  for (const form of document.querySelectorAll(".calculator-ingredient-price-form")) {
    const input = form.querySelector('input[name="unit_price"]');
    const errorMessage = form.querySelector(".calculator-price-error");
    if (!input || !errorMessage) {
      continue;
    }

    const showError = (message) => {
      errorMessage.textContent = message;
      errorMessage.hidden = false;
      form.dataset.saving = "false";
    };

    const savePrice = async () => {
      if (form.dataset.saving === "true") {
        return;
      }
      if (input.value.trim() === input.dataset.initialValue) {
        return;
      }
      if (!input.reportValidity()) {
        return;
      }

      form.dataset.saving = "true";
      errorMessage.hidden = true;
      try {
        const response = await fetch(form.action, {
          method: "POST",
          headers: { Accept: "application/json" },
          body: new FormData(form),
        });
        const payload = await response.json();
        if (!response.ok) {
          showError(payload.errors?.join(" ") || "Could not update this price.");
          return;
        }
        input.dataset.initialValue = input.value.trim();
        saveRecipeCalculatorShoppingListSort();
        try {
          window.sessionStorage.setItem(
            recipeCalculatorScrollStorageKey,
            String(window.scrollY),
          );
        } catch {
          // The calculator results remain the no-storage fallback.
        }
        calculatorForm.action = `/recipe-calculator?updated=${encodeURIComponent(form.dataset.itemUuid)}`;
        calculatorForm.requestSubmit();
      } catch {
        showError("Could not update this price. Try again.");
      }
    };

    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        savePrice();
      }
    });
    input.addEventListener("blur", savePrice);
  }
}

window.addEventListener("load", () => {
  restoreRecipeCalculatorShoppingListSort();
  let savedScrollPosition = null;
  try {
    savedScrollPosition = window.sessionStorage.getItem(recipeCalculatorScrollStorageKey);
    window.sessionStorage.removeItem(recipeCalculatorScrollStorageKey);
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
