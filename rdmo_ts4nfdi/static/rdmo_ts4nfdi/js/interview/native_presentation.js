import {HTTP_IRI, normalizeResource, translate} from "./core.js";

export function hasAnnotationIdentifier(annotation) {
    return Boolean(String(annotation?.iri || "").trim());
}

function createBadge(text, modifier, title) {
    if (!text) {
        return null;
    }
    const badge = document.createElement("span");
    badge.className = `ts4nfdi-annotation-badge ts4nfdi-annotation-badge--${modifier}`;
    badge.textContent = text;
    if (title) {
        badge.title = title;
    }
    return badge;
}

function appendBreadcrumb(parent, segments) {
    const available = segments.filter((segment) => Boolean(segment.text));
    if (!available.length) {
        return;
    }

    const breadcrumb = document.createElement("span");
    breadcrumb.className = "ts4nfdi-annotation-breadcrumb";
    available.forEach((segment, index) => {
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

function annotationFingerprint(annotations) {
    return annotations.map((annotation) => [
        annotation.value_id,
        annotation.target_id,
        annotation.kind,
        annotation.label,
        annotation.iri,
        annotation.badge_label,
        annotation.source?.id,
        annotation.terminology?.id
    ].join(":")).join("|");
}

export function hasSemanticConceptMetadata(detail) {
    return Boolean(
        detail?.description
        || detail?.definitions?.some(Boolean)
        || detail?.synonyms?.some(Boolean)
    );
}

export function missingSemanticMetadataMessage(detail) {
    if (detail?.kind === "ontology") {
        return translate(
            "The TS4NFDI Gateway did not return a description for this terminology."
        );
    }
    if (detail?.kind === "collection") {
        return translate(
            "The TS4NFDI Gateway did not return a description for this collection."
        );
    }
    return translate(
        "The TS4NFDI Gateway did not return a definition or synonyms for this concept."
    );
}

export class NativeInlineAnnotationRenderer {
    render(slot, occurrence, onOpen) {
        const annotations = occurrence?.annotations || [];
        const fingerprint = annotationFingerprint(annotations);
        if (slot.dataset.annotationFingerprint === fingerprint) {
            return;
        }

        slot.replaceChildren();
        slot.dataset.annotationFingerprint = fingerprint;
        slot.setAttribute("aria-hidden", annotations.length ? "false" : "true");

        annotations.forEach((annotation) => {
            if (!hasAnnotationIdentifier(annotation)) {
                return;
            }
            const row = document.createElement("button");
            row.type = "button";
            row.className = "ts4nfdi-annotation-row";
            row.setAttribute(
                "aria-label",
                `${translate("Terminology details")}: ${annotation.label || annotation.iri}`
            );

            const label = document.createElement("span");
            label.className = "ts4nfdi-annotation-label";
            label.textContent = annotation.label || annotation.iri;
            row.appendChild(label);

            const source = normalizeResource(annotation.source);
            const terminology = normalizeResource(annotation.terminology);
            appendBreadcrumb(row, [
                {text: source.label, modifier: "source", title: source.url},
                {
                    text: terminology.label || annotation.badge_label,
                    modifier: "ontology",
                    title: terminology.iri
                },
                {
                    text: annotation.target_label || annotation.label || annotation.kind,
                    modifier: "term",
                    title: annotation.iri
                }
            ]);

            const chevron = document.createElement("span");
            chevron.className = "ts4nfdi-annotation-chevron";
            chevron.textContent = "›";
            chevron.setAttribute("aria-hidden", "true");
            row.appendChild(chevron);
            row.addEventListener("click", () => onOpen(annotation, row));
            slot.appendChild(row);
        });
    }
}

export class NativeAnnotationDrawer {
    constructor(root, presentations) {
        this.root = root;
        this.presentations = presentations;
        this.activeTrigger = null;
        this.onClose = null;
        this.keydown = (event) => this.onKeydown(event);
        this.closeClick = () => this.close();
    }

    start(onClose) {
        if (!this.root) {
            return () => {};
        }
        this.onClose = onClose;
        this.root.querySelectorAll("[data-ts4nfdi-close]").forEach((button) => {
            button.addEventListener("click", this.closeClick);
        });
        document.addEventListener("keydown", this.keydown);
        return () => {
            this.root.querySelectorAll("[data-ts4nfdi-close]").forEach((button) => {
                button.removeEventListener("click", this.closeClick);
            });
            document.removeEventListener("keydown", this.keydown);
            this.presentations.clear(this.widget());
            this.onClose = null;
        };
    }

    loading(annotation, trigger) {
        if (!this.root) {
            return;
        }
        this.activeTrigger = trigger;
        this.root.hidden = false;
        this.root.setAttribute("aria-hidden", "false");
        document.body.classList.add("ts4nfdi-annotation-drawer-open");
        this.title().textContent = annotation.label || translate("Terminology details");
        this.summary().replaceChildren();
        this.presentations.clear(this.widget());

        const loading = document.createElement("div");
        loading.className = "ts4nfdi-annotation-loading";
        loading.setAttribute("role", "status");
        loading.textContent = translate("Loading terminology details …");
        this.summary().appendChild(loading);
        this.root.querySelector(".ts4nfdi-annotation-panel").focus();
    }

    detail(detail) {
        if (!this.root) {
            return;
        }
        this.title().textContent = detail.label || translate("Terminology details");
        this.summary().replaceChildren();
        this.presentations.clear(this.widget());

        const source = normalizeResource(detail.source);
        const terminology = normalizeResource(detail.terminology);
        const breadcrumb = document.createElement("div");
        breadcrumb.className = "ts4nfdi-annotation-summary-breadcrumb";
        appendBreadcrumb(breadcrumb, [
            {text: source.label, modifier: "source", title: source.url},
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
        this.summary().appendChild(breadcrumb);

        this.renderDefinitions(
            detail.definitions?.length
                ? detail.definitions
                : (detail.description ? [detail.description] : [])
        );
        this.renderSynonyms(detail.synonyms || []);
        if (
            detail.metadata_status === "available"
            && !hasSemanticConceptMetadata(detail)
        ) {
            this.renderNotice(missingSemanticMetadataMessage(detail));
        }
        this.renderProperties([
            [translate("Source"), source.label],
            [translate("Database"), source.database || source.id],
            [translate("Backend"), source.backend_type],
            [translate("Terminology"), terminology.label || detail.ontology_id],
            [translate("Short form"), detail.short_form],
            [translate("Type"), (detail.entity_types || []).join(", ")],
            [
                translate("Status"),
                detail.obsolete === true
                    ? translate("Obsolete")
                    : detail.obsolete === false
                        ? translate("Current")
                        : null
            ],
            [translate("Version"), detail.version]
        ]);
        this.renderActions(detail, source);

        if (detail.metadata_status !== "available") {
            this.renderNotice(
                translate("Additional terminology metadata is currently unavailable.")
            );
        } else {
            this.presentations.render(
                this.widget(),
                detail.presentation,
                {detail}
            );
        }
    }

    error(error, retry) {
        if (!this.root) {
            return;
        }
        this.presentations.clear(this.widget());
        this.summary().replaceChildren();
        const message = document.createElement("p");
        message.className = "ts4nfdi-annotation-notice";
        message.textContent = translate("Terminology details could not be loaded.");
        this.summary().appendChild(message);

        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn btn-default btn-sm";
        button.textContent = translate("Retry");
        button.addEventListener("click", retry, {once: true});
        this.summary().appendChild(button);
        console.warn("Could not load TS4NFDI annotation detail.", error);
    }

    close() {
        if (!this.root || this.root.hidden) {
            return;
        }
        this.root.hidden = true;
        this.root.setAttribute("aria-hidden", "true");
        document.body.classList.remove("ts4nfdi-annotation-drawer-open");
        this.presentations.clear(this.widget());
        this.onClose?.();
        if (this.activeTrigger && document.contains(this.activeTrigger)) {
            this.activeTrigger.focus();
        }
        this.activeTrigger = null;
    }

    onKeydown(event) {
        if (event.key === "Escape") {
            this.close();
            return;
        }
        if (!this.root || this.root.hidden || event.key !== "Tab") {
            return;
        }

        const focusable = Array.from(
            this.root.querySelectorAll(
                'a[href], button:not([disabled]), input:not([disabled]), ' +
                '[tabindex]:not([tabindex="-1"])'
            )
        ).filter((element) => element.offsetParent !== null);
        if (!focusable.length) {
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

    renderDefinitions(definitions) {
        const values = definitions.filter(Boolean);
        if (!values.length) {
            return;
        }
        const section = this.createSection(translate("Definition"));
        values.forEach((definition) => {
            const paragraph = document.createElement("p");
            paragraph.className = "ts4nfdi-annotation-description";
            paragraph.textContent = definition;
            section.appendChild(paragraph);
        });
        this.summary().appendChild(section);
    }

    renderSynonyms(synonyms) {
        const values = synonyms.filter(Boolean);
        if (!values.length) {
            return;
        }
        const section = this.createSection(translate("Synonyms"));
        const list = document.createElement("div");
        list.className = "ts4nfdi-annotation-synonyms";
        values.forEach((synonym) => list.appendChild(createBadge(synonym, "synonym")));
        section.appendChild(list);
        this.summary().appendChild(section);
    }

    renderProperties(properties) {
        const available = properties.filter((property) => (
            property[1] != null && property[1] !== ""
        ));
        if (!available.length) {
            return;
        }
        const section = this.createSection(translate("Technical metadata"));
        const list = document.createElement("dl");
        list.className = "ts4nfdi-annotation-properties";
        available.forEach(([name, value]) => {
            const term = document.createElement("dt");
            term.textContent = name;
            const description = document.createElement("dd");
            description.textContent = value;
            list.appendChild(term);
            list.appendChild(description);
        });
        section.appendChild(list);
        this.summary().appendChild(section);
    }

    renderNotice(message) {
        const notice = document.createElement("p");
        notice.className = "ts4nfdi-annotation-notice";
        notice.textContent = message;
        this.summary().appendChild(notice);
    }

    renderActions(detail, source) {
        const actions = document.createElement("div");
        actions.className = "ts4nfdi-annotation-actions";
        if (detail.iri && HTTP_IRI.test(detail.iri)) {
            actions.appendChild(this.externalLink(detail.iri, translate("Open concept IRI")));
            const copy = document.createElement("button");
            copy.type = "button";
            copy.className = "ts4nfdi-annotation-action";
            copy.textContent = translate("Copy IRI");
            copy.addEventListener("click", async () => {
                try {
                    await navigator.clipboard.writeText(detail.iri);
                    copy.textContent = translate("Copied");
                } catch (error) {
                    console.warn("Could not copy terminology IRI.", error);
                }
            });
            actions.appendChild(copy);
        }
        if (source.url && HTTP_IRI.test(source.url)) {
            actions.appendChild(this.externalLink(source.url, translate("Open source")));
        }
        if (!actions.childElementCount) {
            return;
        }
        const section = this.createSection(translate("Links"));
        section.appendChild(actions);
        this.summary().appendChild(section);
    }

    createSection(headingText) {
        const section = document.createElement("section");
        section.className = "ts4nfdi-annotation-section";
        const heading = document.createElement("h3");
        heading.textContent = headingText;
        section.appendChild(heading);
        return section;
    }

    externalLink(url, label) {
        const link = document.createElement("a");
        link.className = "ts4nfdi-annotation-action";
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        return link;
    }

    title() {
        return this.root.querySelector("#ts4nfdi-annotation-drawer-title");
    }

    summary() {
        return this.root.querySelector("#ts4nfdi-annotation-summary");
    }

    widget() {
        return this.root.querySelector("#ts4nfdi-annotation-widget");
    }
}
