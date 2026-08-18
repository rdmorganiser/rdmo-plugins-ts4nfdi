# Possible upstream extension points for the RDMO front end

Status: exploratory proposals for discussion with the RDMO developer community.

These proposals are motivated by the `rdmo_ts4nfdi` prototype, but they are
deliberately independent of TS4NFDI. They should be useful to any trusted Django
app that wants to add contextual help, validation results, provenance,
visualisations, or other supplementary UI to RDMO.

The initial use case is read-only enhancement of an interview. Extensions must
not need access to RDMO's private React components, Redux store, or actions.

## Architectural boundary

The four participating domains should remain separate:

| Domain | Owns | Must not need to know |
| --- | --- | --- |
| RDMO | Interview state, permissions, REST resources, React lifecycle, and stable extension contracts | TS4NFDI endpoints, ontology response shapes, or terminology widgets |
| `rdmo_ts4nfdi` | RDMO-to-terminology mapping, matcher configuration, annotation orchestration, and deployment integration | Private RDMO React state or private internals of a TS4NFDI widget |
| TS4NFDI API Gateway | Search and retrieval across terminology sources | RDMO projects, pages, questions, or Django authentication |
| Terminology Service Suite (TSS) | Reusable terminology presentation and interaction components | RDMO's Redux store, catalog model, or plugin endpoints |

The intended dependency direction is:

```text
RDMO public extension contract
              |
              v
       rdmo_ts4nfdi
        /           \
       v             v
Gateway HTTP API   TSS public widget API
```

RDMO should expose only a generic host contract. The plugin adapts that contract
to the TS4NFDI APIs. It must remain possible to replace the plugin's prototype
renderer with a TSS widget, replace one TSS widget with another, or change from
a proxied to a direct Gateway request without changing RDMO.

## Current situation

In the currently inspected RDMO source, `project_interview.html` is already a
thin shell. React creates independent roots in `#main`, `#sidebar`, and
`#pending`, and the interview is populated through REST requests.

There is one useful server-side bridge:

1. RDMO renders configured Django templates through the templates API.
2. `QuestionHelpTemplate` injects
   `projects/project_interview_question_help.html` into every React-rendered
   question.
3. This plugin places a marker in that template and discovers the surrounding
   question with DOM queries and mutation observers.

This lets the prototype remain outside the RDMO React state, but it has several
limitations:

- the template is rendered without the individual question or question-set
  occurrence as Django context;
- question, attribute, `set_prefix`, and `set_index` have to be inferred;
- React navigation and re-rendering have to be detected by observing the DOM;
- several plugins must merge or cooperate through the same template override;
- a future React-only interview can remove the template bridge completely.

The current hook should therefore be treated as a replaceable RDMO host adapter,
not as part of the terminology feature itself.

## Design principles for an upstream contract

An upstream feature should meet the following requirements:

- **Optional and non-breaking:** an RDMO installation with no registered
  extensions behaves exactly as it does now.
- **Deployment-neutral:** the contract is useful to any installed, trusted
  Django app and contains no TS4NFDI-specific concepts.
- **Framework-neutral at the boundary:** an extension can mount plain DOM,
  Web Components, or its own framework bundle. It must not have to link against
  RDMO's React version.
- **Read-only first:** the initial contract exposes context and lifecycle, not
  the Redux store or state-changing callbacks.
- **Versioned and capability-based:** extensions can detect which slots and
  context versions the host supports.
- **Occurrence-aware:** repeated question sets are identified by more than a
  question ID.
- **Failure-isolated:** an unavailable or broken extension cannot prevent the
  interview from loading or saving.
- **Lifecycle-safe:** each mount has a matching update and unmount operation.
- **Accessible:** extensions receive real mount elements in predictable reading
  order, while overlays have an appropriate host location for focus handling.

## Feature request 1: runtime extension discovery for trusted Django apps

Suggested issue title:

> Add a versioned runtime front-end extension manifest for installed Django apps

### Problem

A Django app can currently provide Python code, templates, static assets, and
REST endpoints. A mostly React-based RDMO front end also needs a supported way
to discover and load the app's browser-side entry point without rebuilding the
RDMO JavaScript bundle or replacing a complete RDMO template.

