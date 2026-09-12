"use strict";

for (const chart of document.querySelectorAll("[data-dashboard-chart]")) {
  const readout = chart.querySelector(".dashboard-chart-readout");
  for (const point of chart.querySelectorAll("[data-chart-description]")) {
    const showValue = () => {
      readout.textContent = point.dataset.chartDescription;
    };
    point.addEventListener("pointerenter", showValue);
    point.addEventListener("focus", showValue);
    point.addEventListener("click", showValue);
  }
}
