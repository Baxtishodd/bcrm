(() => {
    const guardedForms = document.querySelectorAll("form[data-submit-guard]");

    function resetForm(form) {
        form.dataset.submitting = "false";
        form.classList.remove("is-submitting");
        form.removeAttribute("aria-busy");

        const button = form.querySelector('button[type="submit"]');
        const label = button?.querySelector("[data-submit-label]");
        const status = form.querySelector("[data-submit-status]");
        if (button) button.disabled = false;
        if (label && label.dataset.originalLabel) {
            label.textContent = label.dataset.originalLabel;
        }
        if (status) {
            status.hidden = true;
            status.textContent = "";
        }
    }

    guardedForms.forEach((form) => {
        const button = form.querySelector('button[type="submit"]');
        const label = button?.querySelector("[data-submit-label]");
        const status = form.querySelector("[data-submit-status]");
        if (!button || !label) return;

        label.dataset.originalLabel = label.textContent.trim();
        form.dataset.submitting = "false";

        form.addEventListener("submit", (event) => {
            if (form.dataset.submitting === "true") {
                event.preventDefault();
                return;
            }
            if (!form.checkValidity()) return;

            form.dataset.submitting = "true";
            form.classList.add("is-submitting");
            form.setAttribute("aria-busy", "true");
            button.disabled = true;
            label.textContent = form.dataset.submitLoadingLabel || "Yuborilmoqda...";
            if (status) {
                status.hidden = false;
                status.textContent = "Email va PDF tayyorlanmoqda...";
            }

            window.setTimeout(() => {
                if (form.dataset.submitting !== "true" || !status) return;
                status.textContent = form.dataset.submitWaitingMessage;
            }, 5000);
        });
    });

    window.addEventListener("pageshow", () => guardedForms.forEach(resetForm));
})();
