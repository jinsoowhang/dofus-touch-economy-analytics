"use strict";

const minimumLevel = document.querySelector("#recipe-min-level");
const maximumLevel = document.querySelector("#recipe-max-level");
const minimumLevelOutput = document.querySelector("#recipe-min-level-output");
const maximumLevelOutput = document.querySelector("#recipe-max-level-output");

if (minimumLevel && maximumLevel && minimumLevelOutput && maximumLevelOutput) {
  const updateLevelRange = (changedInput) => {
    if (Number(minimumLevel.value) > Number(maximumLevel.value)) {
      if (changedInput === minimumLevel) {
        maximumLevel.value = minimumLevel.value;
      } else {
        minimumLevel.value = maximumLevel.value;
      }
    }
    minimumLevelOutput.value = minimumLevel.value;
    maximumLevelOutput.value = maximumLevel.value;
  };

  minimumLevel.addEventListener("input", () => updateLevelRange(minimumLevel));
  maximumLevel.addEventListener("input", () => updateLevelRange(maximumLevel));
  updateLevelRange();
}
