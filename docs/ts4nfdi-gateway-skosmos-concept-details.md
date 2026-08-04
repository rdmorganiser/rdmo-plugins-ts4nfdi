# TS4NFDI Gateway issue: Skosmos concept details omit AGROVOC definitions

This is a copy-ready upstream issue draft for the
[TS4NFDI API Gateway](https://github.com/ts4nfdi/api-gateway/issues).

## Suggested title

> Skosmos concept-detail responses omit AGROVOC `skos:definition` values

## What Skosmos is

[Skosmos](https://skosmos.org/) is an open-source browser and publishing
application for vocabularies represented with the W3C Simple Knowledge
Organization System (SKOS). It provides a human-facing vocabulary browser,
Linked Data access, and a REST API.

AGROVOC is the controlled agricultural vocabulary in this example. The
AGROVOC service publishes that vocabulary through a Skosmos deployment at:

`https://agrovoc.fao.org/browse/`

Skosmos is therefore not another terminology alongside AGROVOC:

```text
AGROVOC                       vocabulary / concept scheme
    |
    v
AGROVOC Skosmos deployment   source service and API
    |
    v
TS4NFDI API Gateway          normalized, federated interface
    |
    v
RDMO plugin                  consumer of normalized Gateway responses
```

The Gateway configuration identifies the `agrovoc` database as a `skosmos`
backend whose source URL is:

`https://agrovoc.fao.org/browse/rest/v1`

The RDMO plugin deliberately does not call that source-specific API. It uses
the Gateway so that source routing and response normalization remain an
upstream responsibility.

## Environment

Observed on 29 July 2026:

- API Gateway production:
  `https://terminology.services.base4nfdi.de/api-gateway`
- API Gateway source commit inspected by the integration:
  `23c2e2a`
- Gateway database: `agrovoc`
- Gateway backend type: `skosmos`
- Example concept:
  `http://aims.fao.org/aos/agrovoc/c_4826` (`milk`)

## Reproduction

### 1. Search for the concept

```bash
curl --get \
  --data-urlencode 'query=milk' \
  --data-urlencode 'database=agrovoc' \
  'https://terminology.services.base4nfdi.de/api-gateway/search'
```

The matching result contains:

```json
{
  "iri": "http://aims.fao.org/aos/agrovoc/c_4826",
  "label": "milk",
  "descriptions": [],
  "synonyms": [],
  "short_form": "c_4826",
  "ontology": "agrovoc",
  "source_name": "agrovoc",
  "backend_type": "skosmos",
  "type": "skos:Concept"
}
```

### 2. Request the source-neutral concept-detail route

```bash
curl --get \
  --data-urlencode 'database=agrovoc' \
  'https://terminology.services.base4nfdi.de/api-gateway/artefacts/agrovoc/resources/concepts/http%3A%2F%2Faims.fao.org%2Faos%2Fagrovoc%2Fc_4826'
```

The detail response likewise contains:

```json
{
  "iri": "http://aims.fao.org/aos/agrovoc/c_4826",
  "label": "milk",
  "descriptions": [],
  "synonyms": [],
  "short_form": "c_4826",
  "ontology": "agrovoc",
  "source_name": "agrovoc",
  "backend_type": "skosmos",
  "type": null
}
```

### 3. Compare the source vocabulary

The
[AGROVOC page for `milk`](https://agrovoc.fao.org/browse/agrovoc/en/page/c_4826)
contains an English definition:

> Mammary secretion obtained by milking, intended for consumption as liquid
> milk or for further processing.

It also exposes the broader concept `animal products` and several narrower
concepts.

## Expected behavior

The normalized Gateway concept-detail response should expose the definition
available from the source, preferably in `descriptions`, while retaining the
source and terminology provenance:

```json
{
  "iri": "http://aims.fao.org/aos/agrovoc/c_4826",
  "label": "milk",
  "descriptions": [
    "Mammary secretion obtained by milking, intended for consumption or further processing."
  ],
  "ontology": "agrovoc",
  "source_name": "agrovoc",
  "backend_type": "skosmos",
  "type": "skos:Concept"
}
```

Synonyms may legitimately be empty for a particular concept and language.
The important requirement is that available source metadata must not be
silently omitted during normalization.

## Current mapping observation

At commit `23c2e2a`,
`src/main/resources/backend_types/skosmos.yml` defines:

```yaml
models:
  term:
    synonyms: altLabel
    descriptions: scopeNote

endpoints:
  concept_details:
    path: /agrovoc/label?acronym=%s&uri=%s
```

Two details appear relevant:

1. the concept-detail operation uses the Skosmos `label` endpoint, which does
   not represent the full concept record; and
2. `descriptions` maps `scopeNote` but not a definition field such as
   `definition` / `skos:definition`.

Please treat these as diagnostic observations rather than a required
implementation. The preferred fix is whichever source request and mapping
produce a complete normalized Gateway concept record.

## Impact

Consumers can identify and link the selected concept, but they cannot display
the semantic explanation that helps a user distinguish it from similarly
named concepts. Presentation libraries such as the Terminology Service Suite
cannot render information that is absent from the Gateway response.

This affects reusable embedded integrations in particular: each consumer
would otherwise need a Skosmos-specific request and response adapter,
defeating the purpose of the Gateway's normalized interface.

## Suggested acceptance criteria

- `/artefacts/agrovoc/resources/concepts/{encoded-iri}?database=agrovoc`
  returns the English AGROVOC definition for `c_4826`.
- The response retains `iri`, `label`, `ontology`, `source_name`,
  `backend_type`, `short_form`, and `type`.
- Search and concept-detail mappings use the same normalized field names.
- Concepts without definitions or synonyms continue to return valid empty
  arrays.
- A Gateway integration test covers a Skosmos concept with a definition.

## RDMO integration behavior

The RDMO plugin uses the generic Gateway concept-detail route for non-OLS
sources and falls back to the generic Gateway search route only when the
detail request fails. It does not call the AGROVOC Skosmos REST API directly.

Until the Gateway exposes semantic content, the interview drawer labels the
available source/backend fields as “Technical metadata” and explicitly tells
the user when no definition or synonyms were returned.
