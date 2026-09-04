rdmo-plugins-ts4nfdi
====================

This plugin integrates the Terminology Services 4 NFDI (TS4NFDI) API Gateway
with RDMO. It provides dynamic option-set providers and optional annotations
for terminology-backed values in the project interview.

Setup
-----

Install the plugin in your RDMO virtual environment using pip (directly from GitHub):

```bash
pip install git+https://github.com/rdmorganiser/rdmo-plugins-ts4nfdi
```

Add `rdmo_ts4nfdi` before RDMO and other apps which override the interview or
project-answer templates. This ordering lets Django use the TS4NFDI annotation
templates, including linked terminology answers in the normal answer view and
answer PDF, and compose the interview with another plugin such as
`rdmo_chatbot`:

```python
INSTALLED_APPS = [
    "rdmo_ts4nfdi",
    *INSTALLED_APPS,
]

...

OPTIONSET_PROVIDERS += [
    ("ts4nfdi_ontologies", _("TS4NFDI Ontologies"), "rdmo_ts4nfdi.providers.ontologies.TS4NFDIOntologiesProvider"),
    ("ts4nfdi_agrovoc_keywords", _("TS4NFDI AGROVOC Keywords"), "rdmo_ts4nfdi.providers.ontologies.TS4NFDIOntologiesProvider"),
    ("ts4nfdi_collections", _("TS4NFDI Collections"), "rdmo_ts4nfdi.providers.collections.TS4NFDICollectionsProvider"),
    ("ts4nfdi_fairagro_collection_terminologies", _("TS4NFDI Collection Terminologies: FAIRAgro"), "rdmo_ts4nfdi.providers.collection_terminologies.TS4NFDICollectionTerminologiesProvider"),
    ("ts4nfdi_entitysets", _("TS4NFDI Entity Sets"), "rdmo_ts4nfdi.providers.entitysets.TS4NFDIEntitySetProvider"),
]
```

Mount the authenticated annotation API in the root URL configuration:

```python
from django.urls import include, path

urlpatterns += [
    path("api/v1/ts4nfdi/", include("rdmo_ts4nfdi.urls")),
]
```

Add the annotated answer exports for projects and snapshots. These formats
combine the condition-aware RDMO answer tree with explicit semantic annotations;
they are not RDMO archival/import formats:

```python
PROJECT_EXPORTS += [
    (
        "ts-for-nfdi-json",
        _("TS4NFDI annotated JSON"),
        "rdmo_ts4nfdi.exports.AnnotatedJSONExport",
    ),
    (
        "ts-for-nfdi-simple-json",
        _("TS4NFDI simple annotated JSON"),
        "rdmo_ts4nfdi.exports.SimpleAnnotatedJSONExport",
    ),
    (
        "ts-for-nfdi-xml",
        _("TS4NFDI annotated XML"),
        "rdmo_ts4nfdi.exports.AnnotatedXMLExport",
    ),
    (
        "ts-for-nfdi-pdf",
        _("TS4NFDI annotated PDF"),
        "rdmo_ts4nfdi.exports.AnnotatedPDFExport",
    ),
]

PROJECT_SNAPSHOT_EXPORTS += [
    (
        "ts-for-nfdi-json",
        _("TS4NFDI annotated JSON"),
        "rdmo_ts4nfdi.exports.AnnotatedJSONExport",
    ),
    (
        "ts-for-nfdi-simple-json",
        _("TS4NFDI simple annotated JSON"),
        "rdmo_ts4nfdi.exports.SimpleAnnotatedJSONExport",
    ),
    (
        "ts-for-nfdi-xml",
        _("TS4NFDI annotated XML"),
        "rdmo_ts4nfdi.exports.AnnotatedXMLExport",
    ),
    (
        "ts-for-nfdi-pdf",
        _("TS4NFDI annotated PDF"),
        "rdmo_ts4nfdi.exports.AnnotatedPDFExport",
    ),
]
```

The detailed JSON, XML, and PDF formats use the same answer model; JSON and XML
expose it as the versioned `rdmo-ts4nfdi-annotated-answers` contract. The simple
JSON export projects that model into RDMO's flat question layout with structured
`label` and `iri` value pairs. A provider-backed
`Value.external_id` is marked as an annotation only when the configured
question matcher accepts it. In the detailed formats, static option URIs are
exported separately as RDMO option identifiers, and unmatched external
identifiers remain visible without being described as semantic annotations.
Export generation never performs Gateway requests.

