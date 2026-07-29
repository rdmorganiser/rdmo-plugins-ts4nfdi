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

test("presentation cleanup runs before replacement and explicit clearing", () => {
    const calls = [];
    const host = {
        replaceChildren: () => calls.push("clear")
    };
    const registry = new BrowserPresentationRegistry().register(
        "external",
        {
            render: (element, descriptor) => {
                calls.push(`render:${descriptor.component}`);
                return () => calls.push(`cleanup:${descriptor.component}`);
            }
        }
    );

    registry.render(host, {adapter: "external", component: "first"});
    registry.render(host, {adapter: "external", component: "second"});
    registry.clear(host);

    assert.deepEqual(calls, [
        "clear",
        "render:first",
        "cleanup:first",
        "clear",
        "render:second",
        "cleanup:second",
        "clear"
    ]);
});

test("presentation adapters must implement render", () => {
    const registry = new BrowserPresentationRegistry();

    assert.throws(
        () => registry.register("invalid", {}),
        /must define render/
    );
});

test("clearing a presentation aborts its render context", () => {
    let signal;
    const host = {replaceChildren() {}};
    const registry = new BrowserPresentationRegistry().register(
        "external",
        {
            render: (element, descriptor, context) => {
                signal = context.signal;
            }
        }
    );

    registry.render(host, {adapter: "external"});
    assert.equal(signal.aborted, false);

    registry.clear(host);
    assert.equal(signal.aborted, true);
});
