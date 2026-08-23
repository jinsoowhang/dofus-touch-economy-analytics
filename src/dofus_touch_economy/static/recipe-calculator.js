"use strict";

const calculatorSearch = document.querySelector("#calculator-search");
const calculatorChoiceData = document.querySelector("#calculator-choice-data");
const calculatorSearchResults = document.querySelector("#calculator-search-results");
const calculatorSelectedItems = document.querySelector("#calculator-selected-items");
const calculatorEmptySelection = document.querySelector("#calculator-empty-selection");
const calculatorSelectAll = document.querySelector("#calculator-select-all");
const calculatorSelectNone = document.querySelector("#calculator-select-none");
const calculatorRemoveAll = document.querySelector("#calculator-remove-all");
const calculatorSelectedCount = document.querySelector("#calculator-selected-count");
const calculatorForm = document.querySelector("#recipe-calculator-form");
const recipeCartStorageKey = "dofus-recipe-calculator-cart-v1";
const recipeSelectionStorageKey = "dofus-recipe-calculator-selection-v1";
const recipeCalculatorScrollStorageKey = "dofus-recipe-calculator-scroll-position";
const recipeCalculatorShoppingListSortStorageKey =
  "dofus-recipe-calculator-shopping-list-sort";

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
    const itemLabel = document.createElement("span");
    itemLabel.className = "item-label";
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

  calculatorForm.addEventListener("submit", () => {
    persistCart();
    persistSelection();
  });

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
