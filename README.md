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

PROJECT_EXPORTS += [
    ("ts4nfdi", _("TS4NFDI Provider"), "rdmo_ts4nfdi.providers.TS4NFDIProvider"),
]
```

Acknowledgements
-----
This plugin has been developed through the [DMP4NFDI](https://dmp.services.base4nfdi.de/) project,
as an Incubator with [TS4NFDI](https://terminology.services.base4nfdi.de/) for the RDMO client of the [FAIRagro](https://fairagro.net/) consortium.

Both DMP4NFDI and TS4NFDI are Basic Services of Base4NFDI, funded by the German Research Foundation (DFG)
under project [521453681](https://gepris.dfg.de/gepris/projekt/521453681). FAIRagro is funded by the DFG under project [501899475](https://gepris.dfg.de/gepris/projekt/501899475).
Both projects are part of the German National Research Data Infrastructure (NFDI).
