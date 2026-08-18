# FAIRagro entity-set workflow

The FAIRagro data-generation OptionSet reads one public TS4NFDI Gateway entity
set. The entity URI is the dynamic RDMO option ID, so a selected curated concept
is stored in `Value.external_id` and retained in RDMO's standard exports.

```toml
[providers.ts4nfdi_entitysets]
endpoint = "entitysets/"
entityset_id = "fc45621d-7e40-47ce-9616-4133f0b54edf"
entityset_cache_timeout = 300
free_text_candidate = true
```

The list lookup is a temporary compatibility path: the plugin retrieves the
bounded `/entitysets/` response and selects this exact UUID locally. Replace
it with `GET /entitysets/{uuid}` after that Gateway endpoint is released and
deployed.

## Curator workflow

1. Agree the available concepts with FAIRagro and update the Gateway entity
   set through the TS4NFDI/Gateway-maintainer workflow.
2. Keep every entity's stable `uri`, `provider`, and `terminology` accurate.
   The URI becomes the stored identity for a curated answer.
3. Verify the entity-set response and provider output after each curation
   change. The plugin caches the list for the configured TTL.
4. Restart Django after changing plugin configuration. Re-import the catalog
   only when its questions or OptionSet bindings change.

## Curated concepts and free text

The example question deliberately permits free text as well as curated entity
set concepts. A curated selection has an external terminology IRI and can show
terminology details. A free-text selection is stored as ordinary RDMO text with
no external identifier or terminology annotation.

With `free_text_candidate = true`, the provider returns a visible, selectable
free-text entry when the typed text has no exact curated match. It displays the
typed term together with an explanation that selecting it saves free text. The
provider uses RDMO's existing `__isNew__` persistence path, so no data model or
front-end patch is needed for this workaround. The entry appears after RDMO's
normal asynchronous search delay; improving the immediate loading interaction
is covered by the separate RDMO feature-request draft.
