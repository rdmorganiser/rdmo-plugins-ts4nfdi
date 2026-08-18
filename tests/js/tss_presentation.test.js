import assert from "node:assert/strict";
import {test} from "node:test";

import {
    TssPresentationAdapter
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/tss_presentation.js";

function element(tagName) {
    return {
        tagName,
        children: [],
        className: "",
        textContent: "",
        dataset: {},
        listeners: {},
        classList: {add() {}},
        appendChild(child) { this.children.push(child); },
        replaceChildren(...children) { this.children = children; },
        addEventListener(name, callback) { this.listeners[name] = callback; },
        removeEventListener(name) { delete this.listeners[name]; }
    };
}

test("TSS presentations mount only when their optional disclosure is opened", async () => {
    const originalDocument = globalThis.document;
    const originalWindow = globalThis.window;
    const calls = [];
    let destroyed = 0;
    globalThis.document = {
        createElement: element,
        getElementById: () => null,
        head: element("head"),
        body: element("body")
    };
    globalThis.window = {
        ts4nfdiWidgets: {
            createEntityInfo(props, container) {
                calls.push([props, container]);
                return {destroy: () => destroyed++};
            }
        }
    };

    try {
        const host = element("host");
        const adapter = new TssPresentationAdapter({baseUrl: "/rdmo"});
        const cleanup = adapter.render(
            host,
            {
                adapter: "tss",
                component: "entity-info",
                props: {
                    api: "https://gateway.example/ols4/api/",
                    iri: "https://example.test/entity",
                    useLegacy: false
                }
            },
            {signal: new AbortController().signal}
        );

        assert.equal(host.children.length, 1);
        assert.equal(host.children[0].tagName, "details");
        assert.equal(calls.length, 0);

        host.children[0].open = true;
        await host.children[0].listeners.toggle();

        assert.equal(calls.length, 1);
        assert.equal(calls[0][0].api, "https://gateway.example/ols4/api/");
        assert.equal(calls[0][0].useLegacy, false);
        cleanup();
        assert.equal(destroyed, 1);
    } finally {
        globalThis.document = originalDocument;
        globalThis.window = originalWindow;
    }
});
