(() => {
    "use strict";

    function initializeImageEditors(root = document) {
        root.querySelectorAll("input[data-avatar-editor], input[data-image-editor]").forEach((input) => {
            if (input.dataset.imageEditorReady === "true") return;
            input.dataset.imageEditorReady = "true";

            const isAvatar = input.hasAttribute("data-avatar-editor");
            const aspectParts = (input.dataset.imageEditorAspect || "1/1").split("/").map(Number);
            const aspectWidth = aspectParts[0] > 0 ? aspectParts[0] : 1;
            const aspectHeight = aspectParts[1] > 0 ? aspectParts[1] : 1;
            const canvasWidth = 600;
            const canvasHeight = Math.round(canvasWidth * aspectHeight / aspectWidth);
            const outputWidth = Number(input.dataset.imageEditorWidth) || (isAvatar ? 512 : 1200);
            const outputHeight = Math.round(outputWidth * aspectHeight / aspectWidth);
            const title = input.dataset.imageEditorTitle || (isAvatar ? "Avatarni tahrirlash" : "Rasmni tahrirlash");
            const help = input.dataset.imageEditorHelp || (isAvatar ? "Yuzni markazga joylashtiring." : "Rasmni kadr ichiga joylashtiring.");
            const note = isAvatar ? "Rasmni tortib suring. Saqlashda kvadrat avatar tayyorlanadi." : "Rasmni tortib suring, kattalashtiring yoki aylantiring.";

            const editor = document.createElement("div");
            editor.className = "avatar-editor-modal";
            editor.hidden = true;
            editor.innerHTML = `
                <div class="avatar-editor-backdrop" data-image-close></div>
                <section class="avatar-editor-dialog" role="dialog" aria-modal="true" aria-label="${title}">
                    <header><div><p class="eyebrow">Rasm tahriri</p><h2>${help}</h2></div><button class="avatar-editor-close" data-image-close type="button" aria-label="Yopish">×</button></header>
                    <div class="avatar-editor-stage" data-image-stage><canvas width="${canvasWidth}" height="${canvasHeight}" aria-label="Rasm kesish maydoni"></canvas></div>
                    <div class="avatar-editor-controls">
                        <label>Kattalashtirish <input data-image-zoom type="range" min="1" max="3" step="0.01" value="1"></label>
                        <button class="avatar-editor-icon-button" data-image-rotate="-90" type="button" title="Chapga aylantirish" aria-label="Chapga aylantirish">↺</button>
                        <button class="avatar-editor-icon-button" data-image-rotate="90" type="button" title="O'ngga aylantirish" aria-label="O'ngga aylantirish">↻</button>
                    </div>
                    <footer><p>${note}</p><button class="button" data-image-done type="button">Tayyor</button></footer>
                </section>`;
            document.body.append(editor);

            const scope = input.closest("[data-image-editor-scope]") || input.closest("form");
            const preview = scope?.querySelector("[data-image-preview], [data-avatar-preview]");
            const stage = editor.querySelector("[data-image-stage]");
            stage.style.aspectRatio = `${aspectWidth}/${aspectHeight}`;
            const canvas = stage.querySelector("canvas");
            const context = canvas.getContext("2d");
            const zoomControl = editor.querySelector("[data-image-zoom]");
            let image = null;
            let objectUrl = null;
            let zoom = 1;
            let rotation = 0;
            let offsetX = 0;
            let offsetY = 0;
            let dragging = null;

            const close = () => { editor.hidden = true; document.body.classList.remove("avatar-editor-open"); };
            const open = () => { editor.hidden = false; document.body.classList.add("avatar-editor-open"); };
            const draw = () => {
                context.fillStyle = "#0f172a";
                context.fillRect(0, 0, canvas.width, canvas.height);
                if (!image) return;
                const radians = rotation * Math.PI / 180;
                const sideways = Math.abs(rotation % 180) === 90;
                const width = sideways ? image.height : image.width;
                const height = sideways ? image.width : image.height;
                const scale = Math.max(canvas.width / width, canvas.height / height) * zoom;
                context.save();
                context.translate(canvas.width / 2 + offsetX, canvas.height / 2 + offsetY);
                context.rotate(radians);
                context.drawImage(image, -image.width * scale / 2, -image.height * scale / 2, image.width * scale, image.height * scale);
                context.restore();
            };
            const reset = () => { zoom = 1; rotation = 0; offsetX = 0; offsetY = 0; zoomControl.value = "1"; };
            const showPreview = (source) => {
                if (!preview) return;
                preview.innerHTML = "";
                const imagePreview = document.createElement("img");
                imagePreview.src = source;
                imagePreview.alt = "Tanlangan rasm";
                preview.append(imagePreview);
            };

            input.addEventListener("change", () => {
                const [file] = input.files;
                if (!file || !file.type.match(/^image\/(jpeg|png|webp)$/)) return;
                if (objectUrl) URL.revokeObjectURL(objectUrl);
                objectUrl = URL.createObjectURL(file);
                image = new Image();
                image.onload = () => { reset(); draw(); open(); };
                image.src = objectUrl;
            });
            zoomControl.addEventListener("input", () => { zoom = Number(zoomControl.value); draw(); });
            editor.querySelectorAll("[data-image-rotate]").forEach((button) => button.addEventListener("click", () => {
                rotation = (rotation + Number(button.dataset.imageRotate) + 360) % 360;
                draw();
            }));
            editor.querySelectorAll("[data-image-close]").forEach((button) => button.addEventListener("click", close));
            editor.querySelector("[data-image-done]").addEventListener("click", () => {
                const result = document.createElement("canvas");
                result.width = outputWidth;
                result.height = outputHeight;
                const resultContext = result.getContext("2d");
                resultContext.scale(outputWidth / canvas.width, outputHeight / canvas.height);
                resultContext.drawImage(canvas, 0, 0);
                result.toBlob((blob) => {
                    if (!blob) return;
                    const transfer = new DataTransfer();
                    transfer.items.add(new File([blob], isAvatar ? "avatar.webp" : "product.webp", {type: "image/webp"}));
                    input.files = transfer.files;
                    showPreview(result.toDataURL("image/webp", 0.82));
                    close();
                }, "image/webp", 0.86);
            });
            document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !editor.hidden) close(); });

            stage.addEventListener("pointerdown", (event) => {
                if (!image) return;
                dragging = {x: event.clientX, y: event.clientY, offsetX, offsetY};
                stage.setPointerCapture(event.pointerId);
                stage.classList.add("is-dragging");
            });
            stage.addEventListener("pointermove", (event) => {
                if (!dragging) return;
                const scale = canvas.width / stage.clientWidth;
                offsetX = dragging.offsetX + (event.clientX - dragging.x) * scale;
                offsetY = dragging.offsetY + (event.clientY - dragging.y) * scale;
                draw();
            });
            ["pointerup", "pointercancel"].forEach((eventName) => stage.addEventListener(eventName, () => {
                dragging = null;
                stage.classList.remove("is-dragging");
            }));
        });
    }

    window.initializeImageEditors = initializeImageEditors;
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", () => initializeImageEditors());
    } else {
        initializeImageEditors();
    }
})();
