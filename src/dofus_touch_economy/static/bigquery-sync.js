"use strict";

const syncTerminal = document.querySelector("#sync-terminal");
const syncStatus = document.querySelector("#sync-status");
const syncRunButton = document.querySelector("#sync-run-button");

if (syncTerminal && syncStatus && syncRunButton) {
  const statusLabels = {
    idle: "Idle",
    running: "Running",
    succeeded: "Succeeded",
    failed: "Failed",
  };

  const renderStatus = (snapshot) => {
    syncStatus.textContent = statusLabels[snapshot.status] || snapshot.status;
    syncStatus.className = `sync-status sync-status--${snapshot.status}`;
    syncRunButton.disabled = snapshot.status === "running";
    syncRunButton.textContent =
      snapshot.status === "running" ? "Sync in progress…" : "Update BigQuery Now";
    syncTerminal.textContent =
      snapshot.lines.length > 0
        ? snapshot.lines.join("\n")
        : "[ready] No BigQuery sync has run since this web server started.";
    syncTerminal.scrollTop = syncTerminal.scrollHeight;
  };

  const refreshStatus = async () => {
    try {
      const response = await window.fetch("/bigquery-sync/status", {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`status ${response.status}`);
      }
      const snapshot = await response.json();
      renderStatus(snapshot);
      if (snapshot.status === "running") {
        window.setTimeout(refreshStatus, 750);
      }
    } catch (error) {
      syncStatus.textContent = "Status unavailable";
      syncStatus.className = "sync-status sync-status--failed";
      syncTerminal.textContent += `\n[status] Could not refresh progress: ${error.message}`;
    }
  };

  if (syncTerminal.dataset.running === "true") {
    refreshStatus();
  }
}
