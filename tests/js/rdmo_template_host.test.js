import assert from "node:assert/strict";
import {test} from "node:test";

import {
    RDMOTemplateInterviewHost
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/rdmo_template_host.js";

function questionElement(values) {
    return {
        querySelectorAll: () => values.map(({text, input = false, primaryText}) => {
            if (input) {
                return {value: text};
            }
            return {
                textContent: text,
                querySelector: () => (
                    primaryText === undefined ? null : {textContent: primaryText}
                )
            };
        })
    };
}

function occurrence(key, annotations) {
    const [, setPrefix = "", setIndex = "0"] = key.split(":");
    return {
        key,
        set_prefix: setPrefix,
        set_index: Number(setIndex),
        annotations
    };
}

function annotation(label, iri) {
    return {
        label,
        iri,
        matcher_id: "formats"
    };
}

test("repeated datasets are matched from their visible multi-select values", () => {
    const host = new RDMOTemplateInterviewHost();
    const xml = occurrence("7:0:0", [
        annotation("XML", "http://edamontology.org/format_2332")
    ]);
    const png = occurrence("7:0:1", [
        annotation("PNG", "http://edamontology.org/format_3603")
    ]);

    assert.equal(
        host.chooseOccurrence(questionElement([{text: " PNG "}]), [xml, png], new Set()),
        png
    );
});

test("the most complete matching occurrence wins for several selected values", () => {
    const host = new RDMOTemplateInterviewHost();
    const xml = occurrence("7:0:0", [
        annotation("XML", "http://edamontology.org/format_2332")
    ]);
    const xmlAndPng = occurrence("7:0:1", [
        annotation("XML", "http://edamontology.org/format_2332"),
        annotation("PNG", "http://edamontology.org/format_3603")
    ]);

    assert.equal(
        host.chooseOccurrence(
            questionElement([{text: "XML"}, {text: "PNG"}]),
            [xml, xmlAndPng],
            new Set()
        ),
        xmlAndPng
    );
});

test("a dataset without a matching selected answer receives no annotation", () => {
    const host = new RDMOTemplateInterviewHost();
    const xml = occurrence("7:0:0", [
        annotation("XML", "http://edamontology.org/format_2332")
    ]);

    assert.equal(
        host.chooseOccurrence(questionElement([{text: "CSV"}]), [xml], new Set()),
        null
    );
    assert.equal(host.chooseOccurrence(questionElement([]), [xml], new Set()), null);
});

test("an occurrence survives a partially changed provider display label", () => {
    const host = new RDMOTemplateInterviewHost();
    const terminology = occurrence("1019::0", [
        annotation("envo", "http://purl.obolibrary.org/obo/envo.owl"),
        annotation("agrovoc", "agrovoc")
    ]);

    assert.equal(
        host.chooseOccurrence(
            questionElement([
                {
                    text: "Environment OntologyFAIRagro TS collectionenvoDescription",
                    primaryText: "Environment Ontology"
                },
                {
                    text: "agrovocFAIRagro TS collectionagrovocDescription",
                    primaryText: "agrovoc"
                }
            ]),
            [terminology],
            new Set()
        ),
        terminology
    );
});

test("ambiguous repeated answers fail closed when their annotations differ", () => {
    const host = new RDMOTemplateInterviewHost();
    const first = occurrence("7:0:0", [
        annotation("Field trial", "https://example.test/concept/one")
    ]);
    const second = occurrence("7:0:1", [
        annotation("Field trial", "https://example.test/concept/two")
    ]);

    assert.equal(
        host.chooseOccurrence(
            questionElement([{text: "Field trial"}]),
            [first, second],
            new Set()
        ),
        null
    );
});

test("identical repeated annotations may share a visually indistinguishable occurrence", () => {
    const host = new RDMOTemplateInterviewHost();
    const first = occurrence("7:0:0", [
        annotation("XML", "http://edamontology.org/format_2332")
    ]);
    const second = occurrence("7:0:1", [
        annotation("XML", "http://edamontology.org/format_2332")
    ]);

    assert.equal(
        host.chooseOccurrence(questionElement([{text: "XML"}]), [first, second], new Set()),
        first
    );
});

test("the active collection-page tab selects its own duplicate annotation", () => {
    const host = new RDMOTemplateInterviewHost();
    const datasetM2 = occurrence("7::1", [
        annotation("YAML", "http://edamontology.org/format_3750")
    ]);
    const datasetD3 = occurrence("7::2", [
        annotation("YAML", "http://edamontology.org/format_3750")
    ]);

    const candidates = host.scopeCandidatesToActivePageSet(
        [datasetM2, datasetD3],
        2
    );

    assert.deepEqual(candidates, [datasetD3]);
    assert.equal(
        host.chooseOccurrence(questionElement([{text: "YAML"}]), candidates, new Set()),
        datasetD3
    );
});

test("a collection page does not borrow annotations from another active tab", () => {
    const host = new RDMOTemplateInterviewHost();
    const datasetM2 = occurrence("7::1", [
        annotation("YAML", "http://edamontology.org/format_3750")
    ]);

    assert.deepEqual(
        host.scopeCandidatesToActivePageSet([datasetM2], 2),
        []
    );
});
