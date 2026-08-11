# FAIRagro data-generation curation reference

The active FAIRagro data-generation OptionSet is no longer compiled from a
plugin-owned semantic mapping manifest. It reads the public TS4NFDI Gateway
entity set configured in [`ts4nfdi_provider.toml`](../ts4nfdi_provider.toml):

```toml
[providers.ts4nfdi_entitysets]
endpoint = "entitysets"
entityset_id = "fc45621d-7e40-47ce-9616-4133f0b54edf"
```

Each entity URI returned by that resource is the dynamic RDMO option identity.
RDMO consequently stores it in `Value.external_id`, and its normal XML export
retains the selected terminology IRI without a signal or a projection step.

## Curator workflow

`FAIRagro Options - data_generation.csv` remains an archived FAIRagro working
file. The plugin does not load, compile, validate, or deploy it. Updating the
CSV alone therefore has no effect on a running RDMO deployment.

To change the available data-generation choices:

1. Agree the curated concepts with FAIRagro and update the Gateway entity set
   through the TS4NFDI/Gateway-maintainer workflow.
2. Keep each entity's stable `uri`, `provider`, and `terminology` accurate.
   The URI becomes the saved RDMO answer identity.
3. Verify the public `entitysets` response and the RDMO provider output.
4. Restart the Django processes after changing this plugin configuration; no
   catalog import is required unless the question, OptionSet URI, or provider
   key changes.

The removed CSV-to-manifest compiler, option-to-concept mapping relations,
composition columns, `pre_save` projection, and
`ts4nfdi_sync_external_ids` command were part of the retired implementation.
They must not be used for new answers. Existing projects created with that old
provider retain their stored values; review them explicitly before changing
their catalog or provider configuration.

## Historical values

Changing the provider affects newly selected answers only. A historical value
whose `external_id` is an old FAIRagro option URI is not silently rewritten to
a terminology IRI. Automatic save signals are intentionally out of scope
because they would change archived project data without a reviewed mapping.

For an existing deployment:

1. inventory values whose identifiers use the retired FAIRagro option-URI
   namespace;
2. reselect the answer from the current entity set when only a small number of
   projects is affected; or
3. prepare a reviewed, versioned old-URI-to-concept-IRI table and use it in an
   explicit one-time migration with a dry-run report.

Do not infer the replacement from the answer label. Labels are not stable or
unique enough for a data migration. Free-text answers correctly retain an
empty external identifier.
