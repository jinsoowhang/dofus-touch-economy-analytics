"use strict";

const categorySelect = document.querySelector("#sale-category");
const itemSelect = document.querySelector("#sale-item");

if (categorySelect && itemSelect) {
  const placeholder = itemSelect.options[0];
  const itemOptions = Array.from(itemSelect.options).slice(1);

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
  filterItems();
}
