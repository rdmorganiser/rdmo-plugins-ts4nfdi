import assert from "node:assert/strict";
import {test} from "node:test";

import {
    AnnotationDetailCoordinator,
    canUseTssDescriptor,
    serializeTssParameters
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/detail_coordinator.js";

function entityAnnotation(overrides = {}) {
    return {
        value_id: 7,
        matcher_id: "formats",
        kind: "entity",
        label: "XML",
        iri: "http://edamontology.org/format_2332",
        badge_label: "EDAM",
        source: {id: "ebi", label: "EBI", database: "ebi", backend_type: "ols2"},
        terminology: {id: "edam", label: "EDAM"},
        gateway_context: {
            ontology_id: "edam",
            database: "ebi",
            backend_type: "ols2",
            params: {collectionId: "collection-1"}
        },
        presentation: {
            adapter: "tss",
            component: "entity-info",
            options: {entity_type: "class"}
        },
        ...overrides
    };
}

test("deterministic TSS descriptors bypass the legacy annotation detail API", async () => {
    let detailCalls = 0;
    const coordinator = new AnnotationDetailCoordinator({
        api: {detail: async () => { detailCalls++; }},
        baseUrl: "/rdmo",
        gateway: {
            mode: "direct",
            base_url: "https://terminology.services.base4nfdi.de/api-gateway"
        }
    });

    const detail = await coordinator.resolve("24", entityAnnotation());

    assert.equal(detailCalls, 0);
    assert.equal(detail.metadata_status, "presentation");
    assert.deepEqual(detail.presentation, {
        adapter: "tss",
        component: "entity-info",
        props: {
            api: "https://terminology.services.base4nfdi.de/api-gateway/ols4/api/",
            parameter: "database=ebi&collectionId=collection-1",
            iri: "http://edamontology.org/format_2332",
            ontologyId: "edam",
            entityType: "class",
            hasTitle: false,
            showBadges: true
        }
    });
});

test("proxy mode uses the existing RDMO Gateway proxy without annotation detail resolution", async () => {
    const coordinator = new AnnotationDetailCoordinator({
        api: {detail: async () => { throw new Error("legacy detail must not be called"); }},
        baseUrl: "/rdmo",
        gateway: {mode: "proxy"}
    });

    const detail = await coordinator.resolve("24", entityAnnotation());

    assert.equal(
        detail.presentation.props.api,
        "/rdmo/api/v1/ts4nfdi/projects/24/gateway/ols4/api/"
    );
});

test("native and under-specified annotations retain the legacy detail path", async () => {
    const calls = [];
    const coordinator = new AnnotationDetailCoordinator({
        api: {
            detail: async (projectId, annotation) => {
                calls.push([projectId, annotation.value_id]);
                return {label: "legacy"};
            }
        },
        baseUrl: "/rdmo",
        gateway: {mode: "direct", base_url: "https://gateway.example"}
    });

    const native = entityAnnotation({presentation: {adapter: "native", options: {}}});
    const unresolved = entityAnnotation({
        gateway_context: {ontology_id: null, database: null, params: {}}
    });

    assert.deepEqual(await coordinator.resolve("24", native), {label: "legacy"});
    assert.deepEqual(await coordinator.resolve("24", unresolved), {label: "legacy"});
    assert.deepEqual(calls, [["24", 7], ["24", 7]]);
});

test("TSS parameter serialization rejects delimiter injection", () => {
    assert.equal(
        serializeTssParameters({database: "ebi", params: {lang: "en"}}),
        "database=ebi&lang=en"
    );
    assert.throws(
        () => serializeTssParameters({database: "ebi&token=secret", params: {}}),
        /Unsafe TSS Gateway parameter/
    );
});

test("entity TSS descriptors require ontology and database context", () => {
    assert.equal(canUseTssDescriptor(entityAnnotation()), true);
    assert.equal(
        canUseTssDescriptor(entityAnnotation({gateway_context: {ontology_id: "edam", database: null}})),
        false
    );
    assert.equal(
        canUseTssDescriptor(entityAnnotation({gateway_context: {ontology_id: null, database: "ebi"}})),
        false
    );
});
