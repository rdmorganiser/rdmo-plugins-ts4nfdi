# Upstream TS4NFDI bug reports

This document contains copy-ready issue drafts based on problems observed
while integrating the TS4NFDI API Gateway and Terminology Service Suite (TSS)
into the RDMO interview.

The reports were prepared against:

- `@ts4nfdi/terminology-service-suite-js` 6.17.0;
- Terminology Service Suite commit `a3390fc7`; and
- API Gateway commit `23c2e2a`.

Before submitting an issue, reproduce it against the current upstream release
and replace these versions if necessary.

## Terminology Service Suite: MetadataWidget loses API parameters

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> MetadataWidget does not propagate `parameter` to nested widgets, causing
> unscoped requests and repeated retries

### Describe the bug

`MetadataWidget` accepts an additional `parameter`, for example
`database=tib`. The initial entity request includes this parameter, but the
nested `TabWidget` request does not. This causes requests to the TS4NFDI API
Gateway without the required database/source selector.

React Query then retries the failing request several times.

### Version

- `@ts4nfdi/terminology-service-suite-js`: 6.17.0
- Commit: `a3390fc7`
- API: TS4NFDI Gateway OLS2-compatible endpoint

### To reproduce

Mount the plain JavaScript Metadata widget:

```html
<div id="widget"></div>

<script>
window.ts4nfdiWidgets.createMetadata(
    {
        api: "https://terminology.services.base4nfdi.de/api-gateway/ols4/api/",
        iri: "http://edamontology.org/format_2332",
        ontologyId: "edam",
        entityType: "class",
        parameter: "database=tib",
        useLegacy: false
    },
    document.querySelector("#widget")
);
</script>
```

Observe the network requests:

1. This request succeeds:

   ```text
   /ols4/api/v2/ontologies/edam/entities?iri=...&database=tib
   ```

2. A nested request omits the parameter:

   ```text
   /ols4/api/v2/ontologies/edam/entities?iri=...
   ```

3. The parameterless request fails and is retried several times.

### Expected behavior

Every request made by `MetadataWidget` and its nested widgets should inherit
the configured `parameter`.

At least the following propagation paths appear affected:

- `MetadataWidget` to `TabWidget`;
- `TabWidget` to `TabPresentation`; and
- `TabPresentation` to nested hierarchy, ontology-information,
  entity-information, and entity-relation widgets.

### Relevant source locations

`MetadataWidget` destructures `parameter` and uses it for its own request, but
does not pass it to `TabWidget`.

`TabWidget` also destructures `parameter`, but does not pass it into
`TabPresentation`. The terminology-information tab explicitly supplies an
empty parameter.

- [MetadataWidget.tsx](https://github.com/ts4nfdi/terminology-service-suite/blob/a3390fc7/packages/react/src/components/widgets/MetadataWidget/MetadataWidget.tsx)
- [TabWidget.tsx](https://github.com/ts4nfdi/terminology-service-suite/blob/a3390fc7/packages/react/src/components/widgets/MetadataWidget/TabWidget/TabWidget.tsx)
- [TabPresentation.tsx](https://github.com/ts4nfdi/terminology-service-suite/blob/a3390fc7/packages/react/src/components/widgets/MetadataWidget/TabWidget/TabPresentation.tsx)

### Impact

This prevents the widget from being used reliably with the federated Gateway,
where the same terminology or term IRI may be available from several sources
and `database` is needed to route the request.

## API Gateway: entity lookup without a database returns HTTP 500

**Repository:**
[ts4nfdi/api-gateway](https://github.com/ts4nfdi/api-gateway/issues)

**Suggested title:**

> OLS2 entity endpoint returns HTTP 500 when an entity is available from
> multiple databases

### Description

The OLS2-compatible entity endpoint returns HTTP 500 when `database` is
omitted for an EDAM term. Supplying either database that hosts EDAM succeeds.

The generated OpenAPI documentation describes `database` as optional.

### Reproduction

Request the entity without a database:

```bash
curl --include \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332'
```

The response is HTTP 500:

```http
HTTP/2 500
```

```json
{
  "status": 500,
  "error": "Internal Server Error",
  "path": "/api-gateway/ols4/api/v2/ontologies/edam/entities"
}
```

Both source-specific requests succeed:

```bash
curl --fail \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332&database=ebi'

curl --fail \
  'https://terminology.services.base4nfdi.de/api-gateway/ols4/api/v2/ontologies/edam/entities?iri=http%3A%2F%2Fedamontology.org%2Fformat_2332&database=tib'
```

### Expected behavior

One of the following behaviors would be preferable:

1. Federate the lookup and return all matching representations, including
   `source_name`, `source`, and `backend_type`.
2. Return HTTP 400 with a message explaining that `database` is required when
   the lookup is ambiguous and, ideally, list the available sources.

An omitted optional parameter should not produce an internal server error.

### Additional context

The Gateway search endpoint already includes the routing provenance needed
for a subsequent lookup:

- `source_name`;
- `source`;
- `backend_type`;
- `ontology`;
- `ontology_iri`; and
- `iri`.

The Gateway frontend uses `source_name` as the `database` parameter when it
loads concept trees. It would be helpful if this behavior and requirement
were also explicit in the API documentation.

Relevant upstream frontend code:

- [Search result and source breadcrumb](https://github.com/ts4nfdi/api-gateway/blob/23c2e2a/src/frontend/app/home/search/AutoCompleteResult.tsx)
- [Source-aware concept requests](https://github.com/ts4nfdi/api-gateway/blob/23c2e2a/src/frontend/app/api/ArtefactsRestClient.ts)

## Terminology Service Suite feature request: configurable retries

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> Allow consumers to configure React Query retry behavior in wrapped widgets

### Description

Wrapped widgets instantiate their own `QueryClient` with default options.
Consumers therefore cannot disable or limit retries. A permanent API error
can result in several identical requests from each mounted widget.

### Suggested behavior

Consider accepting retry configuration such as:

- `retry: false`;
- `retry: number`; or
- an externally supplied `QueryClient` or set of default query options.

Permanent HTTP 400 and 404 responses should preferably not be retried.

This is especially important for embedded widgets, where several widget
instances can otherwise amplify one Gateway error into many requests.

## Integration note: terminology identity and source routing

The Gateway search interface exposes three distinct levels:

```text
source/database → terminology → term
```

For example:

```text
TIB → EDAM → EDAM_2332
```

EDAM is the terminology. TIB and EBI are separate OLS2 services that can host
EDAM. The term IRI identifies the term, while `source_name` identifies which
service should answer a subsequent Gateway request.

An integration should therefore keep the following information distinct:

| Information | Example | Purpose |
| --- | --- | --- |
| Source | `tib` or `ebi` | Routes subsequent Gateway calls |
| Backend type | `ols2` | Describes the source API |
| Terminology | `edam` | Gives the term its semantic context |
| Term IRI | `http://edamontology.org/format_2332` | Stable semantic identity |
| Short form | `EDAM_2332` | Human-readable identifier |
| Label | `XML` | Answer shown to the user |

The source must not be inferred from the term IRI. It should be retained as
separate routing provenance. Likewise, the source must not be encoded into or
substituted for the stable term IRI.

For a provider restricted to one configured database, the configured database
can supply this provenance. A federated, multi-source provider must preserve
the selected result's `source_name`, `source`, and `backend_type` separately
from RDMO's `external_id`.
