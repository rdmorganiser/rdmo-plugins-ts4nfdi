export const HTTP_IRI = /^https?:\/\//i;

export function translate(message) {
    return typeof window !== "undefined" && typeof window.gettext === "function"
        ? window.gettext(message)
        : message;
}

export function readJsonConfig(id) {
    const element = document.getElementById(id);
    if (!element) {
        return {};
    }

    try {
        return JSON.parse(element.textContent) || {};
    } catch (error) {
        console.warn("Could not parse TS4NFDI frontend configuration.", error);
        return {};
    }
}

export function normalizeResource(resource) {
    if (!resource) {
        return {};
    }
    if (typeof resource === "string") {
        return {id: resource, label: resource};
    }
    return resource;
}

export function removeNullValues(value) {
    return Object.fromEntries(
        Object.entries(value).filter((entry) => entry[1] != null)
    );
}