Requiring an extension to be compiled into RDMO would make deployment-specific
apps difficult to use and would tightly couple them to RDMO's JavaScript
dependencies.

### Proposed capability

RDMO could collect front-end extension declarations from a setting, Django app
hook, or registry and expose the resolved declarations in its bootstrap data or
through a small authenticated REST endpoint.

A conceptual manifest entry could contain:

```json
{
  "id": "example.contextual-help",
  "api_version": "1",
  "script": "/static/example/contextual-help.js",
  "stylesheet": "/static/example/contextual-help.css",
  "slots": [
    "projects.interview.overlay",
    "projects.interview.question.after-help"
  ],
  "order": 100
}
```

The exact registration mechanism should follow existing RDMO conventions. The
important parts of the public contract are:

- globally unique extension IDs;
- a declared host API version;
- static asset URLs resolved by RDMO/Django;
- requested slot names;
- deterministic ordering when several extensions use a slot;
- load each asset at most once;
- optional integrity, nonce, or other Content Security Policy metadata;
- a capability response when an extension API version or slot is unavailable.

Installed Python packages and explicitly configured static bundles are already
trusted deployment code. RDMO should nevertheless catch load and registration
errors and continue without the failed extension.

### Compatibility

The manifest is empty by default. No existing template, URL, or interview
behaviour needs to change. The existing templates API can remain available
during and after introduction of this feature.

## Feature request 2: framework-neutral interview extension slots

Suggested issue title:

> Add stable, framework-neutral extension slots to the React interview

### Problem

A plugin currently has to locate internal React-generated elements by CSS class,
insert children into them, and restore those children after re-rendering. CSS
classes and component structure are presentation details rather than a public
API.

Sharing RDMO's React instance with third-party bundles would create a different
form of coupling. It would bind plugins to RDMO's React version, component
tree, build process, and state architecture.

### Proposed capability

RDMO could render small `ExtensionSlot` components at stable semantic locations.
The component would provide an ordinary DOM element and invoke registered,
framework-neutral lifecycle callbacks.

The minimum useful slots for the current class of use cases are:

- `projects.interview.overlay`: once per interview, outside the question flow,
  for a drawer, dialog, or other supplementary surface;
- `projects.interview.question.after-help`: once for each visible question
  occurrence, near explanatory help;
- `projects.interview.question.after-answer`: once for each visible question
  occurrence, after the answer widget.

Possible later slots include page-level, question-set-level, sidebar, and
interview-completion locations. The initial upstream change should stay small
and add further slots only for demonstrated generic use cases.

A conceptual browser-side registration could look like:

```javascript
window.RDMO.extensions.register({
  id: "example.contextual-help",
  apiVersion: "1",
  slots: {
    "projects.interview.overlay": {
      mount(element, context, host) {
        return () => {
          // Remove listeners and dispose mounted UI.
        };
      }
    },
    "projects.interview.question.after-help": {
      mount(element, context, host) {
        return {
          update(nextContext) {},
          unmount() {}
        };
      }
    }
  }
});
```

This is an illustrative shape, not a requirement for the global name or exact
callback syntax. The significant design choices are:

- RDMO owns the slot element and its lifetime;
- the extension owns only the descendants of that element;
- RDMO calls `mount`, `update`, and `unmount` at defined times;
- an extension is not passed React components, hooks, Redux state, or dispatch;
- callbacks are isolated so one extension cannot break other slots;
- RDMO can warn when an extension requests an unknown slot or API version.

### Compatibility

An empty slot should either render no DOM or an inert empty element and must not
change layout. With no registered extensions, the component tree and all
interview actions retain their current behaviour.

## Feature request 3: versioned, read-only interview context

Suggested issue title:

> Publish a versioned read-only context for interview front-end extensions

### Problem

The database ID of the current project can be read from the HTML shell, but a
question extension also needs stable identifiers for the current page,
question, attribute, and repeated occurrence. Recovering these values from
labels, generated input IDs, or visible text is ambiguous.

Giving an extension the complete Redux state would expose private
implementation details and encourage it to bypass RDMO permissions and update
logic.

### Proposed capability

