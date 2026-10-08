(() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    const counters = document.querySelectorAll("[data-count-up]");
    if (!counters.length) return;

    const duration = 650;
    const easeOut = (progress) => 1 - Math.pow(1 - progress, 3);

    counters.forEach((counter) => {
        const target = Number(counter.dataset.countUp);
        if (!Number.isFinite(target) || target <= 0) return;

        const finalText = counter.textContent;
        const startedAt = performance.now();

        const render = (now) => {
            const progress = Math.min((now - startedAt) / duration, 1);
            counter.textContent = String(Math.round(target * easeOut(progress)));
            if (progress < 1) {
                window.requestAnimationFrame(render);
                return;
            }
            counter.textContent = finalText;
        };

        counter.textContent = "0";
        window.requestAnimationFrame(render);
    });
})();
