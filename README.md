rdmo-plugins-ts4nfdi
==================
This plugin implements dynamic option set, that queries the search endpoint of API Gateway of the Terminology Services 4 NFDI.

Setup
-----

Install the plugin in your RDMO virtual environment using pip (directly from GitHub):

```bash
pip install git+https://github.com/rdmorganiser/rdmo-plugins-ts4nfdi
```

Add the `rdmo_ts4nfdi` app to `INSTALLED_APPS` and the plugin to `OPTIONSET_PROVIDERS` in `config/settings/local.py`:

```python
INSTALLED_APPS += ['rdmo_ts4nfdi']

...

OPTIONSET_PROVIDERS += [
    ("ts4nfdi_ontologies", _("TS4NFDI Ontologies"), "rdmo_ts4nfdi.providers.ontologies.TS4NFDIOntologiesProvider"),
    ("ts4nfdi_collections", _("TS4NFDI Collections"), "rdmo_ts4nfdi.providers.collections.TS4NFDICollectionsProvider"),
]
```

The gateway base URL is configured through `TS4NFDI_PROVIDER`. See `ts4nfdi_provider.toml` for example provider keys using `https://terminology.services.base4nfdi.de/api-gateway`.

Providers can also remove already selected project values from autocomplete results by setting `exclude_selected_attribute_uris` for the relevant attribute URI(s) in `ts4nfdi_provider.toml`.

If a provider request fails, the plugin can return a disabled diagnostic option by setting `show_request_errors = true` (default). The text can be customized with `request_error_text` and `request_error_help`.

Frontend features are configured in the same `TS4NFDI_PROVIDER` dictionary under `[frontend]`. The plugin renders this as JSON before loading `terminology_widget.js`, so static JavaScript does not need to be edited:

```toml
[frontend]
breadcrumbs_enabled = true

[[frontend.breadcrumb_matchers]]
question_uri = "https://rdmo.example.org/terms/questions/dataset/format"
attribute_uri = "https://rdmorganiser.github.io/terms/domain/project/dataset/format"
optionset_uri = "https://rdmo.example.org/terms/options/file_format_ts4nfdi"
api = "https://api.terminology.tib.eu/api/"
ontology_id = "edam"
entity_type = "class"
parameter = "ontology=edam&fieldList=description,label,iri,ontology_name,type,short_form&childrenOf=http://edamontology.org/format_1915"
use_legacy = true
class_name = "ts4nfdi-breadcrumb-style"
```

Acknowledgements
-----
This plugin has been developed through the [DMP4NFDI](https://dmp.services.base4nfdi.de/) project,
as an Incubator with [TS4NFDI](https://terminology.services.base4nfdi.de/) for the RDMO client of the [FAIRagro](https://fairagro.net/) consortium.

Both DMP4NFDI and TS4NFDI are Basic Services of Base4NFDI, funded by the German Research Foundation (DFG)
under project [521453681](https://gepris.dfg.de/gepris/projekt/521453681). FAIRagro is funded by the DFG under project [501899475](https://gepris.dfg.de/gepris/projekt/501899475).
Both projects are part of the German National Research Data Infrastructure (NFDI).