Each extension slot should receive a serialisable, immutable snapshot containing
only stable public context. For example:

```json
{
  "api_version": "1",
  "route": "projects.interview",
  "project": {
    "id": 24
  },
  "page": {
    "id": 341,
    "uri": "https://example.org/terms/questions/page"
  },
  "question": {
    "id": 7153,
    "uri": "https://example.org/terms/questions/format",
    "attribute": {
      "id": 42,
      "uri": "https://example.org/terms/domain/format"
    }
  },
  "occurrence": {
    "set_prefix": "0|3",
    "set_index": 1
  },
  "mode": {
    "disabled": false,
    "editable": true
  }
}
```

The exact fields should be discussed with the RDMO community. The following
semantics are important:

- both database IDs and persistent URIs are useful;
- `set_prefix` and `set_index` identify the visible occurrence;
- the context reflects the permissions and disabled state already computed by
  RDMO;
- values should be omitted initially unless there is a general need to expose a
  minimal value summary;
- extensions fetch additional data from documented RDMO REST APIs or from their
  own namespaced endpoints;
- no mutable Django model, React component, Redux object, or internal action is
  exposed.

The host lifecycle should update or remount a slot when SPA navigation changes
the project, page, question occurrence, or mode. If external value changes need
to be observable later, RDMO could add a narrow versioned subscription such as
`host.subscribe("projects.interview.values.changed", callback)`. A public
subscription is preferable to exposing the store itself.

### Optional host services

A small host object could provide stable infrastructure without exposing state:

- the RDMO base URL and REST API base URL;
- supported API and slot versions;
- a same-origin URL builder;
- a locale or translation capability;
- a request to refresh the extension context.

State-changing functions should not be part of the first version.

## Feature request 4: stable semantic DOM metadata as a transition

Suggested issue title:

> Add stable semantic identifiers to interview question occurrences

### Problem

The full registry and slot API may take time to design. Current deployment
plugins still need a safer way to associate a rendered question with its RDMO
resources without inspecting input names, labels, or private component
structure.

### Proposed capability

As a small, independent change, RDMO could place documented `data-rdmo-*`
attributes on question and question-set occurrence containers. Candidate data
include:

- element type;
- page ID and URI;
- question or question-set ID and URI;
- attribute ID and URI;
- `set_prefix` and `set_index`.

An alternative is to add inert, semantically named slot elements containing
these attributes before the runtime registry exists.

### Limitations

This is a compatibility bridge, not a complete plugin API. React may replace
the DOM node, so a side-loaded extension would still need to observe navigation
or re-rendering. It also does not solve asset discovery, ordering, cleanup, or
error isolation. The documented data attributes should therefore have their own
small version marker and migrate naturally into the later slot context.

## Deferred request: host-mediated state changes

The terminology annotation prototype does not need to mutate RDMO interview
state. It reads the current occurrence and opens supplementary information.

If future extensions need to propose or write answers, that should be a separate
upstream design. A safe mutation API would have to:

- use the same permission, validation, condition, and signal paths as the
  regular RDMO UI;
- expose intent-level operations rather than Redux actions;
- return documented REST representations and validation errors;
- make editability and supported operations explicit in capabilities;
- preserve audit and project snapshot behaviour;
- remain opt-in for extensions.

Until such an API exists, this plugin should not simulate clicks, change React
controlled inputs, dispatch private actions, or write to the Redux store.

## Feature request 5: preserve structured dynamic-option identity metadata

Suggested issue title:

> Let dynamic option providers persist declared provenance metadata with a selected value

### Problem

An RDMO dynamic option provider can return rich search-result objects, but the
current select widget persists only the provider option's `id` as
`Value.external_id` and its `text` as `Value.text`. This is sufficient when an
identifier globally and unambiguously identifies one result. It is insufficient
for federated search, where the same identifier can be returned through several
sources or terminology collections and the selected source is meaningful
provenance.

Re-querying the provider later is only a best-effort reconstruction: external
results may change, the service may be unavailable, and identical identifiers
may have conflicting source contexts. Parsing presentation HTML from an option's
`help` field would couple persistence to markup and should not be required.

This is not terminology-specific. Similar requirements apply to authority
files, repository search, equipment registries, person/institution lookup, and
other federated provider integrations.

