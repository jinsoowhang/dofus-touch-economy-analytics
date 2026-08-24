"use strict";

const siteMenus = Array.from(document.querySelectorAll(".site-menu"));

const closeSiteMenus = (exceptMenu = null) => {
  for (const menu of siteMenus) {
    if (menu !== exceptMenu) {
      menu.open = false;
    }
  }
};

for (const menu of siteMenus) {
  menu.addEventListener("toggle", () => {
    if (menu.open) {
      closeSiteMenus(menu);
    }
  });
}

const eventIsInsideSiteMenu = (event) =>
  event.target instanceof Element && event.target.closest(".site-menu") !== null;

document.addEventListener("pointerdown", (event) => {
  if (!eventIsInsideSiteMenu(event)) {
    closeSiteMenus();
  }
});

document.addEventListener("focusin", (event) => {
  if (!eventIsInsideSiteMenu(event)) {
    closeSiteMenus();
  }
});

document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") {
    return;
  }
  const openMenu = siteMenus.find((menu) => menu.open);
  if (!openMenu) {
    return;
  }
  openMenu.open = false;
  openMenu.querySelector("summary")?.focus();
});
