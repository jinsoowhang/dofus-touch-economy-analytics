"use strict";

const calculatorSearch = document.querySelector("#calculator-search");
const calculatorChoiceTable = document.querySelector(".calculator-choice-table");
const calculatorSelectVisible = document.querySelector("#calculator-select-visible");
const calculatorClearSelection = document.querySelector("#calculator-clear-selection");
const calculatorSelectedCount = document.querySelector("#calculator-selected-count");

if (
  calculatorSearch &&
  calculatorChoiceTable &&
  calculatorSelectVisible &&
  calculatorClearSelection &&
  calculatorSelectedCount
) {
  const rows = Array.from(calculatorChoiceTable.querySelectorAll(".calculator-choice-row"));

  const updateSelectedCount = () => {
    const count = calculatorChoiceTable.querySelectorAll(
      'input[name="selected_item_uuid"]:checked',
    ).length;
    calculatorSelectedCount.textContent = `${count} selected`;
  };

  const setRowSelected = (row, selected) => {
    const checkbox = row.querySelector('input[name="selected_item_uuid"]');
    const quantity = row.querySelector(".calculator-quantity");
    if (!checkbox || !quantity) {
      return;
    }
    checkbox.checked = selected;
    quantity.disabled = !selected;
  };

  calculatorSearch.addEventListener("input", () => {
    const query = calculatorSearch.value.trim().toLocaleLowerCase();
    for (const row of rows) {
      row.hidden = query !== "" && !row.dataset.search.toLocaleLowerCase().includes(query);
    }
  });

  calculatorChoiceTable.addEventListener("change", (event) => {
    if (!event.target.matches('input[name="selected_item_uuid"]')) {
      return;
    }
    setRowSelected(event.target.closest(".calculator-choice-row"), event.target.checked);
    updateSelectedCount();
  });

  calculatorSelectVisible.addEventListener("click", () => {
    for (const row of rows) {
      if (!row.hidden) {
        setRowSelected(row, true);
      }
    }
    updateSelectedCount();
  });

  calculatorClearSelection.addEventListener("click", () => {
    for (const row of rows) {
      setRowSelected(row, false);
    }
    updateSelectedCount();
  });

  updateSelectedCount();
}