See [Annotated answer exports](docs/annotated-answer-exports.md) for the
persistence boundary, annotation fields, export data flow, and the distinction
between semantic annotations, external identifiers, and RDMO option URIs.

This is a clean replacement for the former semantic-only JSON/XML sidecars.
Deployments using the old `SemanticJSONExport` or `SemanticXMLExport` class
paths must update their settings to the classes above.

RDMO 2.5.x restricts the export key used in its URL to lowercase ASCII letters
and hyphens (`[a-z-]+`). Keep `ts-for-nfdi-json`,
`ts-for-nfdi-simple-json`, `ts-for-nfdi-xml`, and `ts-for-nfdi-pdf` as the
internal keys; in particular, a key such as
`ts4nfdi-json` is invalid because it contains a digit. The translated labels
shown to users can still contain `TS4NFDI`.

The FAIRagro data-generation provider reads the configured Gateway entity set.
It returns each entity URI directly as the dynamic RDMO option ID, so RDMO's
normal provider persistence stores that concept IRI in `Value.external_id`.
The standard RDMO XML export therefore retains the selected terminology IRI;
no plugin-specific signal, manifest, or external-ID projection is involved.
This provider does not rewrite historic answers. Review existing project data
before changing an OptionSet provider in a deployment.

The gateway base URL is configured through `TS4NFDI_PROVIDER`. See
`ts4nfdi_provider.toml` for example provider keys using
`https://terminology.services.base4nfdi.de/api-gateway`.

The supplied configuration uses browser-direct Gateway transport for public
TSS-backed annotations such as EDAM. The public OLS4 GET route allows
cross-origin browser requests, so the widget can fetch its data without an
extra request through RDMO:

```toml
[frontend.gateway]
mode = "direct"
```

Only the public Gateway base URL is exposed to the browser in direct mode—never
an API token. Use `mode = "proxy"` for private sources, server-held
credentials, or deployments whose browser/network policy blocks direct access.

The FAIRagro data-generation OptionSet uses the generic
`ts4nfdi_entitysets` provider key with a configured public entity set:

```toml
[providers.ts4nfdi_entitysets]
endpoint = "entitysets/"
entityset_id = "fc45621d-7e40-47ce-9616-4133f0b54edf"
entityset_cache_timeout = 300
```

Terminology sources are declared once and referenced by providers and
annotation matchers. The source supplies both the human-readable breadcrumb
and the Gateway `database` parameter:

```toml
[sources.ebi]
label = "EBI"
database = "ebi"
backend_type = "ols2"
url = "https://www.ebi.ac.uk/ols4/api/v2"

[providers.ts4nfdi_ontologies]
endpoint = "search"
source_key = "ebi"
ontologies = ["edam"]
```

The autocomplete help then presents results as
`EBI › EDAM › EDAM_format_2332`, followed by the concept definition. A
provider or matcher with a `database` that conflicts with its source fails
configuration validation instead of silently querying a different source.

Providers can also remove already selected project values from autocomplete results by setting `exclude_selected_attribute_uris` for the relevant attribute URI(s) in `ts4nfdi_provider.toml`.

For `TS4NFDICollectionsProvider`, this behavior is disabled by default because repeated RDMO question sets can store the same collection option in different `set_prefix` and `set_index` contexts. To opt in, set `exclude_selected_collection_options = true` in the `ts4nfdi_collections` provider config.

Provider results are intentionally not deduplicated. This preserves distinct
Gateway results and allows the same concept to remain selectable in separate
RDMO collection/set contexts.

`TS4NFDICollectionTerminologiesProvider` lists the terminologies for one
configured, bounded collection. It is a browse provider: RDMO loads the list
once, displays the available terminologies when the select is opened, and
filters them locally while the user types. Configure `collection_id` and use
the `ols4/api/ontologies` endpoint with `collectionId`; `fallback_endpoint =
"collections/"` can be used to read the embedded `terminologies` list from the
collections overview when the ontology endpoint is unavailable or empty.

The bundled `/search` providers omit the optiongstal Gateway `display` query
parameter. The Gateway's default response already contains the identifiers,
labels, descriptions, terminology, and source metadata used by the plugin, and
avoiding field projection prevents a currently observed slow/timeout path in
the federated search endpoint.

If a provider request fails, the plugin can return a disabled diagnostic option by setting `show_request_errors = true` (default). The text can be customized with `request_error_text` and `request_error_help`.

