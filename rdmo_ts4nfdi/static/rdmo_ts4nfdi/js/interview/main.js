import {InterviewAnnotationController} from "./controller.js";
import {readJsonConfig} from "./core.js";
import {
    NativeAnnotationDrawer,
    NativeInlineAnnotationRenderer
} from "./native_presentation.js";
import {PluginAnnotationApi} from "./plugin_api.js";
import {BrowserPresentationRegistry} from "./presentation_registry.js";
import {RDMOTemplateInterviewHost} from "./rdmo_template_host.js";
import {TssPresentationAdapter} from "./tss_presentation.js";

function boot() {
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
    const controller = new InterviewAnnotationController({
        host,
        api: new PluginAnnotationApi(host.baseUrl()),
        inlineRenderer: new NativeInlineAnnotationRenderer(),
        drawer: new NativeAnnotationDrawer(
            document.getElementById("ts4nfdi-annotation-drawer"),
            presentations
        )
    });
    controller.start();
    window.addEventListener("pagehide", () => controller.stop(), {once: true});
}

boot();
