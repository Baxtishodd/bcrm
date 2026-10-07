(() => {
    "use strict";

    const outputSize = 512;

    document.querySelectorAll("input[data-avatar-editor]").forEach((input) => {
        const form = input.closest("form");
        if (!form) return;

        const editor = document.createElement("div");
        editor.className = "avatar-editor-modal";
        editor.hidden = true;
        editor.innerHTML = `
            <div class="avatar-editor-backdrop" data-avatar-close></div>
            <section class="avatar-editor-dialog" role="dialog" aria-modal="true" aria-label="Avatarni tahrirlash">
                <header><div><p class="eyebrow">Avatar tahriri</p><h2>Yuzni markazga joylashtiring</h2></div><button class="avatar-editor-close" data-avatar-close type="button" aria-label="Yopish">×</button></header>
                <div class="avatar-editor-stage" data-avatar-stage><canvas width="600" height="600" aria-label="Avatar kesish maydoni"></canvas></div>
                <div class="avatar-editor-controls">
                    <label>Kattalashtirish <input data-avatar-zoom type="range" min="1" max="3" step="0.01" value="1"></label>
                    <button class="avatar-editor-icon-button" data-avatar-rotate="-90" type="button" title="Chapga aylantirish" aria-label="Chapga aylantirish">↺</button>
                    <button class="avatar-editor-icon-button" data-avatar-rotate="90" type="button" title="O'ngga aylantirish" aria-label="O'ngga aylantirish">↻</button>
                </div>
                <footer><p>Rasmni tortib suring. Saqlashda kvadrat avatar tayyorlanadi.</p><button class="button" data-avatar-done type="button">Tayyor</button></footer>
            </section>`;
        document.body.append(editor);

        const preview = form.querySelector("[data-avatar-preview]");
        const stage = editor.querySelector("[data-avatar-stage]");
        const canvas = stage.querySelector("canvas");
        const context = canvas.getContext("2d");
        const zoomControl = editor.querySelector("[data-avatar-zoom]");
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
        const updatePreview = () => {
            if (!preview) return;
            preview.innerHTML = "";
            const imagePreview = document.createElement("img");
            imagePreview.src = canvas.toDataURL("image/webp", 0.82);
            imagePreview.alt = "Avatar ko'rinishi";
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
        editor.querySelectorAll("[data-avatar-rotate]").forEach((button) => button.addEventListener("click", () => {
            rotation = (rotation + Number(button.dataset.avatarRotate) + 360) % 360;
            draw();
        }));
        editor.querySelectorAll("[data-avatar-close]").forEach((button) => button.addEventListener("click", close));
        editor.querySelector("[data-avatar-done]").addEventListener("click", () => { updatePreview(); close(); });
        document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !editor.hidden) close(); });

        stage.addEventListener("pointerdown", (event) => {
            if (!image) return;
            dragging = { x: event.clientX, y: event.clientY, offsetX, offsetY };
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

        form.addEventListener("submit", (event) => {
            if (!image) return;
            event.preventDefault();
            const result = document.createElement("canvas");
            result.width = outputSize;
            result.height = outputSize;
            const resultContext = result.getContext("2d");
            resultContext.scale(outputSize / canvas.width, outputSize / canvas.height);
            resultContext.drawImage(canvas, 0, 0);
            result.toBlob((blob) => {
                if (!blob) return;
                const transfer = new DataTransfer();
                transfer.items.add(new File([blob], "avatar.webp", {type: "image/webp"}));
                input.files = transfer.files;
                image = null;
                form.requestSubmit();
            }, "image/webp", 0.88);
        }, true);
    });
})();
