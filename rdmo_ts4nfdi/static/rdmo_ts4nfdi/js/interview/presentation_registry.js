export class BrowserPresentationRegistry {
    constructor() {
        this.adapters = new Map();
    }

    register(name, adapter) {
        if (!name || this.adapters.has(name)) {
            throw new Error(`Presentation adapter '${name}' is already registered.`);
        }
        this.adapters.set(name, adapter);
        return this;
    }

    render(host, descriptor) {
        host.replaceChildren();
        if (!descriptor || descriptor.adapter === "native") {
            return;
        }
        const adapter = this.adapters.get(descriptor.adapter);
        if (!adapter) {
            console.warn(`Unknown annotation presentation adapter '${descriptor.adapter}'.`);
            return;
        }
        adapter.render(host, descriptor);
    }
}
