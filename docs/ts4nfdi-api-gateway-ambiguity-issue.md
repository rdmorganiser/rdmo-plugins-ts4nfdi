# OLS4 entity lookup without `database` silently returns one source

## Problem

The same ontology and entity can be available from more than one Gateway
database. When `database` is omitted, the OLS4 entity endpoint silently returns
the first non-empty response. The response looks valid but does not explain
that another source was available or why this source was chosen.

This makes a missing routing parameter difficult to detect and can return
metadata from the wrong source context.

## Reproduction

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

## Expected behavior

Please make ambiguity explicit. Two possible contracts would be:

1. return all matching representations with their database/provider metadata;
2. return HTTP 400 when the result is ambiguous and explain that `database`
   is required.

At minimum, the API documentation should state how an unscoped result is
selected and recommend carrying `source_name` from search into `database` for
the entity lookup.

## Source check

Checked against API Gateway commit
`05847535f1fde368c4ed00f85b6c153b428f5d22` and the live service on
2026-08-13.

`AbstractEndpointService.buildUrls()` queries every configured database when
`database` is empty. `selectResultsByDatabase()` then has a TODO to merge the
results and currently returns the first non-empty response.

- [AbstractEndpointService source](https://github.com/ts4nfdi/api-gateway/blob/05847535f1fde368c4ed00f85b6c153b428f5d22/src/main/java/org/semantics/apigateway/service/AbstractEndpointService.java)
