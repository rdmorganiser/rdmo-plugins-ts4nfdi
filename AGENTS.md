The folder `rdmo_ts4nfdi/` contains the python code for this plugin.
It is build as a Django app for the RDMO software. A few tests are in `tests/`. 
The folder `xml/` contains an example of the rdmo content that uses this plugin in the interview (via the catalog).
Under `.external_code/` there are some source repositories that should be considered as read-only and are relevant to this plugin. For example RDMO itself (`.external_code/rdmorganiser/rdmo`) and a few other
rdmo plugins, as well as the code that the TS4NFDI project provides such as `.external_code/ts4nfdi/terminology-service-suite` and their `.external_code/ts4nfdi/api-gateway`.
We want to leverage the metadata of the terminology endpoints provided by `ts4nfdi-api-gateways-docs.json` 
in our rdmo interview, for things such as search for the relevant ontologies or make annotations in the UI of the interview.  

