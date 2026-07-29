const HOOK_SELECTOR = '[data-ts4nfdi-slot="question-annotations"]';

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

        const usedKeys = new Set();
        return Array.from(
            document.querySelectorAll(`#main .interview-question ${HOOK_SELECTOR}`)
        ).map((element) => {
            const questionElement = element.closest(".interview-question");
            const questionId = this.discoverQuestionId(questionElement);
            const candidates = occurrencesByQuestion.get(questionId) || [];
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

    chooseOccurrence(questionElement, candidates, usedKeys) {
        const unused = candidates.filter((candidate) => !usedKeys.has(candidate.key));
        if (!unused.length) {
            return null;
        }

        const displayedValues = Array.from(
            questionElement.querySelectorAll(
                ".react-select__single-value, .text-input input, .textarea-input textarea"
            )
        ).map((element) => (
            String("value" in element ? element.value : element.textContent).trim()
        )).filter(Boolean);
        return unused.find((candidate) => (
            candidate.annotations.some((annotation) => displayedValues.includes(annotation.label))
        )) || unused[0];
    }
}
