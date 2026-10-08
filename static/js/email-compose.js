document.addEventListener("DOMContentLoaded", () => {
    const host = document.querySelector("[data-email-compose-host]");
    const draftPrefix = "bcrm-email-draft:";
    const maxFiles = 10;
    const maxFileBytes = 10 * 1024 * 1024;
    const maxTotalBytes = 25 * 1024 * 1024;

    const showToast = (message, type = "success") => {
        const toast = document.createElement("div");
        toast.className = `email-toast email-toast-${type}`;
        toast.textContent = message;
        document.body.append(toast);
        window.setTimeout(() => toast.classList.add("is-visible"), 10);
        window.setTimeout(() => {
            toast.classList.remove("is-visible");
            window.setTimeout(() => toast.remove(), 180);
        }, 3200);
    };

    const setupCompose = (windowElement, sourceUrl = window.location.href) => {
        if (!windowElement || windowElement.dataset.emailReady) return;
        windowElement.dataset.emailReady = "true";

        const form = windowElement.querySelector("[data-email-compose]");
        const editor = form?.querySelector("[data-email-editor]");
        const bodyInput = form?.querySelector("[data-email-body]");
        const htmlInput = form?.querySelector("[data-email-body-html]");
        const attachments = form?.querySelector("input[type='file'][multiple]");
        const attachmentList = form?.querySelector("[data-attachment-list]");
        const errors = form?.querySelector("[data-email-errors]");
        const sendButton = form?.querySelector("[type='submit']");
        const draftKey = `${draftPrefix}${sourceUrl}`;
        if (!form || !editor || !bodyInput || !htmlInput) return;

        const syncBody = () => {
            bodyInput.value = editor.innerText.trim();
            htmlInput.value = editor.innerHTML.trim();
        };

        const draftFields = () => ({
            mailbox: form.elements.mailbox?.value || "",
            to: form.elements.to?.value || "",
            cc: form.elements.cc?.value || "",
            bcc: form.elements.bcc?.value || "",
            subject: form.elements.subject?.value || "",
            bodyHtml: editor.innerHTML,
        });

        let draftTimer;
        const saveDraft = () => {
            window.clearTimeout(draftTimer);
            draftTimer = window.setTimeout(() => {
                syncBody();
                try {
                    sessionStorage.setItem(draftKey, JSON.stringify(draftFields()));
                } catch (_error) {
                    // Storage mavjud bo'lmasa forma joriy oynada ishlashda davom etadi.
                }
            }, 250);
        };

        const restoreDraft = () => {
            let draft;
            try {
                draft = JSON.parse(sessionStorage.getItem(draftKey) || "null");
            } catch (_error) {
                draft = null;
            }
            if (!draft) return;
            ["mailbox", "to", "cc", "bcc", "subject"].forEach((name) => {
                if (draft[name] && form.elements[name]) form.elements[name].value = draft[name];
            });
            if (draft.bodyHtml) editor.innerHTML = draft.bodyHtml;
            ["cc", "bcc"].forEach((name) => {
                if (draft[name]) form.querySelector(`[data-email-copy-row="${name}"]`)?.removeAttribute("hidden");
            });
        };

        const setFiles = (files) => {
            if (!attachments) return;
            const transfer = new DataTransfer();
            files.forEach((file) => transfer.items.add(file));
            attachments.files = transfer.files;
        };

        const renderFiles = () => {
            if (!attachments || !attachmentList) return;
            attachmentList.replaceChildren();
            Array.from(attachments.files).forEach((file, index) => {
                const item = document.createElement("div");
                item.className = "email-attachment";
                const name = document.createElement("span");
                name.textContent = file.name;
                const size = document.createElement("small");
                size.textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;
                const remove = document.createElement("button");
                remove.type = "button";
                remove.setAttribute("aria-label", `${file.name} faylini olib tashlash`);
                remove.textContent = "×";
                remove.addEventListener("click", () => {
                    setFiles(Array.from(attachments.files).filter((_file, fileIndex) => fileIndex !== index));
                    renderFiles();
                });
                item.append(name, size, remove);
                attachmentList.append(item);
            });
        };

        const addFiles = (newFiles) => {
            if (!attachments) return;
            const files = [...Array.from(attachments.files), ...Array.from(newFiles)];
            const unique = files.filter((file, index, all) => (
                all.findIndex((candidate) => (
                    candidate.name === file.name
                    && candidate.size === file.size
                    && candidate.lastModified === file.lastModified
                )) === index
            ));
            if (unique.some((file) => file.size > maxFileBytes)) {
                showToast("Har bir fayl 10 MB dan oshmasligi kerak.", "error");
                return;
            }
            if (unique.length > maxFiles) {
                showToast("Ko‘pi bilan 10 ta fayl biriktirish mumkin.", "error");
                return;
            }
            if (unique.reduce((total, file) => total + file.size, 0) > maxTotalBytes) {
                showToast("Fayllarning umumiy hajmi 25 MB dan oshmasligi kerak.", "error");
                return;
            }
            setFiles(unique);
            renderFiles();
        };

        restoreDraft();
        syncBody();
        editor.focus();

        form.addEventListener("input", saveDraft);
        attachments?.addEventListener("change", () => {
            const selected = Array.from(attachments.files);
            setFiles([]);
            addFiles(selected);
        });

        windowElement.addEventListener("dragover", (event) => {
            if (!event.dataTransfer?.types.includes("Files")) return;
            event.preventDefault();
            windowElement.classList.add("is-dragging-files");
        });
        windowElement.addEventListener("dragleave", (event) => {
            if (!windowElement.contains(event.relatedTarget)) {
                windowElement.classList.remove("is-dragging-files");
            }
        });
        windowElement.addEventListener("drop", (event) => {
            if (!event.dataTransfer?.files.length) return;
            event.preventDefault();
            windowElement.classList.remove("is-dragging-files");
            addFiles(event.dataTransfer.files);
        });

        form.querySelectorAll("[data-email-copy-toggle]").forEach((button) => {
            button.addEventListener("click", () => {
                const name = button.dataset.emailCopyToggle;
                const row = form.querySelector(`[data-email-copy-row="${name}"]`);
                row?.removeAttribute("hidden");
                row?.querySelector("input, textarea")?.focus();
            });
        });

        form.querySelectorAll("[data-editor-command]").forEach((button) => {
            button.addEventListener("click", () => {
                editor.focus();
                document.execCommand(button.dataset.editorCommand, false);
                syncBody();
                saveDraft();
            });
        });
        form.querySelector("[data-editor-link]")?.addEventListener("click", () => {
            const url = window.prompt("Havola manzili");
            if (!url) return;
            editor.focus();
            document.execCommand("createLink", false, url);
            syncBody();
            saveDraft();
        });

        const close = ({discard = false} = {}) => {
            syncBody();
            if (discard) {
                try {
                    sessionStorage.removeItem(draftKey);
                } catch (_error) {
                    // Storage mavjud bo'lmasa qo'shimcha amal kerak emas.
                }
            } else {
                saveDraft();
            }
            windowElement.remove();
        };

        form.querySelector("[data-email-minimize]")?.addEventListener("click", () => {
            windowElement.classList.toggle("is-minimized");
        });
        form.querySelector("[data-email-maximize]")?.addEventListener("click", () => {
            windowElement.classList.remove("is-minimized");
            windowElement.classList.toggle("is-maximized");
        });
        form.querySelector("[data-email-close]")?.addEventListener("click", () => close());
        form.querySelector("[data-email-discard]")?.addEventListener("click", () => close({discard: true}));

        form.addEventListener("submit", async (event) => {
            event.preventDefault();
            syncBody();
            errors.hidden = true;
            errors.replaceChildren();
            sendButton.disabled = true;
            form.classList.add("is-submitting");
            try {
                const response = await fetch(form.action, {
                    method: "POST",
                    body: new FormData(form),
                    credentials: "same-origin",
                    headers: {"X-Requested-With": "XMLHttpRequest"},
                });
                const result = await response.json();
                if (!response.ok || !result.ok) {
                    const messages = result.errors
                        ? Object.values(result.errors).flat()
                        : [result.message || "Email yuborilmadi."];
                    messages.forEach((message) => {
                        const item = document.createElement("span");
                        item.textContent = message;
                        errors.append(item);
                    });
                    errors.hidden = false;
                    return;
                }
                try {
                    sessionStorage.removeItem(draftKey);
                } catch (_error) {
                    // Storage mavjud bo'lmasa qo'shimcha amal kerak emas.
                }
                showToast(result.message || "Email yuborildi.");
                windowElement.remove();
            } catch (_error) {
                errors.textContent = "Email yuborilmadi. Ulanishni tekshirib qayta urinib ko‘ring.";
                errors.hidden = false;
            } finally {
                sendButton.disabled = false;
                form.classList.remove("is-submitting");
            }
        });
    };

    const openCompose = async (url) => {
        if (!host) {
            window.location.href = url;
            return;
        }
        try {
            const response = await fetch(url, {
                credentials: "same-origin",
                headers: {"X-Requested-With": "XMLHttpRequest"},
            });
            if (!response.ok) throw new Error("Compose oynasi yuklanmadi.");
            host.innerHTML = await response.text();
            setupCompose(host.querySelector("[data-email-compose-window]"), url);
        } catch (_error) {
            window.location.href = url;
        }
    };

    document.addEventListener("click", (event) => {
        const trigger = event.target.closest("[data-email-compose-trigger]");
        if (!trigger) return;
        event.preventDefault();
        void openCompose(trigger.href);
    });

    setupCompose(document.querySelector("[data-email-compose-window]"));
});
