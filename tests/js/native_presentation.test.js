import assert from "node:assert/strict";
import {test} from "node:test";

import {
    hasSemanticConceptMetadata,
    missingSemanticMetadataMessage
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/native_presentation.js";

test("semantic concept metadata accepts definitions, descriptions, or synonyms", () => {
    assert.equal(
        hasSemanticConceptMetadata({definitions: ["A controlled definition."]}),
        true
    );
    assert.equal(
        hasSemanticConceptMetadata({description: "A scope note."}),
        true
    );
    assert.equal(
        hasSemanticConceptMetadata({synonyms: ["alternative label"]}),
        true
    );
});

test("technical provenance alone is not semantic concept metadata", () => {
    assert.equal(
        hasSemanticConceptMetadata({
            definitions: [],
            synonyms: [],
            source: {id: "agrovoc"},
            ontology_id: "agrovoc",
            short_form: "c_4826"
        }),
        false
    );
});

test("missing metadata messages use the selected resource kind", () => {
    assert.equal(
        missingSemanticMetadataMessage({kind: "ontology"}),
        "The TS4NFDI Gateway did not return a description for this terminology."
    );
    assert.equal(
        missingSemanticMetadataMessage({kind: "collection"}),
        "The TS4NFDI Gateway did not return a description for this collection."
    );
    assert.equal(
        missingSemanticMetadataMessage({kind: "entity"}),
        "The TS4NFDI Gateway did not return a definition or synonyms for this concept."
    );
});
