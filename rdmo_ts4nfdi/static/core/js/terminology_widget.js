(function () {
    console.log("[ts4nfdi-ts] terminology_widget.js loaded");

    const HOOK_SELECTOR = ".ts4nfdi-terminology-widget";
    const DEFAULT_API = "https://api.terminology.tib.eu/api/";
    const DEFAULT_OUTPUT_FORMAT = "label";
    const DEFAULT_DELIMITER = "; ";
    const QUESTION_MATCHERS = [];
    const BREADCRUMB_MATCHERS = [
        {
            questionUri: "https://rdmo.fairagro.net/terms/questions/dmp4nfdi/v1-0-0/DMP/Dataset/Distribution/rdadmp_format",
            attributeUri: "https://rdmorganiser.github.io/terms/domain/project/dataset/format",
            optionsetUri: "https://rdmo.fairagro.net/terms/options/file_format_ts4nfdi",
            api: DEFAULT_API,
            ontologyId: "edam",
            entityType: "class",
            parameter: "ontology=edam&fieldList=description,label,iri,ontology_name,type,short_form&childrenOf=http://edamontology.org/format_1915",
            useLegacy: true,
            className: "ts4nfdi-breadcrumb-style"
        }
    ];

    function parseBoolean(value, fallback) {
        if (value == null || value === "") {
            return fallback;
        }

        return value === "true";
    }

    function parsePreselectedValue(rawValue, outputFormat, delimiter) {
        if (!rawValue) {
            return [];
        }

        if (outputFormat === "json") {
            try {
                const parsed = JSON.parse(rawValue);
                return Array.isArray(parsed) ? parsed : [parsed];
            } catch (error) {
                console.warn("Could not parse JSON widget value:", error);
                return [];
            }
        }

        return rawValue
            .split(delimiter)
            .map((item) => item.trim())
            .filter(Boolean)
            .map((item) => {
                if (outputFormat === "iri" || item.startsWith("http://") || item.startsWith("https://")) {
                    return { iri: item };
                }

                return { label: item };
            });
    }

    function serializeSelection(selection, outputFormat, delimiter) {
        if (!Array.isArray(selection) || selection.length === 0) {
            return "";
        }

        if (outputFormat === "json") {
            return JSON.stringify(selection);
        }

        const mapped = selection
            .map((item) => {
                if (outputFormat === "iri") {
                    return item.iri || item.label || "";
                }

                if (outputFormat === "label_iri") {
                    if (item.label && item.iri) {
                        return item.label + " | " + item.iri;
                    }

                    return item.label || item.iri || "";
                }

                return item.label || item.iri || "";
            })
            .filter(Boolean);

        return mapped.join(delimiter);
    }

    function updateRdmoInput(input, value) {
        const prototype = Object.getPrototypeOf(input);
        const descriptor = Object.getOwnPropertyDescriptor(prototype, "value");

        if (descriptor && typeof descriptor.set === "function") {
            descriptor.set.call(input, value);
        } else {
            input.value = value;
        }

        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
    }

    function buildWidgetConfig(hook, input) {
        const outputFormat = hook.dataset.outputFormat || DEFAULT_OUTPUT_FORMAT;
        const delimiter = hook.dataset.delimiter || DEFAULT_DELIMITER;
        const singleSelection = parseBoolean(hook.dataset.singleSelection, true);

        return {
            api: hook.dataset.api || DEFAULT_API,
            parameter: hook.dataset.parameter || "",
            placeholder: hook.dataset.placeholder || "Type to search...",
            allowCustomTerms: parseBoolean(hook.dataset.allowCustomTerms, true),
            singleSelection: singleSelection,
            ts4nfdiGateway: parseBoolean(hook.dataset.ts4nfdiGateway, false),
            showApiSource: parseBoolean(hook.dataset.showApiSource, true),
            singleSuggestionRow: parseBoolean(hook.dataset.singleSuggestionRow, false),
            hasShortSelectedLabel: parseBoolean(hook.dataset.hasShortSelectedLabel, true),
            useLegacy: parseBoolean(hook.dataset.useLegacy, true),
            initialSearchQuery: hook.dataset.initialSearchQuery || "",
            preselected: parsePreselectedValue(input.value, outputFormat, delimiter),
            selectionChangedEvent: function (selection) {
                const serialized = serializeSelection(selection, outputFormat, delimiter);
                updateRdmoInput(input, serialized);
            }
        };
    }

    function hasExplicitConfiguration(hook) {
        return Object.keys(hook.dataset).some(function (key) {
            return key !== "widgetInitialized";
        });
    }

    function getProjectId() {
        const meta = document.querySelector('meta[name="project"]');
        return meta ? meta.content : null;
    }

    function getPageId() {
        const match = window.location.pathname.match(/\/interview\/(?<pageId>\d+|done)\/?$/);
        return match && match.groups ? match.groups.pageId : null;
    }

    function flattenQuestions(elements, questions) {
        elements.forEach(function (element) {
            if (element.model === "questions.question") {
                questions.push(element);
            } else if (element.model === "questions.questionset" && Array.isArray(element.elements)) {
                flattenQuestions(element.elements, questions);
            }
        });

        return questions;
    }

    function questionMatchesConfig(question, matcher) {
        return question &&
            question.uri === matcher.questionUri &&
            question.attribute_uri === matcher.attributeUri &&
            Array.isArray(question.optionsets) &&
            question.optionsets.some(function (optionset) {
                return optionset.uri === matcher.optionsetUri;
            });
    }

    function applyMatcherConfig(hook, question) {
        const matcher = QUESTION_MATCHERS.find(function (candidate) {
            return questionMatchesConfig(question, candidate);
        });

        if (!matcher) {
            return;
        }

        Object.entries(matcher).forEach(function (entry) {
            const key = entry[0];
            const value = entry[1];

            if (key.endsWith("Uri")) {
                return;
            }

            hook.dataset[key] = value;
        });
    }

    function getBreadcrumbMatcher(question) {
        return BREADCRUMB_MATCHERS.find(function (candidate) {
            return questionMatchesConfig(question, candidate);
        });
    }

    function initializeWidget(hook, question) {
        if (hook.dataset.widgetInitialized === "true") {
            return;
        }

        if (!window.ts4nfdiWidgets || typeof window.ts4nfdiWidgets.createAutocomplete !== "function") {
            return;
        }

        const questionElement = hook.closest(".interview-question");
        const input = questionElement && questionElement.querySelector(".interview-widget .text-input input, .interview-widget .textarea-input textarea");

        applyMatcherConfig(hook, question);

        if (!hasExplicitConfiguration(hook)) {
            return;
        }

        if (!questionElement) {
            return;
        }

        if (!input) {
            if (question && question.widget_type === "select") {
                console.warn(
                    "TS4NFDI terminology widget target is configured on a select question. " +
                    "The current integration supports text/textarea widgets only.",
                    question.uri
                );
            }
            return;
        }

        const widgetContainer = document.createElement("div");
        widgetContainer.className = "ts4nfdi-terminology-widget-container";

        hook.appendChild(widgetContainer);
        questionElement.classList.add("ts4nfdi-terminology-enabled");
        input.classList.add("ts4nfdi-terminology-source-input");

        window.ts4nfdiWidgets.createAutocomplete(buildWidgetConfig(hook, input), widgetContainer);
        hook.dataset.widgetInitialized = "true";
    }

    function loadPageQuestions() {
        const projectId = getProjectId();
        const pageId = getPageId();

        if (!projectId || !pageId || pageId === "done") {
            return Promise.resolve([]);
        }

        return window.fetch("/api/v1/projects/projects/" + projectId + "/pages/" + pageId + "/", {
            credentials: "same-origin"
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("Could not load interview page metadata.");
            }

            return response.json();
        }).then(function (page) {
            return flattenQuestions(page.elements || [], []);
        }).catch(function (error) {
            console.warn("TS4NFDI terminology widget metadata lookup failed:", error);
            return [];
        });
    }

    function fetchQuestionValues(attributeId) {
        const projectId = getProjectId();

        if (!projectId || !attributeId) {
            return Promise.resolve([]);
        }

        const params = new URLSearchParams();
        params.append("attribute", String(attributeId));

        return window.fetch("/api/v1/projects/projects/" + projectId + "/values/?" + params.toString(), {
            credentials: "same-origin"
        }).then(function (response) {
            if (!response.ok) {
                throw new Error("Could not load project values.");
            }

            return response.json();
        }).then(function (payload) {
            if (Array.isArray(payload)) {
                return payload;
            }

            if (payload && Array.isArray(payload.results)) {
                return payload.results;
            }

            return [];
        }).catch(function (error) {
            console.warn("TS4NFDI breadcrumb value lookup failed:", error);
            return [];
        });
    }

    function clearLegacyBreadcrumbs(root) {
        root.querySelectorAll(".ts4nfdi-breadcrumbs").forEach(function (element) {
            element.remove();
        });
    }

    function clearActiveBreadcrumb(root) {
        root.querySelectorAll(".ts4nfdi-active-breadcrumb").forEach(function (element) {
            element.remove();
        });
    }

    function getQuestionContext(root, questions, widget) {
        const questionElement = widget && widget.closest(".interview-question");
        if (!questionElement) {
            return null;
        }

        const questionElements = Array.from(root.querySelectorAll(".interview-question"));
        const questionIndex = questionElements.indexOf(questionElement);
        const question = questionIndex >= 0 ? questions[questionIndex] : null;
        const matcher = getBreadcrumbMatcher(question);

        if (!question || !matcher) {
            return null;
        }

        const widgets = Array.from(questionElement.querySelectorAll(".interview-widget"));
        const widgetIndex = widgets.indexOf(widget);

        if (widgetIndex < 0) {
            return null;
        }

        return {
            question: question,
            matcher: matcher,
            questionElement: questionElement,
            widget: widget,
            widgetIndex: widgetIndex
        };
    }

    function getDisplayedWidgetText(widget) {
        const valueElement = widget.querySelector(".react-select__single-value");
        return valueElement ? valueElement.textContent.trim() : "";
    }

    function resolveWidgetValue(widget, scopedValues, widgetIndex) {
        const indexedValue = scopedValues[widgetIndex];
        if (indexedValue) {
            return indexedValue;
        }

        const widgetText = getDisplayedWidgetText(widget).toLowerCase();
        if (!widgetText) {
            return null;
        }

        return scopedValues.find(function (value) {
            return value.text && value.text.toLowerCase() === widgetText;
        }) || null;
    }

    function renderActiveBreadcrumb(root, context, value) {
        clearActiveBreadcrumb(root);

        if (!value || !value.external_id || !/^https?:\/\//.test(value.external_id)) {
            console.log("[ts4nfdi-ts] skipping active breadcrumb", {
                widgetIndex: context.widgetIndex,
                value: value
            });
            return;
        }

        const container = document.createElement("div");
        container.className = "ts4nfdi-active-breadcrumb";

        const widget = document.createElement("div");
        widget.className = "ts4nfdi-breadcrumb-widget";
        container.appendChild(widget);

        context.widget.insertAdjacentElement("afterend", container);

        console.log("[ts4nfdi-ts] mounting active breadcrumb", {
            widgetIndex: context.widgetIndex,
            iri: value.external_id,
            text: value.text
        });

        window.ts4nfdiWidgets.createBreadcrumb(
            {
                api: context.matcher.api,
                iri: value.external_id,
                ontologyId: context.matcher.ontologyId,
                entityType: context.matcher.entityType,
                parameter: context.matcher.parameter,
                useLegacy: context.matcher.useLegacy,
                className: context.matcher.className
            },
            widget
        );
    }

    function updateActiveBreadcrumb(root, questions, activeState) {
        if (!window.ts4nfdiWidgets || typeof window.ts4nfdiWidgets.createBreadcrumb !== "function") {
            console.log("[ts4nfdi-ts] breadcrumb widget API not available");
            return;
        }

        clearLegacyBreadcrumbs(root);

        if (!activeState) {
            clearActiveBreadcrumb(root);
            return;
        }

        const widget = root.querySelector(
            '.interview-question[data-question-uri="' + activeState.questionUri + '"] .interview-widget[data-widget-index="' + activeState.widgetIndex + '"]'
        );

        if (!widget) {
            clearActiveBreadcrumb(root);
            return;
        }

        const context = getQuestionContext(root, questions, widget);

        console.log("[ts4nfdi-ts] active breadcrumb candidate", {
            questionUri: context && context.question && context.question.uri,
            widgetIndex: context && context.widgetIndex,
            matched: Boolean(context)
        });

        if (!context) {
            clearActiveBreadcrumb(root);
            return;
        }

        fetchQuestionValues(context.question.attribute).then(function (values) {
            console.log("[ts4nfdi-ts] fetched values", {
                attribute: context.question.attribute,
                questionUri: context.question.uri,
                values: values
            });

            const scopedValues = values
                .filter(function (value) {
                    return value.attribute === context.question.attribute && value.set_prefix === "" && value.set_index === 0;
                })
                .sort(function (left, right) {
                    return left.collection_index - right.collection_index;
                });

            console.log("[ts4nfdi-ts] scoped active breadcrumb values", {
                questionUri: context.question.uri,
                scopedValues: scopedValues,
                widgetIndex: context.widgetIndex
            });

            renderActiveBreadcrumb(root, context, resolveWidgetValue(widget, scopedValues, context.widgetIndex));
        });
    }

    function markQuestionWidgets(root, questions) {
        const questionElements = Array.from(root.querySelectorAll(".interview-question"));

        questionElements.forEach(function (questionElement, questionIndex) {
            const question = questions[questionIndex];
            if (question) {
                questionElement.dataset.questionUri = question.uri;
            }

            Array.from(questionElement.querySelectorAll(".interview-widget")).forEach(function (widget, widgetIndex) {
                widget.dataset.widgetIndex = String(widgetIndex);
            });
        });
    }

    function scan(root, activeState) {
        const hooks = Array.from(root.querySelectorAll(HOOK_SELECTOR));

        loadPageQuestions().then(function (questions) {
            markQuestionWidgets(root, questions);

            if (hooks.length > 0) {
                hooks.forEach(function (hook, index) {
                    initializeWidget(hook, questions[index]);
                });
            }

            updateActiveBreadcrumb(root, questions, activeState);
        });
    }

    function boot() {
        console.log("[ts4nfdi-ts] boot");
        const main = document.getElementById("main");
        if (!main) {
            console.log("[ts4nfdi-ts] no #main found");
            return;
        }

        let rescanTimer = null;
        const pending = document.getElementById("pending");

        if (!pending) {
            console.log("[ts4nfdi-ts] no #pending found");
            return;
        }

        let activeState = null;
        let seenBusyState = pending.childElementCount > 0;

        const canScan = function () {
            const interviewPage = main.querySelector(".interview-page");
            const activeElement = document.activeElement;
            const editingSelect = activeElement && activeElement.closest(".react-select__control");

            return Boolean(interviewPage) && pending.childElementCount === 0 && !editingSelect;
        };

        const scheduleScan = function () {
            window.clearTimeout(rescanTimer);
            rescanTimer = window.setTimeout(function () {
                if (canScan()) {
                    console.log("[ts4nfdi-ts] pending clear -> scan");
                    scan(main, activeState);
                }
            }, 250);
        };

        window.setTimeout(function () {
            console.log("[ts4nfdi-ts] initial idle scan");
            scheduleScan();
        }, 600);

        main.addEventListener("focusin", function (event) {
            const widget = event.target.closest(".interview-widget");
            const selectInput = widget && widget.querySelector(".interview-input.select-input");

            if (!widget || !selectInput) {
                return;
            }

            loadPageQuestions().then(function (questions) {
                markQuestionWidgets(main, questions);

                const context = getQuestionContext(main, questions, widget);
                if (!context) {
                    activeState = null;
                    clearActiveBreadcrumb(main);
                    return;
                }

                activeState = {
                    questionUri: context.question.uri,
                    widgetIndex: context.widgetIndex
                };

                updateActiveBreadcrumb(main, questions, activeState);
            });
        });

        document.addEventListener("click", function (event) {
            if (!main.contains(event.target)) {
                activeState = null;
                clearActiveBreadcrumb(main);
            }
        });

        const pendingObserver = new MutationObserver(function () {
            const isBusy = pending.childElementCount > 0;

            if (isBusy) {
                seenBusyState = true;
                return;
            }

            if (seenBusyState) {
                seenBusyState = false;
                scheduleScan();
            }
        });

        pendingObserver.observe(pending, {
            childList: true,
            subtree: true
        });
    }

    document.addEventListener("DOMContentLoaded", boot);
})();
