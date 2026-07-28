(function () {
    "use strict";

    const HOOK_SELECTOR = ".ts4nfdi-annotation-hook";
    const ROW_CLASS = "ts4nfdi-annotation-row";
    const HTTP_IRI = /^https?:\/\//i;
    const controllerScript = document.getElementById("ts4nfdi-annotation-controller");
    const frontendConfig = readJsonConfig("ts4nfdi-frontend-config");
    const annotationConfig = frontendConfig.annotations || {};

    let activeRequest = null;
    let activeDetailRequest = null;
    let activeTrigger = null;
    let currentPageId = null;
    let scanRevision = 0;
    let scanTimer = null;
    let tssAssetsPromise = null;

    function readJsonConfig(id) {
        const element = document.getElementById(id);
        if (!element) {
            return {};
        }

        try {
            return JSON.parse(element.textContent) || {};
        } catch (error) {
            console.warn("Could not parse TS4NFDI frontend configuration.", error);
            return {};
        }
    }

    function getBaseUrl() {
        const meta = document.querySelector('meta[name="baseurl"]');
        return meta ? meta.content.replace(/\/+$/, "") : "";
    }

    function getProjectId() {
        const meta = document.querySelector('meta[name="project"]');
        return meta ? meta.content : null;
    }

    function getPageId() {
        const match = window.location.pathname.match(/\/interview\/(\d+|done)\/?$/);
        return match ? match[1] : null;
    }

    function apiUrl(path) {
        return getBaseUrl() + "/api/v1/ts4nfdi/" + path.replace(/^\/+/, "");
    }

    function discoverQuestionId(questionElement) {
        const idElement = questionElement.querySelector(
            '[id^="question-text-"], [id^="question-help-"]'
        );
        if (idElement) {
            const match = idElement.id.match(/question-(?:text|help)-(\d+)/);
            if (match) {
                return Number(match[1]);
            }
        }

        const ariaElement = questionElement.querySelector(
            "[aria-labelledby], [aria-describedby], [aria-label], [aria-description]"
        );
        if (!ariaElement) {
            return null;
        }

        const ariaText = [
            ariaElement.getAttribute("aria-labelledby"),
            ariaElement.getAttribute("aria-describedby"),
            ariaElement.getAttribute("aria-label"),
            ariaElement.getAttribute("aria-description")
        ].filter(Boolean).join(" ");
        const match = ariaText.match(/question-(?:text|help)-(\d+)/);
        return match ? Number(match[1]) : null;
    }

    function getDisplayedValues(questionElement) {
        const values = Array.from(
            questionElement.querySelectorAll(
                ".react-select__single-value, .text-input input, .textarea-input textarea"
            )
        ).map(function (element) {
            return String("value" in element ? element.value : element.textContent).trim();
        });
        return values.filter(Boolean);
    }

    function chooseOccurrence(questionElement, candidates, usedKeys) {
        const unused = candidates.filter(function (candidate) {
            return !usedKeys.has(candidate.key);
        });
        if (unused.length === 0) {
            return null;
        }

        const displayedValues = getDisplayedValues(questionElement);
        const labelMatch = unused.find(function (candidate) {
            return candidate.annotations.some(function (annotation) {
                return displayedValues.includes(annotation.label);
            });
        });
        return labelMatch || unused[0];
    }

    function annotationFingerprint(annotations) {
        return annotations.map(function (annotation) {
            return [
                annotation.value_id,
                annotation.kind,
                annotation.label,
                annotation.iri,
                annotation.badge_label
            ].join(":");
        }).join("|");
    }

    function renderQuestionAnnotations(hook, occurrence) {
        const annotations = occurrence ? occurrence.annotations : [];
        const fingerprint = annotationFingerprint(annotations);
        if (hook.dataset.annotationFingerprint === fingerprint) {
            return;
        }

        hook.replaceChildren();
        hook.dataset.annotationFingerprint = fingerprint;
        hook.setAttribute("aria-hidden", annotations.length ? "false" : "true");

        annotations.forEach(function (annotation) {
            if (!annotation.iri || !HTTP_IRI.test(annotation.iri)) {
                return;
            }

            const row = document.createElement("div");
            row.className = ROW_CLASS;

            const kindBadge = document.createElement("span");
            kindBadge.className = "ts4nfdi-annotation-badge ts4nfdi-annotation-badge--" + annotation.kind;
            kindBadge.textContent = annotation.kind;
            row.appendChild(kindBadge);

            if (annotation.badge_label) {
                const providerBadge = document.createElement("span");
                providerBadge.className = "ts4nfdi-annotation-badge ts4nfdi-annotation-badge--provider";
                providerBadge.textContent = annotation.badge_label;
                row.appendChild(providerBadge);
            }

            const label = document.createElement("span");
            label.className = "ts4nfdi-annotation-label";
            label.textContent = annotation.label || annotation.iri;
            row.appendChild(label);

            const button = document.createElement("button");
            button.type = "button";
            button.className = "ts4nfdi-annotation-details";
            button.textContent = gettext("Terminology details");
            button.setAttribute(
                "aria-label",
                gettext("Terminology details") + ": " + (annotation.label || annotation.iri)
            );
            button.addEventListener("click", function () {
                openDrawer(annotation, button);
            });
            row.appendChild(button);

            hook.appendChild(row);
        });
    }

    function reconcile(payload, revision) {
        if (revision !== scanRevision) {
            return;
        }

        const occurrencesByQuestion = new Map();
        (payload.occurrences || []).forEach(function (occurrence) {
            const current = occurrencesByQuestion.get(occurrence.question_id) || [];
            current.push(occurrence);
            occurrencesByQuestion.set(occurrence.question_id, current);
        });

        const usedKeys = new Set();
        document.querySelectorAll("#main .interview-question").forEach(function (questionElement) {
            const hook = questionElement.querySelector(HOOK_SELECTOR);
            if (!hook) {
                return;
            }

            const questionId = discoverQuestionId(questionElement);
            const candidates = occurrencesByQuestion.get(questionId) || [];
            const occurrence = chooseOccurrence(questionElement, candidates, usedKeys);
            if (occurrence) {
                usedKeys.add(occurrence.key);
            }
            renderQuestionAnnotations(hook, occurrence);
        });
    }

    async function scan() {
        const projectId = getProjectId();
        const pageId = getPageId();
        const main = document.getElementById("main");

        if (!projectId || !pageId || pageId === "done" || !main) {
            closeDrawer();
            return;
        }

        if (currentPageId !== pageId) {
            currentPageId = pageId;
            closeDrawer();
        }

        const revision = ++scanRevision;
        if (activeRequest) {
            activeRequest.abort();
        }
        activeRequest = new AbortController();

        try {
            const response = await fetch(
                apiUrl("projects/" + projectId + "/annotations/?page=" + encodeURIComponent(pageId)),
                {
                    credentials: "same-origin",
                    signal: activeRequest.signal,
                    headers: { "Accept": "application/json" }
                }
            );
            if (!response.ok) {
                throw new Error("Annotation API returned HTTP " + response.status + ".");
            }
            reconcile(await response.json(), revision);
        } catch (error) {
            if (error.name !== "AbortError") {
                console.warn("Could not load TS4NFDI interview annotations.", error);
            }
        }
    }

    function scheduleScan(delay) {
        window.clearTimeout(scanTimer);
        scanTimer = window.setTimeout(function () {
            const pending = document.getElementById("pending");
            if (!pending || pending.childElementCount === 0) {
                scan();
            }
        }, delay == null ? 150 : delay);
    }

    function getDrawer() {
        return document.getElementById("ts4nfdi-annotation-drawer");
    }

    function setDrawerLoading(annotation) {
        const drawer = getDrawer();
        const title = drawer.querySelector("#ts4nfdi-annotation-drawer-title");
        const summary = drawer.querySelector("#ts4nfdi-annotation-summary");
        const widget = drawer.querySelector("#ts4nfdi-annotation-widget");

        title.textContent = annotation.label || gettext("Terminology details");
        summary.replaceChildren();
        widget.replaceChildren();

        const loading = document.createElement("div");
        loading.className = "ts4nfdi-annotation-loading";
        loading.setAttribute("role", "status");
        loading.textContent = gettext("Loading terminology details …");
        summary.appendChild(loading);
    }

    async function openDrawer(annotation, trigger) {
        const drawer = getDrawer();
        if (!drawer) {
            return;
        }

        if (activeDetailRequest) {
            activeDetailRequest.abort();
        }
        activeDetailRequest = new AbortController();

        activeTrigger = trigger;
        drawer.hidden = false;
        drawer.setAttribute("aria-hidden", "false");
        document.body.classList.add("ts4nfdi-annotation-drawer-open");
        setDrawerLoading(annotation);
        drawer.querySelector(".ts4nfdi-annotation-panel").focus();

        try {
            const response = await fetch(
                apiUrl(
                    "projects/" + getProjectId() + "/annotations/" + annotation.value_id +
                    "/?matcher=" + encodeURIComponent(annotation.matcher_id)
                ),
                {
                    credentials: "same-origin",
                    signal: activeDetailRequest.signal,
                    headers: { "Accept": "application/json" }
                }
            );
            if (!response.ok) {
                throw new Error("Annotation detail API returned HTTP " + response.status + ".");
            }
            renderDrawerDetail(await response.json());
        } catch (error) {
            if (error.name !== "AbortError") {
                renderDrawerError(annotation, error);
            }
        }
    }

    function renderDrawerDetail(detail) {
        const drawer = getDrawer();
        const summary = drawer.querySelector("#ts4nfdi-annotation-summary");
        summary.replaceChildren();

        const badges = document.createElement("div");
        badges.className = "ts4nfdi-annotation-summary-badges";
        [
            [detail.kind, detail.kind],
            [detail.ontology_id, "ontology"],
            [detail.source, "source"],
            [detail.version, "version"]
        ].forEach(function (badgeData) {
            if (!badgeData[0]) {
                return;
            }
            const badge = document.createElement("span");
            badge.className = "ts4nfdi-annotation-badge ts4nfdi-annotation-badge--" + badgeData[1];
            badge.textContent = badgeData[0];
            badges.appendChild(badge);
        });
        summary.appendChild(badges);

        if (detail.description) {
            const description = document.createElement("p");
            description.className = "ts4nfdi-annotation-description";
            description.textContent = detail.description;
            summary.appendChild(description);
        }

        const iriLink = document.createElement("a");
        iriLink.className = "ts4nfdi-annotation-iri";
        iriLink.href = detail.iri;
        iriLink.target = "_blank";
        iriLink.rel = "noopener noreferrer";
        iriLink.textContent = detail.iri;
        summary.appendChild(iriLink);

        if (
            detail.metadata_status === "available" &&
            detail.widget &&
            ["metadata", "ontology_info"].includes(detail.widget.type)
        ) {
            renderTssWidget(detail.widget);
        } else if (detail.metadata_status !== "available") {
            const notice = document.createElement("p");
            notice.className = "ts4nfdi-annotation-notice";
            notice.textContent = gettext(
                "Additional terminology metadata is currently unavailable."
            );
            summary.appendChild(notice);
        }
    }

    async function renderTssWidget(widgetDescriptor) {
        const widgetHost = document.getElementById("ts4nfdi-annotation-widget");
        widgetHost.replaceChildren();
        const container = document.createElement("div");
        container.className = "ts4nfdi-annotation-widget-root";
        widgetHost.appendChild(container);

        try {
            await loadTssAssets();
            const factories = {
                metadata: "createMetadata",
                ontology_info: "createOntologyInfo"
            };
            const factoryName = factories[widgetDescriptor.type];
            const factory = window.ts4nfdiWidgets && window.ts4nfdiWidgets[factoryName];
            if (typeof factory !== "function") {
                throw new Error("The requested TS4NFDI widget is not available.");
            }
            const props = removeNullValues(widgetDescriptor.props || {});
            if (props.api && props.api.startsWith("/")) {
                props.api = getBaseUrl() + props.api;
            }
            factory(props, container);
        } catch (error) {
            container.className = "ts4nfdi-annotation-notice";
            container.textContent = gettext("The interactive terminology widget could not be loaded.");
            console.warn("Could not mount TS4NFDI widget.", error);
        }
    }

    function removeNullValues(value) {
        return Object.fromEntries(
            Object.entries(value).filter(function (entry) {
                return entry[1] != null;
            })
        );
    }

    function loadTssAssets() {
        if (window.ts4nfdiWidgets) {
            return Promise.resolve();
        }
        if (tssAssetsPromise) {
            return tssAssetsPromise;
        }

        tssAssetsPromise = new Promise(function (resolve, reject) {
            const stylesheetUrl = controllerScript && controllerScript.dataset.tssStylesheet;
            const stylesheetIntegrity = controllerScript && controllerScript.dataset.tssStylesheetIntegrity;
            const scriptUrl = controllerScript && controllerScript.dataset.tssScript;
            const scriptIntegrity = controllerScript && controllerScript.dataset.tssScriptIntegrity;
            if (!stylesheetUrl || !scriptUrl) {
                reject(new Error("TS4NFDI asset URLs are missing."));
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

            const existingScript = document.getElementById("ts4nfdi-tss-script");
            if (existingScript) {
                existingScript.addEventListener("load", resolve, { once: true });
                existingScript.addEventListener("error", reject, { once: true });
                return;
            }

            const script = document.createElement("script");
            script.id = "ts4nfdi-tss-script";
            script.src = scriptUrl;
            if (scriptIntegrity) {
                script.integrity = scriptIntegrity;
            }
            script.addEventListener("load", resolve, { once: true });
            script.addEventListener("error", reject, { once: true });
            document.body.appendChild(script);
        });

        return tssAssetsPromise;
    }

    function renderDrawerError(annotation, error) {
        const summary = document.getElementById("ts4nfdi-annotation-summary");
        summary.replaceChildren();

        const message = document.createElement("p");
        message.className = "ts4nfdi-annotation-notice";
        message.textContent = gettext("Terminology details could not be loaded.");
        summary.appendChild(message);

        const retry = document.createElement("button");
        retry.type = "button";
        retry.className = "btn btn-default btn-sm";
        retry.textContent = gettext("Retry");
        retry.addEventListener("click", function () {
            openDrawer(annotation, activeTrigger);
        });
        summary.appendChild(retry);
        console.warn("Could not load TS4NFDI annotation detail.", error);
    }

    function closeDrawer() {
        const drawer = getDrawer();
        if (activeDetailRequest) {
            activeDetailRequest.abort();
            activeDetailRequest = null;
        }
        if (!drawer || drawer.hidden) {
            return;
        }

        drawer.hidden = true;
        drawer.setAttribute("aria-hidden", "true");
        document.body.classList.remove("ts4nfdi-annotation-drawer-open");
        drawer.querySelector("#ts4nfdi-annotation-widget").replaceChildren();
        if (activeTrigger && document.contains(activeTrigger)) {
            activeTrigger.focus();
        }
        activeTrigger = null;
    }

    function trapDrawerFocus(event) {
        const drawer = getDrawer();
        if (!drawer || drawer.hidden || event.key !== "Tab") {
            return;
        }

        const focusable = Array.from(
            drawer.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'
            )
        ).filter(function (element) {
            return element.offsetParent !== null;
        });
        if (focusable.length === 0) {
            event.preventDefault();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    }

    function boot() {
        if (!annotationConfig.enabled || !(annotationConfig.matchers || []).length) {
            return;
        }

        const main = document.getElementById("main");
        if (!main || !getProjectId()) {
            return;
        }

        document.querySelectorAll("[data-ts4nfdi-close]").forEach(function (button) {
            button.addEventListener("click", closeDrawer);
        });
        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeDrawer();
            } else {
                trapDrawerFocus(event);
            }
        });

        const pending = document.getElementById("pending");
        if (pending) {
            new MutationObserver(function () {
                if (pending.childElementCount === 0) {
                    scheduleScan(100);
                }
            }).observe(pending, { childList: true, subtree: true });
        }

        new MutationObserver(function (mutations) {
            const externalMutation = mutations.some(function (mutation) {
                return !(
                    mutation.target instanceof Element &&
                    mutation.target.closest(HOOK_SELECTOR)
                );
            });
            if (externalMutation) {
                scheduleScan(200);
            }
        }).observe(main, { childList: true, subtree: true });

        scheduleScan(300);
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", boot);
    } else {
        boot();
    }
})();
