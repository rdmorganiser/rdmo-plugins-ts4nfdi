import assert from "node:assert/strict";
import {test} from "node:test";

import {
    InterviewAnnotationController
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/controller.js";

function makeHarness({detailError = null} = {}) {
    const calls = {
        clear: 0,
        close: 0,
        details: [],
        errors: [],
        inline: [],
        lists: []
    };
    const occurrence = {key: "7:0:0", annotations: [{value_id: 1}]};
    const host = {
        context: () => ({projectId: "24", pageId: "341", available: true}),
        clearSlots: () => calls.clear++,
        slots: () => [{element: "slot", occurrence}],
        observe: () => () => {}
    };
    const api = {
        list: async (projectId, pageId) => {
            calls.lists.push([projectId, pageId]);
            return {occurrences: [occurrence]};
        },
        detail: async () => {
            if (detailError) {
                throw detailError;
            }
            return {label: "XML"};
        }
    };
    const inlineRenderer = {
        render: (element, current, open) => {
            calls.inline.push([element, current]);
            calls.open = open;
        }
    };
    const drawer = {
        start: () => () => {},
        close: () => calls.close++,
        loading: () => {},
        detail: (payload) => calls.details.push(payload),
        error: (error, retry) => calls.errors.push([error, retry])
    };
    return {
        calls,
        controller: new InterviewAnnotationController({
            host,
            api,
            inlineRenderer,
            drawer
        })
    };
}

test("refresh coordinates the host, plugin API, and inline renderer", async () => {
    const {calls, controller} = makeHarness();

    await controller.refresh();

    assert.deepEqual(calls.lists, [["24", "341"]]);
    assert.equal(calls.inline.length, 1);
    assert.equal(calls.inline[0][0], "slot");
    assert.equal(calls.inline[0][1].key, "7:0:0");
});

test("opening an annotation resolves detail exactly once", async () => {
    const {calls, controller} = makeHarness();

    await controller.open("24", {value_id: 1, matcher_id: "formats"}, "trigger");

    assert.deepEqual(calls.details, [{label: "XML"}]);
    assert.deepEqual(calls.errors, []);
});

test("a failed detail request waits for an explicit retry", async () => {
    const failure = new Error("Gateway unavailable");
    const {calls, controller} = makeHarness({detailError: failure});

    await controller.open("24", {value_id: 1, matcher_id: "formats"}, "trigger");

    assert.equal(calls.errors.length, 1);
    assert.equal(calls.errors[0][0], failure);
    assert.equal(typeof calls.errors[0][1], "function");
    assert.deepEqual(calls.details, []);
});
