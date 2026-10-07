document.addEventListener("DOMContentLoaded", () => {
    const inbox = document.querySelector(".message-inbox");
    const messages = document.querySelector(".chat-messages");
    if (messages) {
        messages.scrollTop = messages.scrollHeight;
    }

    const attachmentInput = document.querySelector(".attachment-button input[type='file']");
    const attachmentButton = attachmentInput?.closest(".attachment-button");
    if (attachmentInput && attachmentButton) {
        const defaultTitle = attachmentButton.title;
        attachmentInput.addEventListener("change", () => {
            const file = attachmentInput.files?.[0];
            attachmentButton.classList.toggle("has-file", Boolean(file));
            attachmentButton.title = file?.name || defaultTitle;
        });
    }

    const syncUrl = inbox?.dataset.syncUrl;
    const conversationId = inbox?.dataset.conversationId || "";
    const conversationList = document.querySelector(".conversation-list");
    const filters = document.querySelector(".conversation-filters");
    if (!syncUrl || !conversationList) {
        return;
    }

    let latestMessageId = Number(
        messages?.querySelector(".chat-message:last-of-type")?.dataset.messageId || 0,
    );
    let syncInProgress = false;

    const syncInbox = async () => {
        if (syncInProgress || document.hidden) {
            return;
        }
        syncInProgress = true;
        const params = new URLSearchParams({
            conversation: conversationId,
            after: String(latestMessageId),
        });
        const queryInput = filters?.querySelector("input[name='q']");
        const channelInput = filters?.querySelector("select[name='channel']");
        const mailboxInput = filters?.querySelector("select[name='mailbox']");
        if (queryInput?.value) {
            params.set("q", queryInput.value);
        }
        if (channelInput?.value) {
            params.set("channel", channelInput.value);
        }
        if (mailboxInput?.value) {
            params.set("mailbox", mailboxInput.value);
        }

        try {
            const response = await fetch(`${syncUrl}?${params}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" },
                cache: "no-store",
            });
            if (!response.ok) {
                return;
            }
            const data = await response.json();
            conversationList.innerHTML = data.conversation_list_html;
            if (data.selected_avatar_url) {
                const currentAvatar = document.querySelector(".chat-person .conversation-avatar");
                if (currentAvatar?.tagName === "IMG") {
                    if (currentAvatar.getAttribute("src") !== data.selected_avatar_url) {
                        currentAvatar.src = data.selected_avatar_url;
                    }
                } else if (currentAvatar) {
                    const avatar = document.createElement("img");
                    avatar.className = currentAvatar.className + " conversation-avatar-image";
                    avatar.src = data.selected_avatar_url;
                    avatar.alt = document.querySelector(".chat-person h2")?.textContent || "";
                    currentAvatar.replaceWith(avatar);
                }
            }
            if (messages && data.messages_html) {
                const isNearBottom =
                    messages.scrollHeight - messages.scrollTop - messages.clientHeight < 100;
                messages.querySelector(".chat-empty")?.remove();
                messages.insertAdjacentHTML("beforeend", data.messages_html);
                if (isNearBottom) {
                    messages.scrollTop = messages.scrollHeight;
                }
            }
            latestMessageId = Math.max(latestMessageId, Number(data.latest_message_id || 0));
        } catch (error) {
            // Vaqtinchalik tarmoq xatosida keyingi interval avtomatik qayta urinadi.
        } finally {
            syncInProgress = false;
        }
    };

    const syncTimer = window.setInterval(syncInbox, 2000);
    window.addEventListener("pagehide", () => window.clearInterval(syncTimer), { once: true });
    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) {
            syncInbox();
        }
    });
});
