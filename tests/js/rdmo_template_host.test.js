import assert from "node:assert/strict";
import {test} from "node:test";

import {
    RDMOTemplateInterviewHost
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/rdmo_template_host.js";

function questionElement(values) {
    return {
        querySelectorAll: () => values.map(({text, input = false}) => (
            input ? {value: text} : {textContent: text}
        ))
    };
}

function occurrence(key, annotations) {
    return {key, annotations};
}

function annotation(label, iri, targetId = null) {
    return {
        label,
        iri,
        matcher_id: "formats",
        target_id: targetId
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
