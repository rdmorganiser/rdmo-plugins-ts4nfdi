export class PluginAnnotationApi {
    constructor(baseUrl) {
        this.baseUrl = String(baseUrl || "").replace(/\/+$/, "");
    }

    list(projectId, pageId, signal) {
        return this.request(
            `projects/${projectId}/annotations/?page=${encodeURIComponent(pageId)}`,
            signal
        );
    }

    listV2(projectId, pageId, signal) {
        return this.request(
            `projects/${projectId}/annotations/v2/?page=${encodeURIComponent(pageId)}`,
            signal
        );
    }

    detail(projectId, annotation, signal) {
        const query = new URLSearchParams({matcher: annotation.matcher_id});
        return this.request(
            `projects/${projectId}/annotations/${annotation.value_id}/` +
            `?${query.toString()}`,
            signal
        );
    }

    entitysetProvenance(projectId, annotation, signal) {
        const query = new URLSearchParams({matcher: annotation.matcher_id});
        return this.request(
            `projects/${projectId}/annotations/v2/${annotation.value_id}/entityset-provenance/` +
            `?${query.toString()}`,
            signal
        );
    }

    providerResourceDetail(projectId, annotation, signal) {
        const query = new URLSearchParams({matcher: annotation.matcher_id});
        return this.request(
            `projects/${projectId}/annotations/v2/${annotation.value_id}/provider-resource/` +
            `?${query.toString()}`,
            signal
        );
    }

    gatewaySearch(projectId, query, signal) {
        const params = new URLSearchParams({query});
        return this.request(
            `projects/${projectId}/gateway/search?${params.toString()}`,
            signal
        );
    }

    async request(path, signal) {
        const response = await fetch(
            `${this.baseUrl}/api/v1/ts4nfdi/${path.replace(/^\/+/, "")}`,
            {
                credentials: "same-origin",
                signal,
                headers: {"Accept": "application/json"}
            }
        );
        if (!response.ok) {
            throw new Error(`TS4NFDI plugin API returned HTTP ${response.status}.`);
        }
        return response.json();
    }
}
