(() => {
    "use strict";

    const normalize = (value) => value.toLocaleLowerCase("uz").trim();
    const instances = [];

    const dependencySelect = (select) => {
        const dependencyName = select.dataset.smartSelectDependsOn;
        if (!dependencyName || !select.form) return null;
        const ownName = select.name || "";
        const suffix = ownName.split("-").pop();
        const prefix = suffix && ownName.endsWith(suffix)
            ? ownName.slice(0, ownName.length - suffix.length)
            : "";
        return select.form.elements[`${prefix}${dependencyName}`]
            || select.form.elements[dependencyName]
            || null;
    };

    const setupSelect = (select, index) => {
        const wrapper = document.createElement("div");
        wrapper.className = "smart-select";

        const input = document.createElement("input");
        input.type = "search";
        input.id = `${select.id || `smart-select-${index}`}-search`;
        input.className = "smart-select-input";
        input.autocomplete = "off";
        input.placeholder = select.dataset.smartSelectPlaceholder || "Qidirish...";
        input.disabled = select.disabled;
        input.setAttribute("role", "combobox");
        input.setAttribute("aria-expanded", "false");
        input.setAttribute("aria-controls", `${input.id}-options`);
        if (select.required) input.setAttribute("aria-required", "true");

        const list = document.createElement("div");
        list.id = `${input.id}-options`;
        list.className = "smart-select-options";
        list.setAttribute("role", "listbox");
        list.hidden = true;

        select.classList.add("smart-select-native");
        select.tabIndex = -1;
        select.setAttribute("aria-hidden", "true");
        select.insertAdjacentElement("afterend", wrapper);
        wrapper.append(input, list);

        const label = select.id ? document.querySelector(`label[for="${select.id}"]`) : null;
        if (label) label.htmlFor = input.id;

        const dependency = dependencySelect(select);

        const eligibleOptions = () => {
            const parentValue = dependency?.value || "";
            return Array.from(select.options).filter((option) => {
                if (!option.value) return false;
                const optionParent = option.dataset.parentValue;
                return !dependency || (parentValue && optionParent === parentValue);
            });
        };

        const selectedLabel = () => {
            const option = select.options[select.selectedIndex];
            return option?.value ? option.text.trim() : "";
        };

        const close = () => {
            list.hidden = true;
            input.setAttribute("aria-expanded", "false");
            input.value = selectedLabel();
        };

        const render = (query = "") => {
            const parentValue = dependency?.value || "";
            const normalizedQuery = normalize(query);
            const options = eligibleOptions().filter((option) => (
                !normalizedQuery || normalize(option.text).includes(normalizedQuery)
            ));
            list.replaceChildren();

            if (dependency && !parentValue) {
                const empty = document.createElement("p");
                empty.className = "smart-select-empty";
                empty.textContent = select.dataset.smartSelectEmpty || "Avval bog'liq maydonni tanlang";
                list.append(empty);
                return;
            }

            if (!options.length) {
                const empty = document.createElement("p");
                empty.className = "smart-select-empty";
                empty.textContent = select.dataset.smartSelectNoResults || "Natija topilmadi";
                list.append(empty);
                return;
            }

            options.forEach((option) => {
                const item = document.createElement("button");
                item.type = "button";
                item.className = "smart-select-option";
                item.textContent = option.text.trim();
                item.dataset.value = option.value;
                item.setAttribute("role", "option");
                item.setAttribute("aria-selected", option.selected ? "true" : "false");
                const chooseOption = () => {
                    select.value = option.value;
                    select.dispatchEvent(new Event("change", { bubbles: true }));
                    close();
                };
                item.addEventListener("click", chooseOption);
                list.append(item);
            });
        };

        const open = () => {
            if (input.disabled) return;
            input.value = "";
            render();
            list.hidden = false;
            input.setAttribute("aria-expanded", "true");
        };

        const refreshDependency = () => {
            const selected = select.options[select.selectedIndex];
            if (
                dependency
                && selected?.value
                && selected.dataset.parentValue !== dependency.value
            ) {
                select.value = "";
                select.dispatchEvent(new Event("change", { bubbles: true }));
            }
            input.disabled = select.disabled || Boolean(dependency && !dependency.value);
            input.placeholder = dependency && !dependency.value
                ? select.dataset.smartSelectEmpty || "Avval bog'liq maydonni tanlang"
                : select.dataset.smartSelectPlaceholder || "Qidirish...";
            close();
        };

        input.value = selectedLabel();
        input.addEventListener("focus", open);
        input.addEventListener("click", open);
        input.addEventListener("input", () => {
            render(input.value);
            list.hidden = false;
        });
        input.addEventListener("keydown", (event) => {
            if (event.key === "Escape") {
                event.preventDefault();
                close();
            } else if (event.key === "ArrowDown") {
                event.preventDefault();
                list.querySelector("button")?.focus();
            }
        });
        select.addEventListener("change", () => {
            input.value = selectedLabel();
        });

        const instance = { select, dependency, wrapper, close, refreshDependency };
        instances.push(instance);
        refreshDependency();
    };

    document.querySelectorAll("select[data-smart-select]").forEach(setupSelect);

    document.addEventListener("change", (event) => {
        instances
            .filter((instance) => instance.dependency === event.target)
            .forEach((instance) => instance.refreshDependency());
    });
    document.addEventListener("click", (event) => {
        instances
            .filter((instance) => !instance.wrapper.contains(event.target))
            .forEach((instance) => instance.close());
    });
})();