### Proposed capability

A provider could declare a small JSON-serialisable metadata object on an option,
and RDMO could persist that object alongside the selected value or in a generic
related value-metadata model. The field must be opt-in, size-limited, and treated
as immutable provider provenance rather than trusted HTML.

For example:

```json
{
  "id": "https://example.org/concept/123",
  "text": "Example concept",
  "metadata": {
    "source": "example-authority",
    "collection": "example-vocabulary",
    "local_id": "123"
  }
}
```

The value REST representation and normal project exports should expose the
stored metadata. Import should preserve it, and snapshot/copy operations should
follow the same semantics as the owning value. RDMO does not need to interpret
the keys; deployments and provider plugins own their schemas.

### Compatibility and safety

Providers that do not return metadata behave exactly as before. RDMO should
accept JSON values only, enforce a conservative size limit, reject executable
or markup semantics, and never render metadata without an explicit consumer.
The selected `external_id` remains the canonical external identifier, so
existing exports and integrations remain compatible.

The current plugin prototype keeps this limitation explicit. Matcher policy
`context_resolution = { adapter = "gateway-search" }` lets the browser
best-effort reconstruct one unambiguous breadcrumb for display, with no RDMO
value mutation. It deliberately falls back to a generic breadcrumb when the
Gateway returns conflicting contexts. This is a transitional display adapter,
not a substitute for persisted selection provenance.

## Feature request 6: expose external identifiers consistently in project exports

Suggested issue title:

> Expose `Value.external_id` consistently in machine-readable and human-readable project exports

### Problem

Dynamic providers already persist the selected external identifier in
`Value.external_id`. RDMO's archival XML can preserve this field, but users do
not consistently see that an answer is a controlled identifier in normal JSON
or rendered/PDF output. A label such as “Milk” is therefore visually
indistinguishable from free text even when it denotes a stable terminology
concept.

This is useful beyond terminology plugins: repository records, ORCID and ROR
identifiers, authority files, instruments, licenses, and other provider-backed
answers have the same requirement.

### Proposed capability

- Include `external_id`, `option_uri`, and the ordinary answer text in a stable
  value representation used by standard machine-readable exports.
- Give rendered export templates a documented value helper or hook which can
  display a controlled-value marker and optional identifier link.
- Keep the current label-only rendering as the default so existing PDF layouts
  do not change unless a deployment or export template opts in.
- Preserve these fields through import, project copy, and snapshots using the
  existing value semantics.

The RDMO core does not need to resolve or validate the external identifier.
Plugins and deployments remain responsible for its meaning. This plugin's
`ts-for-nfdi-json` export can remain a semantic sidecar, but should not have to
define a second full project-export format merely to expose identifiers already
stored by RDMO.

### Compatibility and acceptance

- values without an external identifier export exactly as before;
- controlled and free-text answers remain distinguishable;
- standard JSON exposes the identifier without parsing display text;
- an opt-in PDF/rendered template can show the label and identifier accessibly;
- no provider-specific model or terminology dependency is introduced in RDMO.

## Feature request 7: improve free-text entry in asynchronous creatable selects

Suggested issue title:

> Make free-text entry clear and immediately available in asynchronous creatable selects

### Problem

Some questions use both a searchable option provider and `select_creatable` so
that users can choose a controlled term or enter their own text. When the user
types a term that is not present, the menu shows an empty row. Clicking that
row saves the entered text, but there is no visible explanation of what the row
does.

The current interaction therefore makes the free-text path difficult to
discover:

- the user starts typing while the provider search is still loading;
- the action for keeping the typed text is not available until the search
  finishes;
- the action is rendered as an empty option row, so users have to guess that it
  is clickable.

### Source of the empty row

This was checked against RDMO commit
`9f48c2fc93e021ff8eef3e087c1368235bef2e56`, which uses React Select 5.10.2.
Provider options have RDMO's `{id, text, help}` shape. React Select creates a
new free-text candidate with a different shape:

```javascript
{label: inputValue, value: inputValue, __isNew__: true}
```

