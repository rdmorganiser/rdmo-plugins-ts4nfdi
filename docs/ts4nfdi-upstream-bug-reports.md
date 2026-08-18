# Upstream TS4NFDI bug reports

These are copy-ready issue drafts based on the integration with RDMO. The TSS
report was checked against release 7.1.0 and commit
`0a1a0f485c0b16b4f56cfc305900975261f4c7c8`. The Gateway report was checked
against commit `05847535f1fde368c4ed00f85b6c153b428f5d22` and the live service on
2026-08-13.

## TSS: MetadataWidget makes a second request without `parameter`

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> MetadataWidget makes a second entity request without `parameter`

### Problem

`MetadataWidget` can receive a routing parameter such as `database=ebi`. Its
first entity request includes that parameter. The nested `TabWidget` makes a
second request for the same entity, but `MetadataWidget` does not pass the
parameter to it.

The second request is also made when all tabs are disabled. In that case its
result is not displayed.

This matters with a federated API: the scoped request can return the EBI copy
of an entity while the unscoped request returns a copy from another database.

### Reproduction

```javascript
window.ts4nfdiWidgets.createMetadata(
  {
    api: "https://terminology.services.base4nfdi.de/api-gateway/ols4/api/",
    iri: "http://edamontology.org/format_2332",
    ontologyId: "edam",
    entityType: "class",
    parameter: "database=ebi",
    useLegacy: false,
    altNamesTab: false,
    hierarchyTab: false,
    crossRefTab: false,
    terminologyInfoTab: false,
    graphViewTab: false,
    termDepictionTab: false,
    entityInfoTab: false,
    entityRelationTab: false
  },
  document.querySelector("#widget")
);
```

The browser sends these two requests:

```text
/ols4/api/v2/ontologies/edam/entities?iri=...&database=ebi
/ols4/api/v2/ontologies/edam/entities?iri=...
```

### Expected behavior

- If all tabs are disabled, do not mount or fetch `TabWidget`.
- If any tab is enabled, pass `parameter` to `TabWidget` and to any nested
  request that needs the same source context.
- Ideally, reuse the entity already loaded by `MetadataWidget` instead of
  fetching it again.

### Source check

In 7.1.0, `MetadataWidget` uses `parameter` in its own `useQuery`, then always
renders `TabWidget` without that prop. `TabWidget` runs another `useQuery`
before `TabPresentation` discovers that its tab list is empty.

- [MetadataWidget source](https://github.com/ts4nfdi/terminology-service-suite/blob/0a1a0f485c0b16b4f56cfc305900975261f4c7c8/packages/react/src/components/widgets/MetadataWidget/MetadataWidget.tsx)
- [TabWidget source](https://github.com/ts4nfdi/terminology-service-suite/blob/0a1a0f485c0b16b4f56cfc305900975261f4c7c8/packages/react/src/components/widgets/MetadataWidget/TabWidget/TabWidget.tsx)
- [TabPresentation source](https://github.com/ts4nfdi/terminology-service-suite/blob/0a1a0f485c0b16b4f56cfc305900975261f4c7c8/packages/react/src/components/widgets/MetadataWidget/TabWidget/TabPresentation.tsx)

Related issues [#30](https://github.com/ts4nfdi/terminology-service-suite/issues/30)
and [#146](https://github.com/ts4nfdi/terminology-service-suite/issues/146)
discuss duplicate querying and whether `TabWidget` is needed, but neither
describes the lost `parameter` in the current source.

## API Gateway: an unscoped entity lookup silently chooses one database

**Repository:**
[ts4nfdi/api-gateway](https://github.com/ts4nfdi/api-gateway/issues)

**Suggested title:**

> OLS4 entity lookup without `database` silently returns one source

### Problem

The same ontology and entity can be available from more than one Gateway
database. When `database` is omitted, the OLS4 entity endpoint silently returns
the first non-empty response. The response looks valid but does not explain
that another source was available or why this source was chosen.

This makes a missing routing parameter difficult to detect and can return
metadata from the wrong source context.

### Reproduction

```bash
curl --include \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332'
```

On 2026-08-13 this returned HTTP 200 and one TIB record. Both explicitly
scoped requests return a record from the requested source:

```bash
curl --fail \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332&database=ebi'

curl --fail \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332&database=tib'
```

### Expected behavior

Please make ambiguity explicit. Two possible contracts would be:

1. return all matching representations with their database/provider metadata;
2. return HTTP 400 when the result is ambiguous and explain that `database`
   is required.

At minimum, the API documentation should state how an unscoped result is
selected and recommend carrying `source_name` from search into `database` for
the entity lookup.

### Source check

`AbstractEndpointService.buildUrls()` queries every configured database when
`database` is empty. `selectResultsByDatabase()` then has a TODO to merge the
results and currently returns the first non-empty response.

- [AbstractEndpointService source](https://github.com/ts4nfdi/api-gateway/blob/05847535f1fde368c4ed00f85b6c153b428f5d22/src/main/java/org/semantics/apigateway/service/AbstractEndpointService.java)

## TSS: configurable retries

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> Allow consumers to configure React Query retry behavior in wrapped widgets

### Problem

Wrapped widgets create their own `QueryClient` with default options. A host
cannot disable or limit retries, so a permanent API error can produce several
identical requests for each mounted widget.

### Suggested behavior

Allow a retry option or a host-supplied `QueryClient`. Permanent HTTP 400 and
404 responses should preferably not be retried.
