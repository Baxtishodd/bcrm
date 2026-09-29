(() => {
    "use strict";

    const csrfToken = () => {
        const cookie = document.cookie
            .split(";")
            .map((part) => part.trim())
            .find((part) => part.startsWith("csrftoken="));
        return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
    };

    const setupBoard = (board) => {
        let activeItem = null;
        let activeDropBefore = null;
        let touchState = null;
        const updateField = board.dataset.kanbanUpdateField || "status";
        const emptyLabel = board.dataset.kanbanEmptyLabel || "Element yo'q";
        const errorMessage = board.dataset.kanbanErrorMessage || "O'zgarishni saqlab bo'lmadi.";
        const announcer = board.querySelector("[data-kanban-announcer]");

        const announce = (message) => {
            if (announcer) announcer.textContent = message;
        };

        const requestLostReason = () => new Promise((resolve) => {
            const dialog = document.createElement("dialog");
            dialog.className = "kanban-reason-dialog";
            dialog.innerHTML = `
                <form method="dialog" class="kanban-reason-form">
                    <div>
                        <p class="eyebrow">Lead holati</p>
                        <h2>Yutqazish sababini kiriting</h2>
                        <p class="kanban-reason-help">Bu ma'lumot keyingi tahlil va hisobotlarda ishlatiladi.</p>
                    </div>
                    <label for="kanban-lost-reason">Sabab</label>
                    <textarea id="kanban-lost-reason" rows="4" required></textarea>
                    <p class="form-error" data-kanban-reason-error hidden>Sababni kiritish majburiy.</p>
                    <div class="button-row kanban-reason-actions">
                        <button class="button button-secondary" type="button" value="cancel">Bekor qilish</button>
                        <button class="button" type="submit" value="confirm">Yutqazildi deb belgilash</button>
                    </div>
                </form>
            `;
            const form = dialog.querySelector("form");
            const textarea = dialog.querySelector("textarea");
            const error = dialog.querySelector("[data-kanban-reason-error]");
            const cancelButton = dialog.querySelector('button[value="cancel"]');
            let completed = false;

            const finish = (reason = "") => {
                if (completed) return;
                completed = true;
                dialog.remove();
                resolve(reason);
            };

            cancelButton.addEventListener("click", () => {
                dialog.close("cancel");
            });
            form.addEventListener("submit", (event) => {
                const reason = textarea.value.trim();
                if (!reason) {
                    event.preventDefault();
                    error.hidden = false;
                    textarea.focus();
                    return;
                }
                dialog.returnValue = "confirm";
            });
            dialog.addEventListener("close", () => {
                finish(dialog.returnValue === "confirm" ? textarea.value.trim() : "");
            });
            dialog.addEventListener("cancel", (event) => {
                event.preventDefault();
                dialog.close("cancel");
            });

            document.body.append(dialog);
            dialog.showModal();
            textarea.focus();
        });

        const updateColumn = (zone) => {
            if (!zone) return;
            const items = zone.querySelectorAll(":scope > [data-kanban-item]");
            const counter = zone.closest("[data-kanban-column]")?.querySelector("[data-kanban-count]");
            if (counter) counter.textContent = items.length;
            let empty = zone.querySelector(":scope > [data-kanban-empty]");
            if (items.length === 0 && !empty) {
                empty = document.createElement("p");
                empty.className = "kanban-empty";
                empty.dataset.kanbanEmpty = "";
                empty.textContent = emptyLabel;
                zone.append(empty);
            } else if (items.length > 0 && empty) {
                empty.remove();
            }
        };

        const clearDropTargets = () => {
            board.querySelectorAll(".is-drop-target").forEach((zone) => zone.classList.remove("is-drop-target"));
            board.querySelectorAll(".is-insert-before").forEach((item) => item.classList.remove("is-insert-before"));
            board.querySelectorAll(".is-insert-at-end").forEach((zone) => zone.classList.remove("is-insert-at-end"));
        };

        const insertionReference = (zone, clientY, draggedItem) => {
            const cards = Array.from(zone.querySelectorAll(":scope > [data-kanban-item]"))
                .filter((card) => card !== draggedItem);
            return cards.find((card) => {
                const bounds = card.getBoundingClientRect();
                return clientY < bounds.top + bounds.height / 2;
            }) || null;
        };

        const showDropPosition = (zone, beforeItem) => {
            clearDropTargets();
            if (!zone) return;
            zone.classList.add("is-drop-target");
            if (beforeItem) beforeItem.classList.add("is-insert-before");
            else zone.classList.add("is-insert-at-end");
        };

        const autoScroll = (zone, clientY) => {
            if (!zone) return;
            const bounds = zone.getBoundingClientRect();
            const edge = 56;
            if (clientY < bounds.top + edge) zone.scrollBy({ top: -18, behavior: "auto" });
            else if (clientY > bounds.bottom - edge) zone.scrollBy({ top: 18, behavior: "auto" });
        };

        const moveItem = async (item, targetZone, beforeItem = null) => {
            const sourceZone = item.closest("[data-kanban-dropzone]");
            const newValue = targetZone?.dataset.kanbanValue;
            const oldValue = item.dataset.kanbanValue;
            if (!sourceZone || !targetZone || !newValue || item.dataset.kanbanPending) return;

            let lostReason = "";
            if (updateField === "status" && newValue === "lost" && oldValue !== "lost") {
                lostReason = await requestLostReason();
                if (!lostReason) {
                    announce("Yutqazish sababini kiritmasdan Lead yopilmaydi.");
                    return;
                }
            }

            const originalNext = item.nextElementSibling;
            const originalPosition = Array.from(sourceZone.querySelectorAll(":scope > [data-kanban-item]")).indexOf(item);
            const validReference = beforeItem?.parentElement === targetZone && beforeItem !== item ? beforeItem : null;
            targetZone.querySelector(":scope > [data-kanban-empty]")?.remove();
            targetZone.insertBefore(item, validReference);
            const newPosition = Array.from(targetZone.querySelectorAll(":scope > [data-kanban-item]")).indexOf(item);
            if (sourceZone === targetZone && originalPosition === newPosition) return;

            item.dataset.kanbanPending = "true";
            item.classList.add("is-saving");
            item.dataset.kanbanValue = newValue;
            updateColumn(sourceZone);
            updateColumn(targetZone);

            try {
                const response = await fetch(item.dataset.kanbanUpdateUrl, {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": csrfToken(),
                        "X-Requested-With": "XMLHttpRequest",
                    },
                    body: JSON.stringify({
                        [updateField]: newValue,
                        position: newPosition,
                        ...(lostReason ? { lost_reason: lostReason } : {}),
                    }),
                });
                const result = await response.json();
                if (!response.ok) throw new Error(result.error || errorMessage);
                item.classList.add("is-saved");
                window.setTimeout(() => item.classList.remove("is-saved"), 700);
                announce(result.message || "O'zgarish saqlandi.");
            } catch (error) {
                const reference = originalNext?.parentElement === sourceZone ? originalNext : null;
                sourceZone.insertBefore(item, reference);
                item.dataset.kanbanValue = oldValue;
                updateColumn(sourceZone);
                updateColumn(targetZone);
                item.classList.add("is-save-error");
                window.setTimeout(() => item.classList.remove("is-save-error"), 1200);
                announce(error.message || errorMessage);
            } finally {
                delete item.dataset.kanbanPending;
                item.classList.remove("is-saving");
            }
        };

        board.addEventListener("dragstart", (event) => {
            const item = event.target.closest("[data-kanban-item]");
            if (!item || item.dataset.kanbanPending) return;
            activeItem = item;
            item.setAttribute("aria-grabbed", "true");
            item.classList.add("is-dragging");
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", item.dataset.kanbanValue || "");
        });

        board.addEventListener("dragover", (event) => {
            const zone = event.target.closest("[data-kanban-dropzone]");
            if (!activeItem || !zone) return;
            event.preventDefault();
            event.dataTransfer.dropEffect = "move";
            activeDropBefore = insertionReference(zone, event.clientY, activeItem);
            showDropPosition(zone, activeDropBefore);
            autoScroll(zone, event.clientY);
        });

        board.addEventListener("drop", (event) => {
            const zone = event.target.closest("[data-kanban-dropzone]");
            if (!activeItem || !zone) return;
            event.preventDefault();
            activeItem.dataset.kanbanSuppressClick = "true";
            void moveItem(activeItem, zone, activeDropBefore);
            clearDropTargets();
        });

        board.addEventListener("dragend", () => {
            if (activeItem) {
                activeItem.removeAttribute("aria-grabbed");
                activeItem.classList.remove("is-dragging");
                window.setTimeout(() => delete activeItem?.dataset.kanbanSuppressClick, 0);
            }
            activeItem = null;
            activeDropBefore = null;
            clearDropTargets();
        });

        board.addEventListener("click", (event) => {
            const item = event.target.closest("[data-kanban-item]");
            if (item?.dataset.kanbanSuppressClick) {
                event.preventDefault();
                delete item.dataset.kanbanSuppressClick;
            }
        });

        board.addEventListener("pointerdown", (event) => {
            if (event.button !== 0) return;
            const item = event.target.closest("[data-kanban-item]");
            if (!item || item.dataset.kanbanPending) return;
            touchState = {
                item,
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                dragging: false,
                ghost: null,
                zone: null,
                beforeItem: null,
                lastY: event.clientY,
            };
            item.setPointerCapture(event.pointerId);
        });

        board.addEventListener("pointermove", (event) => {
            if (!touchState || event.pointerId !== touchState.pointerId) return;
            const distance = Math.hypot(event.clientX - touchState.startX, event.clientY - touchState.startY);
            if (!touchState.dragging && distance < 10) return;
            event.preventDefault();
            if (!touchState.dragging) {
                touchState.dragging = true;
                touchState.item.classList.add("is-dragging");
                touchState.item.setAttribute("aria-grabbed", "true");
                touchState.ghost = touchState.item.cloneNode(true);
                touchState.ghost.removeAttribute("href");
                touchState.ghost.classList.add("kanban-touch-ghost");
                document.body.append(touchState.ghost);
            }
            touchState.ghost.style.left = `${event.clientX}px`;
            touchState.ghost.style.top = `${event.clientY}px`;
            touchState.ghost.style.width = `${touchState.item.getBoundingClientRect().width}px`;
            touchState.lastY = event.clientY;
            touchState.zone = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-kanban-dropzone]") || null;
            touchState.beforeItem = touchState.zone
                ? insertionReference(touchState.zone, event.clientY, touchState.item)
                : null;
            showDropPosition(touchState.zone, touchState.beforeItem);
            autoScroll(touchState.zone, event.clientY);
        });

        const finishTouch = (event) => {
            if (!touchState || event.pointerId !== touchState.pointerId) return;
            const { item, dragging, ghost, zone, lastY } = touchState;
            if (dragging) {
                event.preventDefault();
                item.dataset.kanbanSuppressClick = "true";
                const beforeItem = zone ? insertionReference(zone, lastY, item) : null;
                void moveItem(item, zone, beforeItem);
                window.setTimeout(() => delete item.dataset.kanbanSuppressClick, 0);
            }
            item.classList.remove("is-dragging");
            item.removeAttribute("aria-grabbed");
            ghost?.remove();
            clearDropTargets();
            touchState = null;
        };

        board.addEventListener("pointerup", finishTouch);
        board.addEventListener("pointercancel", finishTouch);
    };

    document.querySelectorAll("[data-kanban]").forEach(setupBoard);
})();
