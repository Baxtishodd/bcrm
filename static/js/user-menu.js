(() => {
    const menu = document.querySelector("[data-user-menu]");
    if (!menu) return;

    const toggle = menu.querySelector("[data-user-menu-toggle]");
    const panel = menu.querySelector("[data-user-menu-panel]");
    if (!toggle || !panel) return;

    const close = ({focusToggle = false} = {}) => {
        panel.hidden = true;
        toggle.setAttribute("aria-expanded", "false");
        menu.classList.remove("is-open");
        if (focusToggle) toggle.focus();
    };

    const open = () => {
        panel.hidden = false;
        toggle.setAttribute("aria-expanded", "true");
        menu.classList.add("is-open");
        panel.querySelector("[role='menuitem']")?.focus();
    };

    toggle.addEventListener("click", () => {
        if (panel.hidden) {
            const shell = document.querySelector(".app-shell");
            if (shell?.classList.contains("sidebar-collapsed")) {
                document.querySelector(".sidebar-toggle")?.click();
            }
            open();
        }
        else close();
    });

    document.addEventListener("click", (event) => {
        if (!panel.hidden && !menu.contains(event.target)) close();
    });

    menu.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && !panel.hidden) {
            event.preventDefault();
            close({focusToggle: true});
        }
    });
})();
