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

Add `rdmo_ts4nfdi` before RDMO and other apps which override the interview
template. This ordering lets Django compose the TS4NFDI interview template
with another plugin such as `rdmo_chatbot`:

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
    ("fairagro_data_generation", _("FAIRagro Data Generation Methods"), "rdmo_ts4nfdi.providers.semantic_options.FAIRAgroDataGenerationOptionSetProvider"),
]
```

Mount the authenticated annotation API in the root URL configuration:

```python
from django.urls import include, path

urlpatterns += [
    path("api/v1/ts4nfdi/", include("rdmo_ts4nfdi.urls")),
]
```

Add the semantic JSON export as a separate project export. It does not replace
RDMO's archival XML or human-readable JSON exports:

```python
PROJECT_EXPORTS += [
    (
        "ts-for-nfdi-json",
        _("TS4NFDI semantic JSON"),
        "rdmo_ts4nfdi.exports.SemanticJSONExport",
    ),
    (
        "ts-for-nfdi-xml",
        _("TS4NFDI semantic XML"),
        "rdmo_ts4nfdi.exports.SemanticXMLExport",
    ),
]
```

RDMO 2.5.x restricts the export key used in its URL to lowercase ASCII letters
and hyphens (`[a-z-]+`). Keep `ts-for-nfdi-json` and `ts-for-nfdi-xml` as the
internal keys; in particular, a key such as `ts4nfdi-json` is invalid because it
contains a digit. The translated labels shown to users can still contain
`TS4NFDI`.

The export retains the selected answer identity in `answer_id` and lists each
semantic concept separately in `iri`. For a mapped FAIRagro classification,
it therefore contains both the stable FAIRagro option URI and all mapped
concept IRIs, together with mapping-set provenance. Direct terminology
selections normally have the same URI in both fields.

The gateway base URL is configured through `TS4NFDI_PROVIDER`. See
`ts4nfdi_provider.toml` for example provider keys using
`https://terminology.services.base4nfdi.de/api-gateway`.

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

The `presentation` table selects a replaceable browser presentation adapter.
The bundled `tss` adapter supports `entity-info` and `metadata` for entity
annotations and `ontology-info` for ontology annotations. Use
`presentation = { adapter = "native" }` to keep only the plugin's native
prototype view. The configured source consistently supplies parameters such as
`database=ebi`.

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
authenticated user may access. Terminology detail is resolved on demand. The
browser-facing Gateway proxy is restricted to OLS endpoints and an allowlist
of query parameters; it never accepts an arbitrary upstream URL.

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
    "metadata_resolver": "rdmo_ts4nfdi.integrations.ts4nfdi.GatewayMetadataResolver",
    "presentation": "rdmo_ts4nfdi.presentation.AnnotationPresentationRegistry",
    "semantic_options": "rdmo_ts4nfdi.semantic_options.PackageSemanticOptionRegistry",
}
```

The defaults shown above do not need to be configured. Alternative classes
must implement the small protocols in
`rdmo_ts4nfdi.application.annotations`; their constructors follow the same
composition contract as the defaults.

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
`python manage.py ts4nfdi_vendor --tss-version 6.17.0` (`--version` is a
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
points used by the providers and widgets. Use `--openapi-url` when a deployment
targets another Gateway environment. The equivalent standalone entry point is
`python scripts/check_gateway_contract.py`.

Acknowledgements
----------------
This plugin has been developed through the [DMP4NFDI](https://dmp.services.base4nfdi.de/) project,
as an Incubator with [TS4NFDI](https://terminology.services.base4nfdi.de/) for the RDMO client of the [FAIRagro](https://fairagro.net/) consortium.

Both DMP4NFDI and TS4NFDI are Basic Services of Base4NFDI, funded by the German Research Foundation (DFG)
under project [521453681](https://gepris.dfg.de/gepris/projekt/521453681). FAIRagro is funded by the DFG under project [501899475](https://gepris.dfg.de/gepris/projekt/501899475).
Both projects are part of the German National Research Data Infrastructure (NFDI).
