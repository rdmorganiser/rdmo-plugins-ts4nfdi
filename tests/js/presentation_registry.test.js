import assert from "node:assert/strict";
import {test} from "node:test";

import {
    BrowserPresentationRegistry
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/presentation_registry.js";

test("the presentation registry dispatches by adapter name", () => {
    const calls = [];
    const host = {
        replaceChildren: () => calls.push("clear")
    };
    const registry = new BrowserPresentationRegistry().register(
        "external",
        {
            render: (element, descriptor) => calls.push([
                "render",
                element,
                descriptor.component
            ])
        }
    );

    registry.render(host, {adapter: "external", component: "concept"});

    assert.deepEqual(calls, [
        "clear",
        ["render", host, "concept"]
    ]);
});

test("native presentation intentionally requires no external adapter", () => {
    const calls = [];
    const registry = new BrowserPresentationRegistry();

    registry.render(
        {replaceChildren: () => calls.push("clear")},
        {adapter: "native"}
    );

    assert.deepEqual(calls, ["clear"]);
});
