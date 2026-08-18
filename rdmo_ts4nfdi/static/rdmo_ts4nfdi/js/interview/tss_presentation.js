import {removeNullValues, translate} from "./core.js";

const FACTORIES = {
    "entity-info": "createEntityInfo",
    "ontology-info": "createOntologyInfo"
};

export class TssPresentationAdapter {
    constructor({baseUrl, scriptUrl, scriptIntegrity, stylesheetUrl, stylesheetIntegrity}) {
        this.baseUrl = baseUrl;
        this.assets = {scriptUrl, scriptIntegrity, stylesheetUrl, stylesheetIntegrity};
        this.assetsPromise = null;
    }

    supports(descriptor) {
        return descriptor && descriptor.adapter === "tss" && FACTORIES[descriptor.component];
    }

    render(host, descriptor, context = {}) {
        if (!this.supports(descriptor)) {
            return;
        }
        return this.renderDisclosure(host, descriptor, context);
    }

    renderDisclosure(host, descriptor, context) {
        const disclosure = document.createElement("details");
        disclosure.className = "ts4nfdi-annotation-widget-disclosure";
        const label = document.createElement("summary");
        label.textContent = translate("Additional interactive terminology view");
        disclosure.appendChild(label);

        const container = document.createElement("div");
        container.className = "ts4nfdi-annotation-widget-root";
        disclosure.appendChild(container);
        host.appendChild(disclosure);

        let disposed = false;
        let mounted = false;
        let widgetCleanup = null;
        const onToggle = async () => {
            if (!disclosure.open || mounted) {
                return;
            }
            mounted = true;
            container.classList.add("ts4nfdi-annotation-loading");
            container.textContent = translate("Loading interactive terminology view …");
            try {
                await this.loadAssets();
                if (disposed || context.signal?.aborted) {
                    return;
                }
                const factory = this.factory(descriptor);
                const props = this.props(descriptor);
                container.className = "ts4nfdi-annotation-widget-root";
                container.replaceChildren();
                widgetCleanup = this.normalizeCleanup(factory(props, container));
            } catch (error) {
                if (disposed || context.signal?.aborted) {
                    return;
                }
                container.className = "ts4nfdi-annotation-notice";
                container.textContent = translate(
                    "The interactive terminology widget could not be loaded."
                );
                console.warn("Could not mount TSS presentation adapter.", error);
            }
        };
        disclosure.addEventListener("toggle", onToggle);

        return () => {
            disposed = true;
            disclosure.removeEventListener("toggle", onToggle);
            widgetCleanup?.();
            container.replaceChildren();
        };
    }

    factory(descriptor) {
        const factory = window.ts4nfdiWidgets?.[FACTORIES[descriptor.component]];
        if (typeof factory !== "function") {
            throw new Error(`TSS component '${descriptor.component}' is unavailable.`);
        }
        return factory;
    }

    props(descriptor) {
        const props = removeNullValues(descriptor.props || {});
        if (props.api?.startsWith("/")) {
            props.api = this.baseUrl + props.api;
        }
        return props;
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

    loadAssets() {
        if (window.ts4nfdiWidgets) {
            return Promise.resolve();
        }
        if (this.assetsPromise) {
            return this.assetsPromise;
        }

        this.assetsPromise = new Promise((resolve, reject) => {
            const {
                scriptUrl,
                scriptIntegrity,
                stylesheetUrl,
                stylesheetIntegrity
            } = this.assets;
            if (!stylesheetUrl || !scriptUrl) {
                reject(new Error("TSS asset URLs are missing."));
                return;
            }

            if (!document.getElementById("ts4nfdi-tss-stylesheet")) {
                const stylesheet = document.createElement("link");
                stylesheet.id = "ts4nfdi-tss-stylesheet";
                stylesheet.rel = "stylesheet";
                stylesheet.href = stylesheetUrl;
                if (stylesheetIntegrity) {
                    stylesheet.integrity = stylesheetIntegrity;
                }
                document.head.appendChild(stylesheet);
            }

            const existing = document.getElementById("ts4nfdi-tss-script");
            if (existing) {
                if (existing.dataset.loadState === "loaded") {
                    resolve();
                    return;
                }
                if (existing.dataset.loadState === "error") {
                    reject(new Error("The TSS script previously failed to load."));
                    return;
                }
                existing.addEventListener("load", resolve, {once: true});
                existing.addEventListener("error", reject, {once: true});
                return;
            }

            const script = document.createElement("script");
            script.id = "ts4nfdi-tss-script";
            script.src = scriptUrl;
            if (scriptIntegrity) {
                script.integrity = scriptIntegrity;
            }
            script.addEventListener("load", () => {
                script.dataset.loadState = "loaded";
                resolve();
            }, {once: true});
            script.addEventListener("error", () => {
                script.dataset.loadState = "error";
                reject(new Error("The TSS script could not be loaded."));
            }, {once: true});
            document.body.appendChild(script);
        });
        return this.assetsPromise;
    }
}
