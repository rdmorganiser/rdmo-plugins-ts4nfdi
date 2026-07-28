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
                annotation.badge_label,
                annotation.source && annotation.source.id,
                annotation.terminology && annotation.terminology.id
            ].join(":");
        }).join("|");
    }

    function createBadge(text, modifier, title) {
        if (!text) {
            return null;
        }
        const badge = document.createElement("span");
        badge.className = "ts4nfdi-annotation-badge ts4nfdi-annotation-badge--" + modifier;
        badge.textContent = text;
        if (title) {
            badge.title = title;
        }
        return badge;
    }

    function appendBreadcrumb(parent, segments) {
        const availableSegments = segments.filter(function (segment) {
            return Boolean(segment.text);
        });
        if (!availableSegments.length) {
            return;
        }

        const breadcrumb = document.createElement("span");
        breadcrumb.className = "ts4nfdi-annotation-breadcrumb";
        availableSegments.forEach(function (segment, index) {
            if (index) {
                const separator = document.createElement("span");
                separator.className = "ts4nfdi-annotation-separator";
                separator.textContent = "›";
                separator.setAttribute("aria-hidden", "true");
                breadcrumb.appendChild(separator);
            }
            breadcrumb.appendChild(
                createBadge(segment.text, segment.modifier, segment.title)
            );
        });
        parent.appendChild(breadcrumb);
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

            const row = document.createElement("button");
            row.type = "button";
            row.className = ROW_CLASS;
            row.setAttribute(
                "aria-label",
                gettext("Terminology details") + ": " + (annotation.label || annotation.iri)
            );

            const label = document.createElement("span");
            label.className = "ts4nfdi-annotation-label";
            label.textContent = annotation.label || annotation.iri;
            row.appendChild(label);

            const source = annotation.source || {};
            const terminology = annotation.terminology || {};
            appendBreadcrumb(row, [
                {
                    text: source.label,
                    modifier: "source",
                    title: source.url
                },
                {
                    text: terminology.label || annotation.badge_label,
                    modifier: "ontology",
                    title: terminology.iri
                },
                {
                    text: annotation.label || annotation.kind,
                    modifier: "term",
                    title: annotation.iri
                }
            ]);

            const chevron = document.createElement("span");
            chevron.className = "ts4nfdi-annotation-chevron";
            chevron.textContent = "›";
            chevron.setAttribute("aria-hidden", "true");
            row.appendChild(chevron);

            row.addEventListener("click", function () {
                openDrawer(annotation, row);
            });

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
        const title = drawer.querySelector("#ts4nfdi-annotation-drawer-title");
        const summary = drawer.querySelector("#ts4nfdi-annotation-summary");
        const widgetHost = drawer.querySelector("#ts4nfdi-annotation-widget");
        title.textContent = detail.label || gettext("Terminology details");
        summary.replaceChildren();
        widgetHost.replaceChildren();

        const source = normalizeResource(detail.source);
        const terminology = normalizeResource(detail.terminology);
        const breadcrumbSection = document.createElement("div");
        breadcrumbSection.className = "ts4nfdi-annotation-summary-breadcrumb";
        appendBreadcrumb(breadcrumbSection, [
            {
                text: source.label,
                modifier: "source",
                title: source.url
            },
            {
                text: terminology.label || detail.ontology_id,
                modifier: "ontology",
                title: terminology.iri
            },
            {
                text: detail.short_form || detail.label,
                modifier: "term",
                title: detail.iri
            }
        ]);
        summary.appendChild(breadcrumbSection);

        renderDefinitions(
            summary,
            (detail.definitions && detail.definitions.length)
                ? detail.definitions
                : (detail.description ? [detail.description] : [])
        );
        renderSynonyms(summary, detail.synonyms || []);

        const properties = [
            [gettext("Source"), source.label],
            [gettext("Database"), source.database || source.id],
            [gettext("Backend"), source.backend_type],
            [gettext("Terminology"), terminology.label || detail.ontology_id],
            [gettext("Short form"), detail.short_form],
            [gettext("Type"), (detail.entity_types || []).join(", ")],
            [gettext("Status"), detail.obsolete === true ? gettext("Obsolete") : (
                detail.obsolete === false ? gettext("Current") : null
            )],
            [gettext("Version"), detail.version]
        ];
        renderProperties(summary, properties);
        renderActions(summary, detail, source);

        if (
            detail.metadata_status === "available" &&
            detail.widget &&
            ["metadata", "entity_info", "ontology_info"].includes(detail.widget.type)
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

    function normalizeResource(resource) {
        if (!resource) {
            return {};
        }
        if (typeof resource === "string") {
            return { id: resource, label: resource };
        }
        return resource;
    }

    function renderDefinitions(parent, definitions) {
        const values = definitions.filter(Boolean);
        if (!values.length) {
            return;
        }
        const section = createSection(gettext("Definition"));
        values.forEach(function (definition) {
            const paragraph = document.createElement("p");
            paragraph.className = "ts4nfdi-annotation-description";
            paragraph.textContent = definition;
            section.appendChild(paragraph);
        });
        parent.appendChild(section);
    }

    function renderSynonyms(parent, synonyms) {
        const values = synonyms.filter(Boolean);
        if (!values.length) {
            return;
        }
        const section = createSection(gettext("Synonyms"));
        const list = document.createElement("div");
        list.className = "ts4nfdi-annotation-synonyms";
        values.forEach(function (synonym) {
            list.appendChild(createBadge(synonym, "synonym"));
        });
        section.appendChild(list);
        parent.appendChild(section);
    }

    function createSection(headingText) {
        const section = document.createElement("section");
        section.className = "ts4nfdi-annotation-section";
        const heading = document.createElement("h3");
        heading.textContent = headingText;
        section.appendChild(heading);
        return section;
    }

    function renderProperties(parent, properties) {
        const available = properties.filter(function (property) {
            return property[1] != null && property[1] !== "";
        });
        if (!available.length) {
            return;
        }
        const section = createSection(gettext("Concept information"));
        const list = document.createElement("dl");
        list.className = "ts4nfdi-annotation-properties";
        available.forEach(function (property) {
            const term = document.createElement("dt");
            term.textContent = property[0];
            const description = document.createElement("dd");
            description.textContent = property[1];
            list.appendChild(term);
            list.appendChild(description);
        });
        section.appendChild(list);
        parent.appendChild(section);
    }

    function renderActions(parent, detail, source) {
        const section = createSection(gettext("Links"));
        const actions = document.createElement("div");
        actions.className = "ts4nfdi-annotation-actions";

        if (detail.iri && HTTP_IRI.test(detail.iri)) {
            actions.appendChild(createExternalLink(detail.iri, gettext("Open concept IRI")));
            const copy = document.createElement("button");
            copy.type = "button";
            copy.className = "ts4nfdi-annotation-action";
            copy.textContent = gettext("Copy IRI");
            copy.addEventListener("click", async function () {
                try {
                    await navigator.clipboard.writeText(detail.iri);
                    copy.textContent = gettext("Copied");
                } catch (error) {
                    console.warn("Could not copy terminology IRI.", error);
                }
            });
            actions.appendChild(copy);
        }
        if (source.url && HTTP_IRI.test(source.url)) {
            actions.appendChild(createExternalLink(source.url, gettext("Open source")));
        }
        if (!actions.childElementCount) {
            return;
        }
        section.appendChild(actions);
        parent.appendChild(section);
    }

    function createExternalLink(url, label) {
        const link = document.createElement("a");
        link.className = "ts4nfdi-annotation-action";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        return link;
    }

    function renderTssWidget(widgetDescriptor) {
        const widgetHost = document.getElementById("ts4nfdi-annotation-widget");
        widgetHost.replaceChildren();
        const disclosure = document.createElement("details");
        disclosure.className = "ts4nfdi-annotation-widget-disclosure";
        const disclosureLabel = document.createElement("summary");
        disclosureLabel.textContent = gettext("Additional interactive terminology view");
        disclosure.appendChild(disclosureLabel);
        const container = document.createElement("div");
        container.className = "ts4nfdi-annotation-widget-root";
        disclosure.appendChild(container);
        widgetHost.appendChild(disclosure);

        let mounted = false;
        disclosure.addEventListener("toggle", async function () {
            if (!disclosure.open || mounted) {
                return;
            }
            mounted = true;
            container.classList.add("ts4nfdi-annotation-loading");
            container.textContent = gettext("Loading interactive terminology view …");
            try {
                await loadTssAssets();
                const factories = {
                    metadata: "createMetadata",
                    entity_info: "createEntityInfo",
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
                container.className = "ts4nfdi-annotation-widget-root";
                container.replaceChildren();
                factory(props, container);
            } catch (error) {
                container.className = "ts4nfdi-annotation-notice";
                container.textContent = gettext("The interactive terminology widget could not be loaded.");
                console.warn("Could not mount TS4NFDI widget.", error);
            }
        });
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
