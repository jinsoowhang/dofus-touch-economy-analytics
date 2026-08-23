"use strict";

const tableSortCollator = new Intl.Collator(undefined, {
  numeric: true,
  sensitivity: "base",
});

const tableSortValue = (cell, type) => {
  const input = cell.querySelector("input:not([type='hidden'])");
  const time = cell.querySelector("time[datetime]");
  const rawValue =
    cell.dataset.sortValue ?? input?.value ?? time?.dateTime ?? cell.textContent.trim();
  if (rawValue === "" || rawValue === "—") {
    return null;
  }
  if (type === "number") {
    const parsed = Number.parseFloat(rawValue.replaceAll(",", "").replace("%", ""));
    return Number.isFinite(parsed) ? parsed : null;
  }
  if (type === "date") {
    const parsed = Date.parse(rawValue);
    return Number.isNaN(parsed) ? null : parsed;
  }
  return rawValue.toLocaleLowerCase();
};

for (const table of document.querySelectorAll("table[data-sortable-table]")) {
  const body = table.tBodies[0];
  const headers = Array.from(table.tHead?.rows[0]?.cells || []);
  if (!body || headers.length === 0) {
    continue;
  }

  for (const [columnIndex, header] of headers.entries()) {
    if (header.hasAttribute("data-sort-disabled")) {
      continue;
    }
    const label = header.textContent.trim();
    const type = header.dataset.sortType || "text";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "sort-header client-sort-header";
    button.setAttribute("aria-label", `Sort by ${label}, ascending`);
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const arrow = document.createElement("span");
    arrow.className = "sort-arrow";
    arrow.setAttribute("aria-hidden", "true");
    button.append(labelElement, arrow);
    header.replaceChildren(button);
    header.setAttribute("aria-sort", "none");

    button.addEventListener("click", () => {
      const direction = header.getAttribute("aria-sort") === "ascending" ? "descending" : "ascending";
      const rows = Array.from(body.rows).map((row, originalIndex) => ({
        row,
        originalIndex,
        value: tableSortValue(row.cells[columnIndex], type),
      }));
      rows.sort((left, right) => {
        if (left.value === null && right.value === null) {
          return left.originalIndex - right.originalIndex;
        }
        if (left.value === null) {
          return 1;
        }
        if (right.value === null) {
          return -1;
        }
        const comparison =
          type === "text"
            ? tableSortCollator.compare(left.value, right.value)
            : left.value - right.value;
        if (comparison === 0) {
          return left.originalIndex - right.originalIndex;
        }
        return direction === "ascending" ? comparison : -comparison;
      });
      for (const row of rows) {
        body.append(row.row);
      }
      for (const otherHeader of headers) {
        if (!otherHeader.hasAttribute("data-sort-disabled")) {
          otherHeader.setAttribute("aria-sort", "none");
          const otherButton = otherHeader.querySelector(".client-sort-header");
          const otherArrow = otherHeader.querySelector(".sort-arrow");
          if (otherButton) {
            otherButton.setAttribute(
              "aria-label",
              `Sort by ${otherButton.firstElementChild.textContent}, ascending`,
            );
          }
          if (otherArrow) {
            otherArrow.textContent = "";
          }
        }
      }
      header.setAttribute("aria-sort", direction);
      arrow.textContent = direction === "ascending" ? "▲" : "▼";
      button.setAttribute(
        "aria-label",
        `Sort by ${label}, ${direction === "ascending" ? "descending" : "ascending"}`,
      );
    });
  }
}
