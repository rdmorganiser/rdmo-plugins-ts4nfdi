import {removeNullValues, translate} from "./core.js";

const FACTORIES = {
    "metadata": "createMetadata",
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

    render(host, descriptor) {
        host.replaceChildren();
        if (!this.supports(descriptor)) {
            return;
        }

        const disclosure = document.createElement("details");
        disclosure.className = "ts4nfdi-annotation-widget-disclosure";
        const label = document.createElement("summary");
        label.textContent = translate("Additional interactive terminology view");
        disclosure.appendChild(label);

        const container = document.createElement("div");
        container.className = "ts4nfdi-annotation-widget-root";
        disclosure.appendChild(container);
        host.appendChild(disclosure);

        let mounted = false;
        disclosure.addEventListener("toggle", async () => {
            if (!disclosure.open || mounted) {
                return;
            }
            mounted = true;
            container.classList.add("ts4nfdi-annotation-loading");
            container.textContent = translate("Loading interactive terminology view …");
            try {
                await this.loadAssets();
                const factory = window.ts4nfdiWidgets?.[FACTORIES[descriptor.component]];
                if (typeof factory !== "function") {
                    throw new Error(`TSS component '${descriptor.component}' is unavailable.`);
                }
                const props = removeNullValues(descriptor.props || {});
                if (props.api?.startsWith("/")) {
                    props.api = this.baseUrl + props.api;
                }
                container.className = "ts4nfdi-annotation-widget-root";
                container.replaceChildren();
                factory(props, container);
            } catch (error) {
                container.className = "ts4nfdi-annotation-notice";
                container.textContent = translate(
                    "The interactive terminology widget could not be loaded."
                );
                console.warn("Could not mount TSS presentation adapter.", error);
            }
        });
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
            script.addEventListener("load", resolve, {once: true});
            script.addEventListener("error", reject, {once: true});
            document.body.appendChild(script);
        });
        return this.assetsPromise;
    }
}
