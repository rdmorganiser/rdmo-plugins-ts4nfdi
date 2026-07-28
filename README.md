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
    ("ts4nfdi_collections", _("TS4NFDI Collections"), "rdmo_ts4nfdi.providers.collections.TS4NFDICollectionsProvider"),
    ("ts4nfdi_collection_terminologies_fairagro", _("TS4NFDI Collection Terminologies: FAIRAgro"), "rdmo_ts4nfdi.providers.collection_terminologies.TS4NFDICollectionTerminologiesProvider"),
]
```

Mount the authenticated annotation API in the root URL configuration:

```python
from django.urls import include, path

urlpatterns += [
    path("api/v1/ts4nfdi/", include("rdmo_ts4nfdi.urls")),
]
```

The gateway base URL is configured through `TS4NFDI_PROVIDER`. See
`ts4nfdi_provider.toml` for example provider keys using
`https://terminology.services.base4nfdi.de/api-gateway`.

Providers can also remove already selected project values from autocomplete results by setting `exclude_selected_attribute_uris` for the relevant attribute URI(s) in `ts4nfdi_provider.toml`.

For `TS4NFDICollectionsProvider`, this behavior is disabled by default because repeated RDMO question sets can store the same collection option in different `set_prefix` and `set_index` contexts. To opt in, set `exclude_selected_collection_options = true` in the `ts4nfdi_collections` provider config.

`TS4NFDICollectionTerminologiesProvider` lists the terminologies for one configured collection. Configure `collection_id` and use the `ols4/api/ontologies` endpoint with `collectionId`; `fallback_endpoint = "collections/"` can be used to read the embedded `terminologies` list from the collections overview when the ontology endpoint is unavailable or empty.

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
entity_type = "class"
tabs = ["synonyms", "hierarchy", "ontology", "crossref"]

[frontend.annotations.matchers.gateway_params]
database = "ebi"
```

The annotation list endpoint returns only values belonging to a project the
authenticated user may access. Terminology detail is resolved on demand. The
browser-facing Gateway proxy is restricted to OLS endpoints and an allowlist
of query parameters; it never accepts an arbitrary upstream URL.

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

The Gateway itself is not vendored. The plugin targets the configured
`gateway.base_url`, forwards official JSON responses without translating their
shape, and limits its authenticated browser proxy to known hosts, paths, and
query parameters. This keeps response-model compatibility in the upstream
Gateway/TSS pair. To detect a removed Gateway route before deployment, run:

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
