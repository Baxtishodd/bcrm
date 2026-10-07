document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-email-compose]");
    if (!form) {
        return;
    }

    const contactInput = form.querySelector("[data-contact-email]");
    const recipientInput = form.querySelector("[data-email-recipients]");
    const addContactButton = form.querySelector("[data-add-contact-email]");
    const attachmentInput = form.querySelector("input[type='file'][multiple]");
    const attachmentSummary = form.querySelector("[data-attachment-summary]");

    addContactButton?.addEventListener("click", () => {
        const email = contactInput?.value.trim();
        if (!email || !recipientInput) {
            contactInput?.focus();
            return;
        }
        const current = recipientInput.value
            .split(/[,;\n]+/)
            .map((item) => item.trim())
            .filter(Boolean);
        if (!current.some((item) => item.toLowerCase() === email.toLowerCase())) {
            current.push(email);
        }
        recipientInput.value = current.join(", ");
        contactInput.value = "";
        contactInput.focus();
    });

    contactInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            addContactButton?.click();
        }
    });

    attachmentInput?.addEventListener("change", () => {
        if (!attachmentSummary) {
            return;
        }
        const count = attachmentInput.files?.length || 0;
        attachmentSummary.textContent = count
            ? `${count} ta fayl tanlandi.`
            : "Bir nechta fayl tanlash mumkin. Har bir fayl 10 MB gacha.";
    });
});
