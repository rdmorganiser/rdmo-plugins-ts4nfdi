const GATEWAY_SEARCH_ADAPTER = "gateway-search";
const HTTP_IRI = /^https?:\/\//i;

function firstValue(record, fields) {
    for (const field of fields) {
        const value = record?.[field];
        if (Array.isArray(value)) {
            const first = value.find((item) => item != null && String(item).trim());
            if (first != null) {
                return String(first).trim();
            }
        } else if (value != null && String(value).trim()) {
            return String(value).trim();
        }
    }
    return null;
}

export function extractGatewaySearchResults(payload) {
    if (Array.isArray(payload)) {
        return payload;
    }
    if (!payload || typeof payload !== "object") {
        return [];
    }
    for (const candidate of [
        payload.elements,
        payload.results,
        payload.items,
        payload.docs,
        payload.response?.docs
    ]) {
        if (Array.isArray(candidate)) {
            return candidate;
        }
    }
    return [];
}

function normalizeResultContext(result) {
    const sourceName = firstValue(result, ["source_name", "sourceName", "database"]);
    const rawSource = firstValue(result, ["source"]);
    const sourceUrl = rawSource && HTTP_IRI.test(rawSource) ? rawSource : null;
    const sourceLabel = sourceName || (rawSource && !sourceUrl ? rawSource : null);
    const ontologyId = firstValue(result, [
        "ontologyId",
        "ontology_id",
        "ontology_name",
        "ontology"
    ]);
    const shortForm = firstValue(result, ["shortForm", "short_form", "obo_id"]);
    const backendType = firstValue(result, ["backend_type", "backendType"]);

    return {
        source: sourceLabel || sourceUrl ? {
            id: sourceLabel || sourceUrl,
            label: sourceLabel || sourceUrl,
            iri: null,
            url: sourceUrl,
            database: sourceLabel,
            backend_type: backendType
        } : null,
        terminology: ontologyId ? {
            id: ontologyId,
            label: ontologyId,
            iri: null,
            url: null,
            database: null,
            backend_type: null
        } : null,
        short_form: shortForm,
        gateway_context: sourceLabel && ontologyId ? {
            ontology_id: ontologyId,
            database: sourceLabel,
            backend_type: backendType,
            params: {}
        } : null
    };
}

function contextIdentity(context) {
    return JSON.stringify([
        context.source?.id || null,
        context.source?.url || null,
        context.terminology?.id || null,
        context.gateway_context?.backend_type || null
    ]);
}

export function resolveGatewaySearchContext(payload, iri) {
    const matches = extractGatewaySearchResults(payload).filter((result) => (
        firstValue(result, ["iri", "@id", "uri", "id"]) === iri
    ));
    if (!matches.length) {
        return null;
    }

    const contexts = new Map();
    matches.forEach((result) => {
        const context = normalizeResultContext(result);
        contexts.set(contextIdentity(context), context);
    });
    if (contexts.size !== 1) {
        return null;
    }

    const context = contexts.values().next().value;
    return context.source || context.terminology || context.short_form
        ? context
        : null;
}

export class BrowserGatewaySearchClient {
    constructor({api, gateway = {}, fetchImpl = null}) {
        this.api = api;
        this.gateway = gateway || {};
        this.fetchImpl = fetchImpl || globalThis.fetch.bind(globalThis);
    }

    async search(projectId, query, signal) {
        const mode = this.gateway.mode || "proxy";
        if (mode === "proxy") {
            return this.api.gatewaySearch(projectId, query, signal);
        }
        if (mode !== "direct") {
            throw new Error(`Unsupported TS4NFDI Gateway browser mode '${mode}'.`);
        }

        const baseUrl = String(this.gateway.base_url || "").replace(/\/+$/, "");
        if (!HTTP_IRI.test(baseUrl)) {
            throw new Error("Direct Gateway mode requires an HTTP(S) base URL.");
        }
        const url = new URL(`${baseUrl}/search`);
        url.searchParams.set("query", query);
        const response = await this.fetchImpl(url.toString(), {
            signal,
            headers: {"Accept": "application/json"}
        });
        if (!response.ok) {
            throw new Error(`TS4NFDI Gateway search returned HTTP ${response.status}.`);
        }
        return response.json();
    }
}

function requiresGatewaySearch(annotation) {
    return annotation?.context_resolution?.adapter === GATEWAY_SEARCH_ADAPTER
        && Boolean(annotation?.label && annotation?.iri)
        && !(annotation?.source && annotation?.terminology);
}

function mergeContext(annotation, context) {
    if (!context) {
        return annotation;
    }
    return {
        ...annotation,
        short_form: annotation.short_form || context.short_form,
        source: annotation.source || context.source,
        terminology: annotation.terminology || context.terminology,
        gateway_context: annotation.gateway_context || context.gateway_context
    };
}

export class AnnotationContextCoordinator {
    constructor({client, logger = console}) {
        this.client = client;
        this.logger = logger;
        this.contexts = new Map();
    }

    async enrichOccurrence(projectId, occurrence, signal) {
        if (!occurrence?.annotations?.some(requiresGatewaySearch)) {
            return occurrence;
        }
        const annotations = await Promise.all(
            occurrence.annotations.map((annotation) => (
                this.enrichAnnotation(projectId, annotation, signal)
            ))
        );
        const changed = annotations.some(
            (annotation, index) => annotation !== occurrence.annotations[index]
        );
        return changed ? {...occurrence, annotations} : occurrence;
    }

    async enrichAnnotation(projectId, annotation, signal) {
        if (!requiresGatewaySearch(annotation)) {
            return annotation;
        }
        const cacheKey = `${annotation.label}\u0000${annotation.iri}`;
        let contextPromise = this.contexts.get(cacheKey);
        if (!contextPromise) {
            contextPromise = this.client.search(projectId, annotation.label, signal)
                .then((payload) => resolveGatewaySearchContext(payload, annotation.iri))
                .catch((error) => {
                    if (error?.name === "AbortError") {
                        this.contexts.delete(cacheKey);
                        throw error;
                    }
                    this.logger.warn(
                        "Could not resolve TS4NFDI inline annotation context.",
                        error
                    );
                    return null;
                });
            this.contexts.set(cacheKey, contextPromise);
        }
        return mergeContext(annotation, await contextPromise);
    }
}
