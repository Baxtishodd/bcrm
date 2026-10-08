(() => {
    const root = document.querySelector("[data-sales-analytics]");
    const dataElement = document.getElementById("sales-analytics-data");
    if (!root || !dataElement) return;

    let datasets;
    try {
        datasets = JSON.parse(dataElement.textContent);
    } catch (_error) {
        return;
    }
    if (!datasets.length) return;

    const svgNamespace = "http://www.w3.org/2000/svg";
    const numberFormatter = new Intl.NumberFormat("uz-UZ", {maximumFractionDigits: 2});
    const compactFormatter = new Intl.NumberFormat("uz-UZ", {
        notation: "compact",
        maximumFractionDigits: 1,
    });
    const numeric = (value) => Number(value || 0);
    const svgNode = (name, attributes = {}) => {
        const node = document.createElementNS(svgNamespace, name);
        Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
        return node;
    };
    const addText = (svg, text, x, y, className, anchor = "start") => {
        const node = svgNode("text", {x, y, class: className, "text-anchor": anchor});
        node.textContent = text;
        svg.append(node);
    };

    const chartBase = (container, maxValue) => {
        const width = 720;
        const height = 250;
        const padding = {top: 18, right: 18, bottom: 34, left: 58};
        const plotWidth = width - padding.left - padding.right;
        const plotHeight = height - padding.top - padding.bottom;
        const safeMax = maxValue > 0 ? maxValue : 1;
        const svg = svgNode("svg", {
            viewBox: `0 0 ${width} ${height}`,
            preserveAspectRatio: "xMidYMid meet",
            "aria-hidden": "true",
        });
        container.replaceChildren(svg);
        [0, 0.5, 1].forEach((ratio) => {
            const y = padding.top + plotHeight * ratio;
            svg.append(svgNode("line", {
                x1: padding.left,
                y1: y,
                x2: width - padding.right,
                y2: y,
                class: "chart-grid-line",
            }));
            addText(
                svg,
                compactFormatter.format(safeMax * (1 - ratio)),
                padding.left - 9,
                y + 4,
                "chart-axis-label",
                "end",
            );
        });
        return {svg, width, height, padding, plotWidth, plotHeight, safeMax};
    };

    const drawDailyChart = (container, dataset) => {
        const current = dataset.daily_current.map(numeric);
        const previous = dataset.daily_previous.map(numeric);
        const maxValue = Math.max(0, ...current, ...previous);
        const chart = chartBase(container, maxValue);
        const point = (value, index, total) => {
            const x = chart.padding.left + (total <= 1 ? 0 : index * chart.plotWidth / (total - 1));
            const y = chart.padding.top + chart.plotHeight - value / chart.safeMax * chart.plotHeight;
            return [x, y];
        };
        const line = (values, className) => {
            if (!values.length) return;
            const points = values.map((value, index) => point(value, index, values.length));
            const path = svgNode("polyline", {
                points: points.map(([x, y]) => `${x},${y}`).join(" "),
                class: className,
            });
            chart.svg.append(path);
            points.forEach(([x, y], index) => {
                const dot = svgNode("circle", {cx: x, cy: y, r: 3, class: `${className}-dot`});
                const title = svgNode("title");
                title.textContent = `${dataset.day_labels[index]}-kun: ${numberFormatter.format(values[index])} ${dataset.currency}`;
                dot.append(title);
                chart.svg.append(dot);
            });
        };
        line(previous, "chart-line-previous");
        line(current, "chart-line-current");
        const labelIndexes = [...new Set([0, Math.floor((current.length - 1) / 2), current.length - 1])];
        labelIndexes.forEach((index) => {
            if (index < 0) return;
            const [x] = point(0, index, current.length);
            addText(chart.svg, `${dataset.day_labels[index]}-kun`, x, chart.height - 9, "chart-axis-label", index === 0 ? "start" : index === current.length - 1 ? "end" : "middle");
        });
        container.setAttribute(
            "aria-label",
            `${dataset.currency}: ushbu oy ${numberFormatter.format(numeric(dataset.current_sales))}, o'tgan oy shu davrda ${numberFormatter.format(numeric(dataset.previous_sales))}`,
        );
    };

    const drawMonthlyChart = (container, dataset) => {
        const sales = dataset.monthly_sales.map(numeric);
        const receipts = dataset.monthly_receipts.map(numeric);
        const maxValue = Math.max(0, ...sales, ...receipts);
        const chart = chartBase(container, maxValue);
        const groupWidth = chart.plotWidth / dataset.month_labels.length;
        const barWidth = Math.min(16, groupWidth * 0.3);
        dataset.month_labels.forEach((label, index) => {
            const center = chart.padding.left + groupWidth * index + groupWidth / 2;
            [
                {value: sales[index], x: center - barWidth - 1, className: "chart-bar-sales", name: "Savdo"},
                {value: receipts[index], x: center + 1, className: "chart-bar-receipts", name: "Tushum"},
            ].forEach((bar) => {
                const barHeight = bar.value / chart.safeMax * chart.plotHeight;
                const rect = svgNode("rect", {
                    x: bar.x,
                    y: chart.padding.top + chart.plotHeight - barHeight,
                    width: barWidth,
                    height: Math.max(barHeight, bar.value > 0 ? 2 : 0),
                    rx: 3,
                    class: bar.className,
                });
                const title = svgNode("title");
                title.textContent = `${label} · ${bar.name}: ${numberFormatter.format(bar.value)} ${dataset.currency}`;
                rect.append(title);
                chart.svg.append(rect);
            });
            if (index % 2 === 0 || index === dataset.month_labels.length - 1) {
                addText(chart.svg, label, center, chart.height - 9, "chart-axis-label", "middle");
            }
        });
        container.setAttribute(
            "aria-label",
            `${dataset.currency}: oxirgi 12 oydagi savdo va haqiqiy tushum`,
        );
    };

    const render = (currency) => {
        const dataset = datasets.find((item) => item.currency === currency) || datasets[0];
        ["current_sales", "current_receipts", "outstanding", "average_order"].forEach((metric) => {
            const element = root.querySelector(`[data-analytics-value="${metric}"]`);
            if (element) element.textContent = `${numberFormatter.format(numeric(dataset[metric]))} ${dataset.currency}`;
        });
        const orderCount = root.querySelector('[data-analytics-value="order_count"]');
        if (orderCount) orderCount.textContent = numberFormatter.format(numeric(dataset.order_count));
        root.querySelectorAll("[data-analytics-currency-label]").forEach((element) => {
            element.textContent = dataset.currency;
        });
        const change = root.querySelector("[data-analytics-change]");
        if (change) {
            const percent = dataset.change_percent;
            change.classList.toggle("is-negative", percent !== null && numeric(percent) < 0);
            change.classList.toggle("is-positive", percent !== null && numeric(percent) >= 0);
            change.textContent = percent === null
                ? "Yangi davr"
                : `${numeric(percent) >= 0 ? "+" : ""}${numberFormatter.format(numeric(percent))}% · o'tgan oyga nisbatan`;
        }
        drawDailyChart(root.querySelector('[data-chart="daily"]'), dataset);
        drawMonthlyChart(root.querySelector('[data-chart="monthly"]'), dataset);
    };

    root.querySelector("[data-analytics-currency]")?.addEventListener("change", (event) => {
        render(event.target.value);
    });
    render(datasets[0].currency);
})();
