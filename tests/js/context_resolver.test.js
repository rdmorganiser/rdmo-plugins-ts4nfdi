import assert from "node:assert/strict";
import {test} from "node:test";

import {
    AnnotationContextCoordinator,
    BrowserGatewaySearchClient,
    resolveGatewaySearchContext
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/context_resolver.js";

const CHOCOLATE_IRI = "http://kmi.open.ac.uk/projects/smartproducts/ontologies/food.owl#Chocolate";

function gatewayResult(overrides = {}) {
    return {
        iri: CHOCOLATE_IRI,
        label: "Chocolate",
        source_name: "agroportal",
        source: "https://data.agroportal.eu",
        ontology: "SPO-FTM",
        short_form: "Chocolate",
        backend_type: "ontoportal",
        ...overrides
    };
}

function annotation(overrides = {}) {
    return {
        value_id: 7,
        label: "Chocolate",
        iri: CHOCOLATE_IRI,
        source: null,
        terminology: null,
        short_form: null,
        gateway_context: null,
        context_resolution: {adapter: "gateway-search"},
        ...overrides
    };
}

test("an exact Gateway IRI recovers the dropdown breadcrumb context", () => {
    const context = resolveGatewaySearchContext(
        [gatewayResult(), gatewayResult({iri: "https://example.test/other"})],
        CHOCOLATE_IRI
    );

    assert.equal(context.source.label, "agroportal");
    assert.equal(context.source.url, "https://data.agroportal.eu");
    assert.equal(context.terminology.label, "SPO-FTM");
    assert.equal(context.short_form, "Chocolate");
    assert.deepEqual(context.gateway_context, {
        ontology_id: "SPO-FTM",
        database: "agroportal",
        backend_type: "ontoportal",
        params: {}
    });
});

test("identical duplicate search contexts are accepted", () => {
    const context = resolveGatewaySearchContext(
        [gatewayResult(), gatewayResult()],
        CHOCOLATE_IRI
    );

    assert.equal(context.terminology.id, "SPO-FTM");
});

test("conflicting contexts for the same IRI fail closed", () => {
    const context = resolveGatewaySearchContext(
        [gatewayResult(), gatewayResult({source_name: "ebi", ontology: "foodon"})],
        CHOCOLATE_IRI
    );

    assert.equal(context, null);
});

test("the coordinator deduplicates repeated annotation requests", async () => {
    const calls = [];
    const coordinator = new AnnotationContextCoordinator({
        client: {
            search: async (projectId, query) => {
                calls.push([projectId, query]);
                return [gatewayResult()];
            }
        }
    });
    const occurrence = {
        key: "7:0:0",
        annotations: [annotation({value_id: 7}), annotation({value_id: 8})]
    };

    const enriched = await coordinator.enrichOccurrence("24", occurrence);

    assert.deepEqual(calls, [["24", "Chocolate"]]);
    assert.equal(enriched.annotations[0].source.id, "agroportal");
    assert.equal(enriched.annotations[1].terminology.id, "SPO-FTM");
});

test("failed browser resolution preserves the fallback annotation", async () => {
    const warnings = [];
    const coordinator = new AnnotationContextCoordinator({
        client: {search: async () => { throw new Error("unavailable"); }},
        logger: {warn: (...args) => warnings.push(args)}
    });
    const original = annotation();

    const enriched = await coordinator.enrichOccurrence(
        "24",
        {key: "7:0:0", annotations: [original]}
    );

    assert.equal(enriched.annotations[0], original);
    assert.equal(warnings.length, 1);
});

test("direct browser mode calls the public Gateway search route", async () => {
    const requests = [];
    const client = new BrowserGatewaySearchClient({
        api: {},
        gateway: {mode: "direct", base_url: "https://gateway.example/api-gateway/"},
        fetchImpl: async (url, options) => {
            requests.push([url, options]);
            return {ok: true, json: async () => []};
        }
    });

    await client.search("24", "Chocolate & milk");

    assert.equal(
        requests[0][0],
        "https://gateway.example/api-gateway/search?query=Chocolate+%26+milk"
    );
    assert.deepEqual(requests[0][1].headers, {Accept: "application/json"});
});

test("direct browser mode binds the native fetch receiver", async () => {
    const originalFetch = globalThis.fetch;
    let receiver = null;
    globalThis.fetch = async function () {
        receiver = this;
        return {ok: true, json: async () => []};
    };

    try {
        const client = new BrowserGatewaySearchClient({
            api: {},
            gateway: {mode: "direct", base_url: "https://gateway.example/api-gateway/"}
        });

        await client.search("24", "Chocolate");
    } finally {
        globalThis.fetch = originalFetch;
    }

    assert.equal(receiver, globalThis);
});

test("proxy browser mode uses the project-authorized search endpoint", async () => {
    const calls = [];
    const client = new BrowserGatewaySearchClient({
        api: {
            gatewaySearch: async (...args) => {
                calls.push(args);
                return [];
            }
        },
        gateway: {mode: "proxy"}
    });

    await client.search("24", "Chocolate");

    assert.deepEqual(calls, [["24", "Chocolate", undefined]]);
});
