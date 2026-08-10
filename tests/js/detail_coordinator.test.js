import assert from "node:assert/strict";
import {test} from "node:test";

import {
    AnnotationDetailCoordinator,
    canUseTssDescriptor,
    requiresEntitysetProvenance,
    requiresProviderResourceDetail,
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

test("provider-resource annotations use their scoped native-detail API and cache the result", async () => {
    let resourceCalls = 0;
    const coordinator = new AnnotationDetailCoordinator({
        api: {
            detail: async () => { throw new Error("legacy detail must not be called"); },
            providerResourceDetail: async () => {
                resourceCalls++;
                return {
                    label: "NFDI metadata standards",
                    metadata_status: "available",
                    definitions: [],
                    presentation: {adapter: "native", component: null, props: {}}
                };
            }
        },
        baseUrl: "/rdmo",
        gateway: {mode: "direct", base_url: "https://gateway.example"}
    });
    const annotation = entityAnnotation({
        kind: "collection",
        provider_resource_detail: true,
        presentation: {adapter: "native", component: null, options: {}},
        gateway_context: null
    });

    const first = await coordinator.resolve("24", annotation);
    const second = await coordinator.resolve("24", annotation);

    assert.equal(requiresProviderResourceDetail(annotation), true);
    assert.equal(resourceCalls, 1);
    assert.equal(first.label, "NFDI metadata standards");
    assert.equal(second, first);
});

test("entity-set provenance promotes compatible OLS2 entries to the TSS path and caches the result", async () => {
    let provenanceCalls = 0;
    const coordinator = new AnnotationDetailCoordinator({
        api: {
            detail: async () => { throw new Error("legacy detail must not be called"); },
            entitysetProvenance: async () => {
                provenanceCalls++;
                return entityAnnotation({
                    source: {
                        id: "tib",
                        label: "TIB Terminology Service",
                        database: "tib",
                        backend_type: "ols2"
                    },
                    terminology: {id: "ncit", label: "ncit"},
                    iri: "http://purl.obolibrary.org/obo/NCIT_C180602",
                    label: "Workshop",
                    gateway_context: {
                        ontology_id: "ncit",
                        database: "tib",
                        backend_type: "ols2",
                        params: {}
                    },
                    presentation: {
                        adapter: "tss",
                        component: "entity-info",
                        options: {}
                    }
                });
            }
        },
        baseUrl: "/rdmo",
        gateway: {mode: "direct", base_url: "https://gateway.example"}
    });
    const annotation = entityAnnotation({
        entityset_provenance: true,
        presentation: {adapter: "native", component: null, options: {}},
        gateway_context: null
    });

    const first = await coordinator.resolve("24", annotation);
    const second = await coordinator.resolve("24", annotation);

    assert.equal(requiresEntitysetProvenance(annotation), true);
    assert.equal(provenanceCalls, 1);
    assert.equal(first.presentation.adapter, "tss");
    assert.equal(first.presentation.props.ontologyId, "ncit");
    assert.equal(second.presentation.props.parameter, "database=tib");
});

test("entity-set provenance retains the native entry detail for unsupported backends", async () => {
    const entryDetail = entityAnnotation({
        source: {
            id: "agrovoc",
            label: "FAO AGROVOC service",
            database: "agrovoc",
            backend_type: "skosmos"
        },
        terminology: {id: "agrovoc", label: "agrovoc"},
        gateway_context: {
            ontology_id: "agrovoc",
            database: "agrovoc",
            backend_type: "skosmos",
            params: {}
        },
        definitions: ["Image-processing definition."],
        presentation: {adapter: "native", component: null, options: {}}
    });
    const coordinator = new AnnotationDetailCoordinator({
        api: {
            detail: async () => { throw new Error("legacy detail must not be called"); },
            entitysetProvenance: async () => entryDetail
        },
        baseUrl: "/rdmo",
        gateway: {mode: "direct", base_url: "https://gateway.example"}
    });

    const detail = await coordinator.resolve(
        "24",
        entityAnnotation({
            entityset_provenance: true,
            presentation: {adapter: "native", component: null, options: {}},
            gateway_context: null
        })
    );

    assert.equal(detail, entryDetail);
    assert.equal(detail.definitions[0], "Image-processing definition.");
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