Interview annotations
---------------------

Annotations are configured in the same `TS4NFDI_PROVIDER` dictionary. A
matcher must identify a question, its attribute, and its option set together.
This deliberately avoids annotating unrelated questions which happen to store
an HTTP URL.

```toml
[frontend]
[frontend.annotations]
enabled = true

[[frontend.annotations.matchers]]
id = "dataset-format"
question_uri = "https://rdmo.example.org/terms/questions/dataset/format"
attribute_uri = "https://rdmorganiser.github.io/terms/domain/project/dataset/format"
optionset_uri = "https://rdmo.example.org/terms/options/file_format_ts4nfdi"
resource_type = "entity"
badge_label = "EDAM"
ontology_id = "edam"
source_key = "ebi"
presentation = { adapter = "tss", component = "entity-info", entity_type = "class" }
```

A deliberately broad multi-source provider cannot put its selected source and
terminology into an RDMO `Value`: RDMO persists only the option label and IRI.
Enable the narrow v2 browser resolver when its inline annotation should recover
the same breadcrumb fields returned by Gateway search:

```toml
[[frontend.annotations.matchers]]
id = "broad-keyword"
question_uri = "https://rdmo.example.org/terms/questions/dataset/keyword"
attribute_uri = "https://rdmo.example.org/terms/domain/dataset/keyword"
optionset_uri = "https://rdmo.example.org/terms/options/keywords"
resource_type = "entity"
badge_label = "Terminology"
context_resolution = { adapter = "gateway-search" }
presentation = { adapter = "tss", component = "entity-info", entity_type = "class" }
```

Annotation API v2 remains metadata-free. After rendering the fallback row, the
browser searches by the stored label, requires an exact IRI match, and enriches
the in-memory row with source, terminology, backend, and short form. Identical requests
share a controller-lifetime cache; conflicting source contexts fail closed and
retain the generic breadcrumb. Direct mode calls the public Gateway, while
proxy mode uses the project-authorized `/gateway/search` compatibility route.
Neither mode changes the stored RDMO value. TSS is selected only when the
resolved source is an OLS2/OLS4 backend; other backends keep the native detail
view.

Native annotations for a bounded provider resource such as a terminology
collection can retain their own description without using the generic concept
metadata resolver. Set `provider_resource_detail = true` on its
provider-backed `collection` or `ontology` matcher:

```toml
[[frontend.annotations.matchers]]
id = "terminology-collection"
question_uri = "https://rdmo.example.org/terms/questions/metadata/collection"
attribute_uri = "https://rdmo.example.org/terms/domain/metadata/collection"
optionset_uri = "https://rdmo.example.org/terms/options/metadata/collections"
resource_type = "collection"
provider_key = "ts4nfdi_collections"
badge_label = "TS4NFDI collection"
provider_resource_detail = true
presentation = { adapter = "native" }
```

The page-list response stays Gateway-free. On opening the annotation, the
browser uses a project-authorized endpoint to read the selected record from
the same cached Gateway endpoint as the OptionSet provider. This is a small
native resource lookup, not a concept metadata or label-search fallback.

For a provider-backed ontology, `presentation = { adapter = "tss", component =
"ontology-info" }` is a conditional enhancement. If the ontology response omits
its source, the click-time resolver can join the selected ontology to its
configured collection member and source registry. The record is sent to TSS
only when this produces an OLS2/OLS4 backend, database, and ontology ID. The extra
collection request is cached; an incomplete, failed, or non-OLS result
continues to use the native description view.

The `presentation` table selects a replaceable browser presentation adapter.
The bundled `tss` adapter supports `entity-info` for entity annotations and
`ontology-info` for ontology annotations. The native drawer always remains the
primary view; compatible TSS widgets are lazy disclosures below it. The plugin
always uses TSS's OLS4 request mode and consistently supplies source parameters
such as `database=ebi`.

A deployment-owned ES module can also be registered under
`frontend.presentation_adapters` and selected by its adapter name. This makes
switching between native, TSS, and custom widgets a TOML configuration change,
without a plugin Python fork. See
[`docs/presentation-adapters.md`](docs/presentation-adapters.md) for the
deployment steps, supported TSS combinations, module contract, and cleanup
lifecycle.

This is a clean configuration cut. The former top-level matcher keys
`widget_type`, `entity_type`, `tabs`, and `use_legacy` are not accepted.
Move presentation-specific values into the nested `presentation` table as
shown above. Invalid matchers are logged and excluded, so deployments should
update their TOML before enabling the refactored plugin.

