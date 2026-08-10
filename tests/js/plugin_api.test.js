import assert from "node:assert/strict";
import {test} from "node:test";

import {
    PluginAnnotationApi
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/plugin_api.js";

test("v2 annotation discovery uses the parallel descriptor endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const requests = [];
    globalThis.fetch = async (url) => {
        requests.push(url);
        return {
            ok: true,
            json: async () => ({api_version: "2", occurrences: []})
        };
    };

    try {
        const api = new PluginAnnotationApi("/rdmo");
        await api.listV2("24", "341");
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(
        requests[0],
        "/rdmo/api/v1/ts4nfdi/projects/24/annotations/v2/?page=341"
    );
});

test("legacy detail remains available for native fallback", async () => {
    const originalFetch = globalThis.fetch;
    const requests = [];
    globalThis.fetch = async (url) => {
        requests.push(url);
        return {ok: true, json: async () => ({label: "XML"})};
    };

    try {
        const api = new PluginAnnotationApi("/rdmo");
        await api.detail("24", {value_id: 7, matcher_id: "formats"});
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(
        requests[0],
        "/rdmo/api/v1/ts4nfdi/projects/24/annotations/7/?matcher=formats"
    );
});

test("entity-set provenance uses the scoped v2 click-time endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const requests = [];
    globalThis.fetch = async (url) => {
        requests.push(url);
        return {ok: true, json: async () => ({label: "Workshop"})};
    };

    try {
        const api = new PluginAnnotationApi("/rdmo");
        await api.entitysetProvenance("24", {value_id: 7, matcher_id: "fairagro-data-generation"});
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(
        requests[0],
        "/rdmo/api/v1/ts4nfdi/projects/24/annotations/v2/7/entityset-provenance/?matcher=fairagro-data-generation"
    );
});

test("provider-resource details use the scoped v2 click-time endpoint", async () => {
    const originalFetch = globalThis.fetch;
    const requests = [];
    globalThis.fetch = async (url) => {
        requests.push(url);
        return {ok: true, json: async () => ({label: "NFDI metadata standards"})};
    };

    try {
        const api = new PluginAnnotationApi("/rdmo");
        await api.providerResourceDetail("24", {value_id: 7, matcher_id: "collections"});
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(
        requests[0],
        "/rdmo/api/v1/ts4nfdi/projects/24/annotations/v2/7/provider-resource/?matcher=collections"
    );
});
