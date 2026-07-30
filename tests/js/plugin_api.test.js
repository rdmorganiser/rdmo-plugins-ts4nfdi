import assert from "node:assert/strict";
import {test} from "node:test";

import {
    PluginAnnotationApi
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/plugin_api.js";

test("mapped annotation detail includes its target id", async () => {
    const originalFetch = globalThis.fetch;
    const requests = [];
    globalThis.fetch = async (url) => {
        requests.push(url);
        return {
            ok: true,
            json: async () => ({label: "field experiment"})
        };
    };

    try {
        const api = new PluginAnnotationApi("/rdmo");
        await api.detail("24", {
            value_id: 7,
            matcher_id: "fairagro-data-generation",
            target_id: "inrae-field-experiment"
        });
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(
        requests[0],
        "/rdmo/api/v1/ts4nfdi/projects/24/annotations/7/" +
        "?matcher=fairagro-data-generation&target=inrae-field-experiment"
    );
});
