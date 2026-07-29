import assert from "node:assert/strict";
import {test} from "node:test";

import {
    hasSemanticConceptMetadata
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
