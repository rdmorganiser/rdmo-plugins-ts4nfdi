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

    detail(projectId, annotation, signal) {
        const query = new URLSearchParams({
            matcher: annotation.matcher_id
        });
        if (annotation.target_id) {
            query.set("target", annotation.target_id);
        }
        return this.request(
            `projects/${projectId}/annotations/${annotation.value_id}/` +
            `?${query.toString()}`,
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
