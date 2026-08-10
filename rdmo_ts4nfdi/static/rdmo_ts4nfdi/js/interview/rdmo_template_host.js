const HOOK_SELECTOR = '[data-ts4nfdi-slot="question-annotations"]';

function normalizeDisplayedValue(value) {
    return String(value || "")
        .replace(/\s+/g, " ")
        .trim()
        .toLocaleLowerCase();
}

function selectedValueText(element) {
    if ("value" in element) {
        return element.value;
    }

    // Provider option markup can add breadcrumbs and descriptions beside the
    // actual label. RDMO places all of it inside the selected-value container,
    // so using its complete textContent would no longer equal Value.text.
    const primaryLabel = element.querySelector?.(
        ".interview-select-option > span:first-child"
    );
    return primaryLabel ? primaryLabel.textContent : element.textContent;
}

function annotationFingerprint(occurrence) {
    return (occurrence.annotations || []).map((annotation) => [
        annotation.label,
        annotation.iri,
        annotation.matcher_id
    ].map(normalizeDisplayedValue).join(":"))
        .sort()
        .join("|");
}

export class RDMOTemplateInterviewHost {
    /**
     * Adapter for the current RDMO template and React-generated DOM.
     *
     * No other frontend module may depend on RDMO selectors, URL shapes, or
     * loading indicators. A future official RDMO extension API replaces only
     * this class.
     */
    constructor() {
        this.timer = null;
        this.observers = [];
    }

    baseUrl() {
        const meta = document.querySelector('meta[name="baseurl"]');
        return meta ? meta.content.replace(/\/+$/, "") : "";
    }

    context() {
        const projectMeta = document.querySelector('meta[name="project"]');
        const pageMatch = window.location.pathname.match(/\/interview\/(\d+|done)\/?$/);
        return {
            projectId: projectMeta ? projectMeta.content : null,
            pageId: pageMatch ? pageMatch[1] : null,
            available: Boolean(document.getElementById("main"))
        };
    }

    slots(payload) {
        const occurrencesByQuestion = new Map();
        (payload.occurrences || []).forEach((occurrence) => {
            const current = occurrencesByQuestion.get(occurrence.question_id) || [];
            current.push(occurrence);
            occurrencesByQuestion.set(occurrence.question_id, current);
        });

        const activePageSetIndex = this.activePageSetIndex();
        const usedKeys = new Set();
        return Array.from(
            document.querySelectorAll(`#main .interview-question ${HOOK_SELECTOR}`)
        ).map((element) => {
            const questionElement = element.closest(".interview-question");
            const questionId = this.discoverQuestionId(questionElement);
            const candidates = this.scopeCandidatesToActivePageSet(
                occurrencesByQuestion.get(questionId) || [],
                activePageSetIndex
            );
            const occurrence = this.chooseOccurrence(questionElement, candidates, usedKeys);
            if (occurrence) {
                usedKeys.add(occurrence.key);
            }
            return {element, occurrence};
        });
    }

    clearSlots() {
        document.querySelectorAll(`#main ${HOOK_SELECTOR}`).forEach((element) => {
            element.replaceChildren();
            delete element.dataset.annotationFingerprint;
            element.setAttribute("aria-hidden", "true");
        });
    }

    observe(onChange) {
        const main = document.getElementById("main");
        if (!main) {
            return () => {};
        }

        const schedule = (delay = 150) => {
            window.clearTimeout(this.timer);
            this.timer = window.setTimeout(() => {
                const pending = document.getElementById("pending");
                if (!pending || pending.childElementCount === 0) {
                    onChange(this.context());
                }
            }, delay);
        };

        const pending = document.getElementById("pending");
        if (pending) {
            const pendingObserver = new MutationObserver(() => {
                if (pending.childElementCount === 0) {
                    schedule(100);
                }
            });
            pendingObserver.observe(pending, {childList: true, subtree: true});
            this.observers.push(pendingObserver);
        }

        const mainObserver = new MutationObserver((mutations) => {
            const externalMutation = mutations.some((mutation) => !(
                mutation.target instanceof Element &&
                mutation.target.closest(HOOK_SELECTOR)
            ));
            if (externalMutation) {
                schedule(200);
            }
        });
        mainObserver.observe(main, {childList: true, subtree: true});
        this.observers.push(mainObserver);
        schedule(300);

        return () => {
            window.clearTimeout(this.timer);
            this.observers.forEach((observer) => observer.disconnect());
            this.observers = [];
        };
    }

