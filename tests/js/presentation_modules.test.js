import assert from "node:assert/strict";
import {test} from "node:test";

import {
    loadConfiguredPresentationAdapters
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/presentation_modules.js";
import {
    BrowserPresentationRegistry
} from "../../rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/presentation_registry.js";

test("a deployment-defined module is registered and receives its context", async () => {
    const registry = new BrowserPresentationRegistry();
    const moduleUrl = new URL("./fixtures/custom_adapter.js", import.meta.url).href;

    const registered = await loadConfiguredPresentationAdapters(
        registry,
        [{
            name: "fairagro-concept-card",
            module_url: moduleUrl,
            export: "createConceptCard"
        }],
        {baseUrl: "/rdmo"}
    );
    const host = {
        cleaned: false,
        replaceChildren() {}
    };
    registry.render(
        host,
        {
            adapter: "fairagro-concept-card",
            component: "compact",
            props: {accent: "green"}
        },
        {detail: {label: "XML"}}
    );

    assert.deepEqual(registered, ["fairagro-concept-card"]);
    assert.deepEqual(host.rendered, {
        baseUrl: "/rdmo",
        component: "compact",
        label: "XML"
    });

    registry.clear(host);
    assert.equal(host.cleaned, true);
});
