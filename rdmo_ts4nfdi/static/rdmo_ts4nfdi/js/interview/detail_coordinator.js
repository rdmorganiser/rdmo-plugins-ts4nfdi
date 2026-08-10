const TSS_COMPONENTS = new Set(["metadata", "entity-info", "ontology-info"]);
const PUBLIC_GATEWAY_PARAM_KEYS = new Set(["database", "collectionId", "lang"]);

export function canUseTssDescriptor(annotation) {
    const presentation = annotation?.presentation;
    const context = annotation?.gateway_context;
    if (!presentation || presentation.adapter !== "tss") {
        return false;
    }
    if (!TSS_COMPONENTS.has(presentation.component) || !context?.database) {
        return false;
    }
    if (annotation.kind === "entity") {
        return Boolean(annotation.iri && context.ontology_id);
    }
    if (presentation.component === "ontology-info") {
        return Boolean(context.ontology_id);
    }
    return false;
}

export function requiresEntitysetProvenance(annotation) {
    return annotation?.entityset_provenance === true;
}

export function requiresProviderResourceDetail(annotation) {
    return annotation?.provider_resource_detail === true;
}

export function serializeTssParameters(context) {
    const pairs = [
        ["database", context?.database],
        ...Object.entries(context?.params || {})
    ];
    return pairs
        .filter(([key, value]) => PUBLIC_GATEWAY_PARAM_KEYS.has(key) && value != null && value !== "")
        .map(([key, value]) => {
            const stringValue = String(value);
            if (/[&=\u0000-\u001f]/.test(stringValue)) {
                throw new Error(`Unsafe TSS Gateway parameter '${key}'.`);
            }
            return `${key}=${stringValue}`;
        })
        .join("&");
}

export class AnnotationDetailCoordinator {
    constructor({api, baseUrl, gateway = {}}) {
        this.api = api;
        this.baseUrl = String(baseUrl || "").replace(/\/+$/, "");
        this.gateway = gateway || {};
        this.entitysetDetails = new Map();
        this.providerResourceDetails = new Map();
    }

    async resolve(projectId, annotation, signal) {
        if (requiresEntitysetProvenance(annotation)) {
            return this.entitysetDetail(projectId, annotation, signal);
        }
        if (requiresProviderResourceDetail(annotation)) {
            return this.providerResourceDetail(projectId, annotation, signal);
        }
        if (!canUseTssDescriptor(annotation)) {
            return this.api.detail(projectId, annotation, signal);
        }
        return this.tssDetail(projectId, annotation);
    }

    async entitysetDetail(projectId, annotation, signal) {
        const cacheKey = `${projectId}:${annotation.matcher_id}:${annotation.value_id}`;
        let detail = this.entitysetDetails.get(cacheKey);
        if (!detail) {
            detail = await this.api.entitysetProvenance(projectId, annotation, signal);
            this.entitysetDetails.set(cacheKey, detail);
        }
        return canUseTssDescriptor(detail)
            ? this.tssDetail(projectId, detail)
            : detail;
    }

    async providerResourceDetail(projectId, annotation, signal) {
        const cacheKey = `${projectId}:${annotation.matcher_id}:${annotation.value_id}`;
        let detail = this.providerResourceDetails.get(cacheKey);
        if (!detail) {
            detail = await this.api.providerResourceDetail(projectId, annotation, signal);
            this.providerResourceDetails.set(cacheKey, detail);
        }
        return detail;
    }

    tssDetail(projectId, annotation) {
        const context = annotation.gateway_context;
        const presentation = annotation.presentation;
        const props = {
            api: this.ols4ApiBase(projectId),
            parameter: serializeTssParameters(context)
        };

        if (annotation.kind === "entity") {
            props.iri = annotation.iri;
            props.ontologyId = context.ontology_id;
            props.entityType = presentation.options?.entity_type;
        }
        if (presentation.component === "entity-info") {
            props.hasTitle = false;
            props.showBadges = true;
        } else if (presentation.component === "metadata") {
            const tabs = new Set(presentation.options?.tabs || []);
            props.altNamesTab = tabs.has("synonyms");
            props.hierarchyTab = tabs.has("hierarchy");
            props.crossRefTab = tabs.has("crossref");
            props.terminologyInfoTab = tabs.has("ontology");
            props.graphViewTab = tabs.has("graphview");
            props.termDepictionTab = tabs.has("depiction");
            props.entityInfoTab = tabs.has("entityinfo");
            props.entityRelationTab = tabs.has("entityrelations");
            props.copyButton = "right";
        } else if (presentation.component === "ontology-info") {
            props.ontologyId = context.ontology_id;
        }

        const cleanProps = Object.fromEntries(
            Object.entries(props).filter(([, value]) => value != null && value !== "")
        );
        return {
            ...annotation,
            metadata_status: "presentation",
            ontology_id: context.ontology_id,
            definitions: [],
            synonyms: [],
            entity_types: [],
            source: annotation.source || {
                id: context.database,
                label: context.database,
                database: context.database,
                backend_type: context.backend_type
            },
            terminology: annotation.terminology || {
                id: context.ontology_id,
                label: annotation.badge_label || context.ontology_id
            },
            presentation: {
                adapter: "tss",
                component: presentation.component,
                props: cleanProps
            }
        };
    }

    ols4ApiBase(projectId) {
        const mode = this.gateway.mode || "proxy";
        if (mode === "direct") {
            const gatewayBase = String(this.gateway.base_url || "").replace(/\/+$/, "");
            if (!/^https?:\/\//.test(gatewayBase)) {
                throw new Error("Direct Gateway mode requires an HTTP(S) base URL.");
            }
            return `${gatewayBase}/ols4/api/`;
        }
        if (mode === "proxy") {
            return `${this.baseUrl}/api/v1/ts4nfdi/projects/${projectId}/gateway/ols4/api/`;
        }
        throw new Error(`Unsupported TS4NFDI Gateway browser mode '${mode}'.`);
    }
}
