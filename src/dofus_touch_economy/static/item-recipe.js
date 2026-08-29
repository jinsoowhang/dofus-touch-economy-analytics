"use strict";

const recipeCraftQuantity = document.querySelector("#recipe-craft-quantity");
const recipeTotalCostPreview = document.querySelector("#recipe-total-cost-preview");

if (recipeCraftQuantity && recipeTotalCostPreview) {
  const kamaFormatter = new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 20,
  });
  const quantityStorageKey =
    `dofus-item-recipe-craft-quantity-v1:${recipeCraftQuantity.dataset.itemUuid}`;
  const quantityCells = document.querySelectorAll(".recipe-scaled-quantity");
  const totalCostCells = document.querySelectorAll(".recipe-scaled-total-cost");

  try {
    const storedQuantity = Number(window.sessionStorage.getItem(quantityStorageKey));
    window.sessionStorage.removeItem(quantityStorageKey);
    if (Number.isInteger(storedQuantity) && storedQuantity >= 1 && storedQuantity <= 1000) {
      recipeCraftQuantity.value = String(storedQuantity);
    }
  } catch {
    // The preview still works when transient browser storage is unavailable.
  }

  const updateRecipeQuantityPreview = () => {
    const craftQuantity = Number(recipeCraftQuantity.value);
    const isValidQuantity =
      Number.isInteger(craftQuantity) && craftQuantity >= 1 && craftQuantity <= 1000;

    for (const cell of quantityCells) {
      const output = cell.querySelector("output");
      const unitQuantity = Number(cell.dataset.unitQuantity);
      const scaledQuantity = isValidQuantity ? unitQuantity * craftQuantity : null;
      cell.dataset.sortValue = scaledQuantity === null ? "" : String(scaledQuantity);
      output.textContent = scaledQuantity === null ? "—" : kamaFormatter.format(scaledQuantity);
    }

    for (const cell of totalCostCells) {
      const output = cell.querySelector("output");
      const unitTotalCost = cell.dataset.unitTotalCost;
      if (!isValidQuantity || unitTotalCost === "") {
        cell.dataset.sortValue = "";
        output.textContent = "—";
        continue;
      }
      const scaledTotalCost = Number(unitTotalCost) * craftQuantity;
      cell.dataset.sortValue = String(scaledTotalCost);
      output.textContent = kamaFormatter.format(scaledTotalCost);
    }

    const unitRecipeCost = recipeTotalCostPreview.dataset.unitRecipeCost;
    if (unitRecipeCost === "") {
      recipeTotalCostPreview.textContent = "Incomplete";
    } else if (!isValidQuantity) {
      recipeTotalCostPreview.textContent = "—";
    } else {
      recipeTotalCostPreview.textContent =
        `${kamaFormatter.format(Number(unitRecipeCost) * craftQuantity)} kama`;
    }
  };

  for (const form of document.querySelectorAll(".recipe-price-edit-form")) {
    form.addEventListener("submit", () => {
      const craftQuantity = Number(recipeCraftQuantity.value);
      if (!Number.isInteger(craftQuantity) || craftQuantity < 1 || craftQuantity > 1000) {
        return;
      }
      try {
        window.sessionStorage.setItem(quantityStorageKey, String(craftQuantity));
      } catch {
        // Saving the ingredient price does not depend on browser storage.
      }
    });
  }

  recipeCraftQuantity.addEventListener("input", updateRecipeQuantityPreview);
  updateRecipeQuantityPreview();
}
