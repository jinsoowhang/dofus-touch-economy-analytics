"use strict";

const homeRoot = document.querySelector("#home");
const homeStorageKey = "dofus-home-checklist-v1";
const homeCheckboxes = Array.from(homeRoot.querySelectorAll("[data-task-key]"));
const homeToday = homeRoot.dataset.today;
const homeNextDay = Date.parse(homeRoot.dataset.nextDayAt);
const homeDateFormatter = new Intl.DateTimeFormat("en-CA", {
  timeZone: "America/Los_Angeles", year: "numeric", month: "2-digit", day: "2-digit",
});

const homeCheckDate = () => {
  const parts = Object.fromEntries(homeDateFormatter.formatToParts(new Date()).map(part => [part.type, part.value]));
  if (`${parts.year}-${parts.month}-${parts.day}` !== homeToday) {
    window.location.reload();
    return false;
  }
  return true;
};

const homeUpdateProgress = () => {
  const completed = homeCheckboxes.filter(input => input.checked).length;
  document.querySelector("#home-progress").textContent = `${completed} of ${homeCheckboxes.length} complete`;
  document.querySelector("#home-progress-bar").value = completed;
  for (const input of homeCheckboxes) {
    input.closest(".home-task").classList.toggle("is-complete", input.checked);
  }
  const next = homeCheckboxes.find(input => !input.checked);
  const nextLabel = document.querySelector("#home-next-label");
  const nextLink = document.querySelector("#home-next-link");
  nextLink.hidden = !next;
  if (next) {
    const task = next.closest(".home-task");
    const label = task.querySelector("label").cloneNode(true);
    label.querySelector(".home-step").remove();
    const link = task.querySelector("[data-task-link]");
    nextLabel.textContent = `Up next: ${label.textContent}`;
    nextLink.href = link.href;
    nextLink.textContent = link.textContent;
  } else {
    nextLabel.textContent = "Today's routine is complete. You're all set.";
  }
};

const homeRestore = () => {
  if (!homeCheckDate()) return;
  let completed = [];
  try {
    const stored = JSON.parse(window.localStorage.getItem(homeStorageKey) || "null");
    if (stored?.date === homeToday && Array.isArray(stored.completed)) {
      completed = stored.completed.filter(value => typeof value === "string");
    }
  } catch {
    document.querySelector("#home-storage-error").hidden = false;
  }
  for (const input of homeCheckboxes) {
    input.disabled = false;
    input.checked = completed.includes(input.dataset.taskKey);
  }
  homeUpdateProgress();
};

for (const input of homeCheckboxes) {
  input.addEventListener("change", () => {
    if (!homeCheckDate()) return;
    try {
      window.localStorage.setItem(homeStorageKey, JSON.stringify({
        date: homeToday,
        completed: homeCheckboxes.filter(input => input.checked).map(input => input.dataset.taskKey),
      }));
      document.querySelector("#home-storage-error").hidden = true;
    } catch {
      document.querySelector("#home-storage-error").hidden = false;
    }
    homeUpdateProgress();
  });
}
window.addEventListener("pageshow", homeRestore);
window.addEventListener("storage", event => {
  if (event.key === homeStorageKey || event.key === null) homeRestore();
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") homeCheckDate();
});
window.setTimeout(homeCheckDate, Math.max(0, homeNextDay - Date.now()) + 1000);
homeRestore();