The annotation list endpoint returns only values belonging to a project the
authenticated user may access. Opening any annotation first resolves its
native Django detail. A compatible OLS2/OLS4 entity or ontology adds a lazy
TSS disclosure to that result; incomplete or non-OLS sources simply keep the
native detail. The optional browser-facing Gateway proxy is restricted to OLS
endpoints and an allowlist of query parameters; it never accepts an arbitrary
upstream URL.

Each saved annotation is displayed as a clickable
`source › terminology › term` row. Its drawer renders normalized Gateway
metadata directly: definitions, synonyms, source/database/backend,
terminology, short form, type, status, IRI actions, and a source link. The
official Terminology Service Suite widget is an optional collapsed enhancement
and is loaded only when the user expands it. Consequently, the useful detail
view remains available if a widget cannot interpret an upstream response, and
the widget does not issue background requests while collapsed.

On repeated RDMO pages, the current RDMO 2.5.1 DOM does not expose
`set_prefix` and `set_index`. The compatibility host therefore matches an
annotation occurrence against all visible selected labels, including
multi-value selects, and deliberately renders nothing when two occurrences
cannot be distinguished. It never falls back to an annotation from another
dataset. An official occurrence context remains the preferred upstream
solution; see `docs/rdmo-upstream-feature-requests.md`.

Template composition
--------------------

The plugin overrides `projects/project_interview.html` using Django's normal
template chaining. It calls `block.super` and contributes four independent
fragments:

- `rdmo_ts4nfdi/project_interview_head.html`
- `rdmo_ts4nfdi/project_interview_css.html`
- `rdmo_ts4nfdi/project_interview_js.html`
- `rdmo_ts4nfdi/project_interview_extra_body.html`

There is no Python, JavaScript, or template dependency on `rdmo_chatbot`. When
both plugins are installed, put `rdmo_ts4nfdi` first in `INSTALLED_APPS`; its
chained template then finds the chatbot interview template and retains the
chatbot's blocks through `block.super`.

If the deployment already maintains one combined
`projects/project_interview.html`, include the four fragments in the matching
blocks instead. This is also the most explicit merge strategy for further
interview plugins.

The question-help hook is provided by
`projects/project_interview_question_help.html`. RDMO must be configured to
render that interview template in the React application. The hook deliberately
contains no widget markup or TS4NFDI API assumptions; it is only a stable DOM
mount point for the controller.

Architecture
------------

The annotation implementation has four explicit boundaries:

- the application layer coordinates plugin-owned annotation models;
- the current RDMO host adapter translates project models and the
  template/React DOM into occurrence-aware annotation slots;
- TS4NFDI Gateway adapters own external HTTP requests and response mapping;
- a presentation registry selects the native prototype or TSS descriptor.

The browser follows the same composition. `RDMOTemplateInterviewHost` is the
only module which knows the current RDMO URL shape, loading indicator, React
CSS classes, or question-help marker. The controller communicates with it
through slot and lifecycle methods. The plugin REST client, native renderer,
drawer, and TSS adapter do not inspect RDMO's React state.

This separation is intentional. A future official RDMO front-end extension API
can replace `RDMOTemplateInterviewHost` while retaining the annotation API,
Gateway integration, and presentation adapters. The possible generic RDMO
extension points are documented in
`docs/rdmo-upstream-feature-requests.md`.

Backend adapters can be replaced through normal Django dotted paths:

```python
TS4NFDI_ADAPTERS = {
    "interview_host": "rdmo_ts4nfdi.integrations.rdmo.RDMOInterviewHost",
    "gateway": "rdmo_ts4nfdi.integrations.ts4nfdi.GatewayClient",
    "entityset_provenance": "rdmo_ts4nfdi.application.GatewayEntitySetProvenanceResolver",
    "provider_resource_detail": "rdmo_ts4nfdi.application.provider_resources.GatewayProviderResourceDetailResolver",
    "metadata_resolver": "rdmo_ts4nfdi.integrations.ts4nfdi.GatewayMetadataResolver",
    "presentation": "rdmo_ts4nfdi.presentation.AnnotationPresentationRegistry",
}
```

The defaults shown above do not need to be configured. Alternative classes
must implement the documented composition contract. Annotation adapters use
the small protocols in `rdmo_ts4nfdi.application.annotations`; the entity-set
provenance adapter receives the configured Gateway client and source registry.
The provider-resource detail adapter receives the configured Gateway client.