    discoverQuestionId(questionElement) {
        if (!questionElement) {
            return null;
        }
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

    activePageSetIndex() {
        const tabs = Array.from(document.querySelectorAll(
            "#main .interview-page-tabs .nav-tabs > li"
        ));
        const activeIndex = tabs.findIndex((tab) => tab.classList.contains("active"));

        // RDMO's collection-page tabs are emitted in set-index order. The
        // React DOM does not expose the actual set_index, but the active tab's
        // position is sufficient for the normal, contiguous collection sets
        // RDMO creates. If it cannot be determined, retain the existing
        // label-based matching behaviour below.
        return activeIndex === -1 ? null : activeIndex;
    }

    scopeCandidatesToActivePageSet(candidates, activePageSetIndex) {
        if (activePageSetIndex === null) {
            return candidates;
        }

        const topLevelCandidates = candidates.filter(
            (candidate) => !candidate.set_prefix
        );
        if (!topLevelCandidates.length) {
            return candidates;
        }

        // A collection page renders only the active top-level set. Do not
        // fall back to another set when this one has no semantic annotations:
        // showing no row is safer than attaching another dataset's details.
        return topLevelCandidates.filter(
            (candidate) => Number(candidate.set_index) === activePageSetIndex
        );
    }

    chooseOccurrence(questionElement, candidates, usedKeys) {
        const unused = candidates.filter((candidate) => !usedKeys.has(candidate.key));
        if (!unused.length) {
            return null;
        }

        const displayedValues = new Set(Array.from(
            questionElement.querySelectorAll(
                ".react-select__single-value, .react-select__multi-value__label, " +
                ".text-input input, .textarea-input textarea"
            )
        ).map((element) => normalizeDisplayedValue(
            selectedValueText(element)
        )).filter(Boolean));
        if (!displayedValues.size) {
            return null;
        }

        const matches = unused.map((candidate) => {
            const labels = new Set(
                (candidate.annotations || [])
                    .map((annotation) => normalizeDisplayedValue(annotation.label))
                    .filter(Boolean)
            );
            const matchedLabels = new Set(
                Array.from(labels).filter((label) => displayedValues.has(label))
            );
            return {candidate, matchedLabels};
        }).filter(({matchedLabels}) => (
            matchedLabels.size > 0
        ));
        if (!matches.length) {
            return null;
        }

        // A provider may change the display label independently of an already
        // stored RDMO Value.text (for example ``envo`` becoming
        // ``Environment Ontology``). Use the occurrence with the greatest
        // visible overlap instead of requiring every stored label to match.
        const largestMatch = Math.max(
            ...matches.map(({matchedLabels}) => matchedLabels.size)
        );
        const bestMatches = matches.filter(
            ({matchedLabels}) => matchedLabels.size === largestMatch
        );
        if (bestMatches.length === 1) {
            return bestMatches[0].candidate;
        }

        // The current RDMO DOM does not expose set_prefix/set_index. Multiple
        // matching occurrences are safe only when they would render exactly
        // the same annotations. Otherwise fail closed instead of showing a
        // different dataset's semantic information.
        const fingerprints = new Set(
            bestMatches.map(({candidate}) => annotationFingerprint(candidate))
        );
        return fingerprints.size === 1 ? bestMatches[0].candidate : null;
    }
}
