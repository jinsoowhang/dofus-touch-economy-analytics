"use strict";

const calculatorSearch = document.querySelector("#calculator-search");
const calculatorChoiceData = document.querySelector("#calculator-choice-data");
const calculatorSearchResults = document.querySelector("#calculator-search-results");
const calculatorSelectedItems = document.querySelector("#calculator-selected-items");
const calculatorEmptySelection = document.querySelector("#calculator-empty-selection");
const calculatorClearSelection = document.querySelector("#calculator-clear-selection");
const calculatorSelectedCount = document.querySelector("#calculator-selected-count");

if (
  calculatorSearch &&
  calculatorChoiceData &&
  calculatorSearchResults &&
  calculatorSelectedItems &&
  calculatorEmptySelection &&
  calculatorClearSelection &&
  calculatorSelectedCount
) {
  const choices = JSON.parse(calculatorChoiceData.textContent);
  const choicesByUuid = new Map(choices.map((choice) => [choice.item_uuid, choice]));

  const updateSelectedCount = () => {
    const count = calculatorSelectedItems.children.length;
    calculatorSelectedCount.textContent = `${count} selected`;
    calculatorEmptySelection.hidden = count > 0;
  };

  const createCell = (text, className = "") => {
    const cell = document.createElement("td");
    cell.textContent = text;
    cell.className = className;
    return cell;
  };

  const addChoice = (choice) => {
    if (calculatorSelectedItems.querySelector(`[data-item-uuid="${choice.item_uuid}"]`)) {
      return;
    }

    const row = document.createElement("tr");
    row.dataset.itemUuid = choice.item_uuid;
    const itemCell = document.createElement("td");
    const hiddenItem = document.createElement("input");
    hiddenItem.type = "hidden";
    hiddenItem.name = "selected_item_uuid";
    hiddenItem.value = choice.item_uuid;
    itemCell.append(hiddenItem);
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
    quantity.value = "1";
    quantity.required = true;
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
    updateSelectedCount();
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
      const isSelected = calculatorSelectedItems.querySelector(
        `[data-item-uuid="${choice.item_uuid}"]`,
      );
      button.disabled = Boolean(isSelected);
      button.textContent = `${choice.display_name} — ${choice.profession} — ${choice.category || "Uncategorized"}${isSelected ? " — Selected" : ""}`;
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
    renderSearchResults();
  });

  calculatorClearSelection.addEventListener("click", () => {
    calculatorSelectedItems.replaceChildren();
    updateSelectedCount();
    renderSearchResults();
  });

  updateSelectedCount();
}
