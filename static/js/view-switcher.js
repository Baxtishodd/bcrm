(() => {
    "use strict";

    document.querySelectorAll("[data-view-switcher]").forEach((switcher) => {
        switcher.addEventListener("click", (event) => {
            const button = event.target.closest("[data-view-mode]");
            if (!button) return;

            const url = new URL(window.location.href);
            url.searchParams.set("view", button.dataset.viewMode);
            url.searchParams.delete("page");
            window.location.assign(url.toString());
        });
    });
})();