Upstream TS4NFDI dependencies
-----------------------------

The annotation UI uses the plain-HTML build of the official
`@ts4nfdi/terminology-service-suite-js` package. Its JS and CSS are vendored so
an RDMO deployment is reproducible and does not execute a floating CDN
dependency. Both assets always come from one npm release. Their version,
upstream tarball integrity, local hashes, and static paths are recorded in
`rdmo_ts4nfdi/vendor/terminology_service_suite.json`.

The bundle is loaded only when a user opens an annotation with an interactive
metadata or ontology widget. The template adds the pinned version to the asset
URLs for cache invalidation and supplies Subresource Integrity hashes to the
browser.

Do not edit the generated JS or CSS. To upgrade both files together from the
official npm registry from an RDMO application, run:

```shell
python manage.py ts4nfdi_vendor --latest
python manage.py ts4nfdi_vendor --check
```

An exact, reproducible upgrade is also possible with
`python manage.py ts4nfdi_vendor --tss-version 7.1.0` (`--version` is a
Django-reserved option). A scheduled dependency job can run
`python manage.py ts4nfdi_vendor --check-latest` to report a newly published
release. The updater reads npm's package metadata, verifies the published
`dist.integrity` value before opening the archive, extracts only the two
declared assets, updates their hashes, and then updates the manifest.

The equivalent repository/CI entry point is
`python scripts/update_tss_vendor.py`; it invokes the same package code and
accepts the same options. The management command is preferable in an RDMO app
because it resolves the exact installed `rdmo_ts4nfdi` package. Updating assets
inside an editable dependency changes its source checkout. For a non-editable
wheel installation, update the plugin source before building the wheel instead
of treating changes in `site-packages` as persistent.

After an upgrade, run the deployment's normal `collectstatic` step and restart
the Django processes so the cached manifest is reloaded. With `runserver`, a
restart followed by a hard browser reload is sufficient.

The Gateway itself is not vendored. The authenticated browser proxy forwards
official JSON responses without translating their shape and is limited to known
hosts, paths, and query parameters. This keeps the TSS widget on the upstream
Gateway response contract. The separate server-side metadata adapter maps
Gateway fields into the plugin's native annotation model.

An upstream Gateway timeout is returned by the browser proxy as `424 Failed
Dependency`, with `code: "gateway_timeout"` and `upstream_status: 504` in the
JSON response. It is logged as a warning and is not reported as a Django server
error, so a temporary terminology outage does not trigger `AdminEmailHandler`.
Other Gateway errors keep their original proxy status.

To detect a removed Gateway route before deployment, run:

```shell
python manage.py ts4nfdi_gateway_check
```

The checker reads the live Gateway OpenAPI document and verifies the entry
points used by the providers and widgets, including the `/entitysets` route
used by the FAIRagro Data Generation provider. Use `--openapi-url` when a
deployment targets another Gateway environment. The equivalent standalone entry
point is `python scripts/check_gateway_contract.py`.

To check the public responses needed by the supplied direct-mode example
configuration as well, run:

```shell
python manage.py ts4nfdi_gateway_check --live
```

This probes EDAM's OLS4 entity response, broad Gateway search, the configured
FAIRagro collection and entity set, and reports whether AGROVOC's OLS4 facade
is ready for a future TSS migration. It is an operator check, not a normal
request-path health check; a temporary public Gateway outage does not affect
the plugin's local tests.

The Gateway emits CORS headers only when it receives a browser `Origin`
header. To assert direct-mode CORS for both OLS4 and broad search for a
particular deployment, pass its RDMO origin explicitly:

```shell
python manage.py ts4nfdi_gateway_check --live --origin https://rdmo.example.org
```

Acknowledgements
----------------
This plugin has been developed through the [DMP4NFDI](https://dmp.services.base4nfdi.de/) project,
as an Incubator with [TS4NFDI](https://terminology.services.base4nfdi.de/) for the RDMO client of the [FAIRagro](https://fairagro.net/) consortium.

Both DMP4NFDI and TS4NFDI are Basic Services of Base4NFDI, funded by the German Research Foundation (DFG)
under project [521453681](https://gepris.dfg.de/gepris/projekt/521453681). FAIRagro is funded by the DFG under project [501899475](https://gepris.dfg.de/gepris/projekt/501899475).
Both projects are part of the German National Research Data Infrastructure (NFDI).
