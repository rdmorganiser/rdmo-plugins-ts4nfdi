import {InterviewAnnotationController} from "./controller.js";
import {readJsonConfig, translate} from "./core.js";
import {AnnotationDetailCoordinator} from "./detail_coordinator.js";
import {
    NativeAnnotationDrawer,
    NativeInlineAnnotationRenderer
} from "./native_presentation.js";
import {PluginAnnotationApi} from "./plugin_api.js";
import {
    loadConfiguredPresentationAdapters
} from "./presentation_modules.js";
import {BrowserPresentationRegistry} from "./presentation_registry.js";
import {RDMOTemplateInterviewHost} from "./rdmo_template_host.js";
import {TssPresentationAdapter} from "./tss_presentation.js";

async function boot() {
    const frontendConfig = readJsonConfig("ts4nfdi-frontend-config");
    if (!frontendConfig.annotations?.enabled) {
        return;
    }

    const controllerScript = document.getElementById("ts4nfdi-annotation-controller");
    const host = new RDMOTemplateInterviewHost();
    const tssPresentation = new TssPresentationAdapter({
        baseUrl: host.baseUrl(),
        scriptUrl: controllerScript?.dataset.tssScript,
        scriptIntegrity: controllerScript?.dataset.tssScriptIntegrity,
        stylesheetUrl: controllerScript?.dataset.tssStylesheet,
        stylesheetIntegrity: controllerScript?.dataset.tssStylesheetIntegrity
    });
    const presentations = new BrowserPresentationRegistry()
        .register("tss", tssPresentation);
    await loadConfiguredPresentationAdapters(
        presentations,
        frontendConfig.presentation_adapters,
        {
            baseUrl: host.baseUrl(),
            translate
        }
    );

    const api = new PluginAnnotationApi(host.baseUrl());
    const controller = new InterviewAnnotationController({
        host,
        annotations: {
            list: (...args) => api.listV2(...args)
        },
        details: new AnnotationDetailCoordinator({
            api,
            baseUrl: host.baseUrl(),
            gateway: frontendConfig.gateway
        }),
        inlineRenderer: new NativeInlineAnnotationRenderer(),
        drawer: new NativeAnnotationDrawer(
            document.getElementById("ts4nfdi-annotation-drawer"),
            presentations
        )
    });
    controller.start();
    window.addEventListener("pagehide", () => controller.stop(), {once: true});
}

boot().catch((error) => {
    console.warn("Could not start TS4NFDI interview annotations.", error);
});
