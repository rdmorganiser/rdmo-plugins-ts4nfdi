export class BrowserPresentationRegistry {
    constructor() {
        this.adapters = new Map();
        this.cleanups = new WeakMap();
        this.renderTokens = new WeakMap();
        this.abortControllers = new WeakMap();
    }

    register(name, adapter) {
        if (!name || this.adapters.has(name)) {
            throw new Error(`Presentation adapter '${name}' is already registered.`);
        }
        if (!adapter || typeof adapter.render !== "function") {
            throw new TypeError(`Presentation adapter '${name}' must define render().`);
        }
        this.adapters.set(name, adapter);
        return this;
    }

    clear(host) {
        this.renderTokens.set(host, Symbol("cleared"));
        this.abortControllers.get(host)?.abort();
        this.abortControllers.delete(host);
        const cleanup = this.cleanups.get(host);
        this.cleanups.delete(host);
        if (cleanup) {
            try {
                cleanup();
            } catch (error) {
                console.warn("Could not clean up an annotation presentation.", error);
            }
        }
        host.replaceChildren();
    }

    render(host, descriptor, context = {}) {
        this.clear(host);
        if (!descriptor || descriptor.adapter === "native") {
            return;
        }
        const adapter = this.adapters.get(descriptor.adapter);
        if (!adapter) {
            console.warn(`Unknown annotation presentation adapter '${descriptor.adapter}'.`);
            return;
        }

        const token = Symbol(descriptor.adapter);
        const abortController = new AbortController();
        this.renderTokens.set(host, token);
        this.abortControllers.set(host, abortController);
        try {
            const lifecycle = adapter.render(
                host,
                descriptor,
                {
                    ...context,
                    signal: abortController.signal
                }
            );
            if (lifecycle && typeof lifecycle.then === "function") {
                lifecycle
                    .then((resolved) => this.rememberCleanup(host, token, resolved))
                    .catch((error) => {
                        if (this.renderTokens.get(host) === token) {
                            this.clear(host);
                        }
                        if (error?.name !== "AbortError") {
                            console.warn(
                                `Could not render annotation presentation '${descriptor.adapter}'.`,
                                error
                            );
                        }
                    });
            } else {
                this.rememberCleanup(host, token, lifecycle);
            }
        } catch (error) {
            this.clear(host);
            console.warn(
                `Could not render annotation presentation '${descriptor.adapter}'.`,
                error
            );
        }
    }

    rememberCleanup(host, token, lifecycle) {
        const cleanup = this.normalizeCleanup(lifecycle);
        if (!cleanup) {
            return;
        }
        if (this.renderTokens.get(host) === token) {
            this.cleanups.set(host, cleanup);
        } else {
            cleanup();
        }
    }

    normalizeCleanup(lifecycle) {
        if (typeof lifecycle === "function") {
            return lifecycle;
        }
        if (lifecycle && typeof lifecycle.unmount === "function") {
            return () => lifecycle.unmount();
        }
        if (lifecycle && typeof lifecycle.destroy === "function") {
            return () => lifecycle.destroy();
        }
        return null;
    }
}