RDMO's `getOptionLabel` and custom `OptionText` renderer both read only
`option.text`. The new candidate has no `text`, so its row is empty. The click
still works because `handleChange` recognizes `__isNew__` and stores
`option.value` as ordinary text.

### Desired behavior

- Users can type immediately; they do not have to wait for provider results
  before choosing the free-text path.
- While search is running, show a clear action such as **Use “my text” as free
  text**. React Select provides `allowCreateWhileLoading` for this behavior.
- Render the new candidate from its `label` or `value`, not only from `text`.
- Clearly distinguish a provider result from the free-text action.
- If there are no provider results, optionally show **No matching term found**
  as a separate status message rather than using a blank option.
- Keyboard use is predictable: arrow keys navigate results and Enter chooses
  the currently highlighted provider result or free-text action.
- A provider error does not block users from saving their own text.
- The behavior is accessible and works at narrow screen widths.

### Compatibility and acceptance

- Apply this behavior only to creatable selects; ordinary controlled selects
  must still require an option.
- Keep the current storage semantics: provider results save their
  `external_id`, while created values save ordinary text.
- Existing saved answers continue to load and edit normally.
- Cover loading, no-result, exact-result, error, mouse, and keyboard cases.
- The free-text row has a meaningful accessible name, not only visible text.

This request is independent of the proposed interview extension API. It is a
general usability improvement for any RDMO catalog that combines asynchronous
provider search with optional free-text answers.

## Feature request 8: browse bounded asynchronous provider options before typing

Suggested issue title:

> Let opted-in asynchronous option providers return browse options for an empty search

### Problem

Some dynamic providers have a small, bounded set of controlled values that
users should be able to inspect before they know what to type. For example, the
TS4NFDI RDMO plugin exposes one curated Gateway entity set. It caches the
bounded list and can filter it locally, but its provider is marked as
search-backed so that RDMO uses the asynchronous select widget.

The current interview `SelectInput` does not call the options endpoint when
the input is empty: it immediately calls `callback([])`. Returning the complete
entity set from the provider for an empty `search` value would therefore have
no visible effect. Users must guess a search term before they can discover the
available controlled values.

This is separate from feature request 7. That request makes a newly typed
free-text value clear and usable; this request lets a user browse known
provider values before typing.

### Established component pattern

This is a standard asynchronous-combobox pattern rather than a
terminology-specific behaviour. React Select supports initial asynchronous
options through `defaultOptions`: an option array supplies an initial list, and
`defaultOptions={true}` invokes `loadOptions` for the empty input. Material UI
documents the same two distinct modes: **load on open** for a bounded initial
list and **search as you type** for remote filtering.

RDMO already renders its asynchronous selects with React Select's
`defaultOptions`; the empty-input guard prevents providers from opting into
this supported mode.

