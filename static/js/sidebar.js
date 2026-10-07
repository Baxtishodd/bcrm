(() => {
    const shell = document.querySelector(".app-shell");
    const toggle = document.querySelector(".sidebar-toggle");
    if (!shell || !toggle) return;

    const storageKey = "bcrm-sidebar-collapsed";

    const setCollapsed = (collapsed) => {
        shell.classList.toggle("sidebar-collapsed", collapsed);
        toggle.setAttribute("aria-expanded", String(!collapsed));
        const label = collapsed ? "Sidebarni ochish" : "Sidebarni yig‘ish";
        toggle.setAttribute("aria-label", label);
        toggle.setAttribute("title", label);
    };

    let collapsed = false;
    try {
        collapsed = window.localStorage.getItem(storageKey) === "true";
    } catch (_error) {
        // Storage bloklangan bo‘lsa ham toggle joriy sahifada ishlayveradi.
    }
    setCollapsed(collapsed);

    toggle.addEventListener("click", () => {
        collapsed = !shell.classList.contains("sidebar-collapsed");
        setCollapsed(collapsed);
        try {
            window.localStorage.setItem(storageKey, String(collapsed));
        } catch (_error) {
            // Brauzer storage'ga ruxsat bermasa holatni saqlamaslik yetarli.
        }
    });
})();
