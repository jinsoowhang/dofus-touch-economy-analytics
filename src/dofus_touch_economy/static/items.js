(() => {
  const scrollStorageKey = "dofus-catalog-price-scroll-position";

  const rememberScrollPosition = () => {
    try {
      sessionStorage.setItem(scrollStorageKey, String(window.scrollY));
    } catch {
      // Saving the price still works when browser storage is unavailable.
    }
  };

  const restoreScrollPosition = () => {
    let storedScrollPosition = null;
    try {
      storedScrollPosition = sessionStorage.getItem(scrollStorageKey);
      sessionStorage.removeItem(scrollStorageKey);
    } catch {
      return;
    }
    const scrollPosition = Number(storedScrollPosition);
    if (storedScrollPosition !== null && Number.isFinite(scrollPosition) && scrollPosition >= 0) {
      requestAnimationFrame(() => window.scrollTo(0, scrollPosition));
    }
  };

  const submitIfChanged = (form) => {
    if (form.dataset.submitting === "true") return;

    const input = form.querySelector("input[name='current_price']");
    if (!input || input.value.trim() === input.dataset.initialValue?.trim()) return;
    if (!input.value.trim() || !input.reportValidity()) return;

    form.dataset.submitting = "true";
    rememberScrollPosition();
    form.requestSubmit();
  };

  const bindPriceForms = (root = document) => {
    root.querySelectorAll(".catalog-current-price-form").forEach((form) => {
      if (form.dataset.priceEditBound === "true") return;
      form.dataset.priceEditBound = "true";

      const input = form.querySelector("input[name='current_price']");
      if (!input) return;
      input.addEventListener("keydown", (event) => {
        if (event.key !== "Enter") return;
        event.preventDefault();
        submitIfChanged(form);
      });
      input.addEventListener("blur", () => submitIfChanged(form));
    });
  };

  restoreScrollPosition();
  bindPriceForms();
  document.body.addEventListener("htmx:afterSwap", (event) => bindPriceForms(event.target));
})();