- [React Select: Async and `defaultOptions`](https://react-select.com/async)
- [Material UI: asynchronous Autocomplete](https://mui.com/material-ui/react-autocomplete/)

### Proposed capability and implementation outline

- Add `browse_on_empty_search = False` to RDMO's dynamic-provider contract.
  It is meaningful only when `search = True`.
- Expose the equivalent capability on the serialized option set sent to the
  interview front end.
- In `SelectInput.handleLoadOptions()`, retain the current empty-result
  behaviour unless at least one asynchronous option set opts in. For an empty
  input, call `ProjectApi.fetchOptions(projectId, optionset.id, '')` only for
  opted-in option sets.
- For non-empty input, keep the existing behaviour: query every asynchronous
  option set with the typed search value.
- Document that an opted-in provider must return a bounded result set. Large or
  unbounded remote indexes remain search-only and retain the current behaviour.

The existing options endpoint already accepts an empty `search` parameter, and
the normal option response shape and value persistence do not need to change.
Choosing a returned provider value must continue to store its `external_id` and
text exactly as it does today.

### Compatibility and acceptance

- Existing providers receive no empty search request unless they explicitly
  opt in.
- An opted-in provider displays its initial bounded options when the async
  select loads with an empty input.
- A question with several option sets queries only opted-in sets for an empty
  input, while a non-empty input continues to query all search-backed sets.
- Provider errors are contained by the existing error handling and do not
  change answer persistence.
- Controlled selections and free-text answers retain their existing storage,
  editing, and export semantics.
- Cover mouse and keyboard selection, an empty initial list, normal typed
  search, and a provider error in front-end and endpoint tests.

## Suggested upstream sequence

The proposals can be discussed and delivered independently:

1. Add semantic question-occurrence identifiers as a small transitional,
   non-breaking improvement.
2. Agree on a versioned runtime extension manifest for trusted Django apps.
3. Add the interview overlay and question slots with lifecycle cleanup.
4. Add the minimal read-only occurrence context.
5. Add further slots or read-only events only after additional generic use
   cases are demonstrated.
6. Expose stored external identifiers through generic export contracts.
7. Improve the existing asynchronous creatable-select interaction independently.
8. Add opt-in browsing for bounded asynchronous provider option sets.
9. Discuss host-mediated mutations separately if a real use case appears.

The first community discussion could combine steps 2–4 as one design issue but
split the implementation into reviewable changes.

## Acceptance criteria for an upstream implementation

An implementation should be tested for at least the following cases:

- no extensions are configured;
- one extension mounts in an overlay and in every visible question occurrence;
- two extensions share a slot with deterministic ordering;
- an extension script fails to load or throws during mount;
- navigating between pages updates or disposes all affected slots;
- repeated and nested question sets receive distinct occurrence contexts;
- read-only or disabled interviews expose the correct mode;
- extension cleanup removes listeners, observers, and mounted UI;
- the extension cannot access a Redux store or internal action through the
  public contract;
- keyboard and screen-reader behaviour remains unchanged when slots are empty.

## Clean-cut refactor boundary for `rdmo_ts4nfdi`

The plugin can be refactored without retaining its current internal architecture.
The goal is behavioural continuity, not compatibility with private modules.

### Behaviour to preserve

The refactored plugin should continue to provide:

- terminology-backed RDMO option providers;
- config-driven matching of catalog questions, attributes, and option sets;
- occurrence-correct annotations for existing interview answers;
- inline, source-aware annotation summaries;
- an on-demand details drawer with Gateway metadata;
- optional, lazily loaded TSS presentation where a suitable widget exists;
- a native prototype presentation when the external widget cannot cover the
  use case;
- authenticated and permission-checked access to project-related plugin data;
- vendor and Gateway compatibility management commands;
- current example-catalog and FAIRagro-style use cases.

### Compatibility not required

The refactor does not need compatibility layers for:

- private Python helper or service import paths;
- the current division of Python modules;
- current internal JSON response shapes used only by the plugin JavaScript;
- current JavaScript filenames, functions, DOM classes, or CSS classes;
- the current annotation marker implementation;
- current private plugin endpoint paths;
- old configuration keys that are replaced by a documented new schema.

Tests and deployment examples should move to the new contracts in the same
change. Dead modules should be removed instead of wrapping both architectures.

### Persisted contracts to treat deliberately

A clean cut should not accidentally invalidate data or configuration stored
outside this repository. In particular:

- catalog, question, attribute, option-set, and concept URIs are persisted
  identifiers;
- RDMO provider dotted paths can be stored in deployment settings or catalog
  configuration;
- provider registration keys can be referenced by an RDMO deployment.

The recommended choice is to keep the three existing public provider class
paths as thin entry points and replace their implementations completely. They
are external RDMO configuration contracts, not legacy service internals. If
changing them provides a concrete architectural benefit, the refactor must
include an explicit deployment and catalog migration rather than silent
breakage.

### Replaceable RDMO host adapter

For the current RDMO release, one adapter may continue to:

- load assets through the interview Django template;
- use the question-help marker;
- observe React-owned DOM only to detect mounting and navigation;
- read stable server-rendered metadata and call plugin REST endpoints.

This adapter must contain all knowledge of the present RDMO DOM and template
bridge. Terminology matching, Gateway access, annotation models, and renderers
must not query the RDMO DOM.

When RDMO offers an official extension API, a new host adapter should implement
the same plugin-side contract using RDMO slots and lifecycle callbacks. Removing
the side-loaded adapter must then require no change to the Gateway client,
matcher logic, annotation services, TSS adapter, or native renderer.

This preserves a functioning prototype now while making the future replacement
explicit and localised.
