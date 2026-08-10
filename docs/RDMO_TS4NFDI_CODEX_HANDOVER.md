# RDMO TS4NFDI Plugin Refactor — Codex Handover

## Purpose

This document hands over the current refactoring direction for `rdmorganiser/rdmo-plugins-ts4nfdi`.

The goal is to simplify the plugin by moving terminology-specific responsibilities to the components that already own them:

- **RDMO server** owns RDMO authorization, project/value traversal, matcher selection, and semantic annotation descriptors.
- **Browser plugin** owns annotation interaction, presentation selection, and direct-vs-proxy transport selection.
- **Terminology Service Suite (TSS)** owns rich terminology UI and terminology metadata fetching for TSS-backed annotations.
- **TS4NFDI API Gateway** owns source selection, backend translation/federation, and normalized OLS-compatible terminology responses.

A second major simplification is the Gateway **`/entitysets`** endpoint, which replaces the plugin-owned FAIRagro CSV → semantic option-set → mapping/projection workflow for the Data Generation question.

Codex should use this document as architectural context, but **must verify the current state against the local checkout** before making further changes.

---

# 1. High-level target architecture

```text
RDMO interview
    │
    │  page annotation discovery
    ▼
RDMO plugin backend
    │
    │  v2 semantic annotation descriptors
    ▼
Browser annotation controller
    │
    ├── Native detail adapter
    │       └── lightweight local/server detail where needed
    │
    └── TSS detail adapter
            │
            ├── direct mode
            │      └── Browser → TS4NFDI Gateway
            │
            └── proxy mode
                   └── Browser → RDMO proxy → TS4NFDI Gateway

TSS owns:
    - entity metadata retrieval
    - ontology metadata retrieval
    - OLS model normalization
    - rich terminology rendering

Gateway owns:
    - database/source selection
    - heterogeneous backend translation
    - OLS-compatible facade
    - federation
```

The important architectural rule is:

> **Do not reimplement Gateway/TSS terminology normalization in the RDMO plugin.**

---

# 2. Existing RDMO dynamic OptionSet provider flow stays server-side

The normal RDMO dynamic option-provider mechanism remains a good fit and is **not** the main refactoring target.

Typical flow:

```text
Browser RDMO select
    ↓
GET /api/v1/projects/projects/{project_id}/options/
    ?optionset=...
    &search=...
    ↓
RDMO ProjectViewSet.options
    ↓
rdmo-plugins-ts4nfdi Provider
    ↓
TS4NFDI API Gateway
```

Selected values are normally persisted as:

```text
Value.external_id = external terminology/entity identifier
Value.text        = selected label
```

Keep this server-side provider flow intact.

The refactor is mainly about:

1. removing the custom FAIRagro semantic-option mapping system, and
2. simplifying interview annotations/details.

---

# 3. FAIRagro Data Generation: replace custom semantic option sets with `/entitysets`

## 3.1 Gateway endpoint

The TS4NFDI Gateway exposes:

```text
https://terminology.services.base4nfdi.de/api-gateway/entitysets
```

For the FAIRagro Data Generation use case, the entity-set ID used in this work is:

```text
fc45621d-7e40-47ce-9616-4133f0b54edf
```

An entity-set entity conceptually looks like:

```json
{
  "uri": "http://opendata.inrae.fr/thesaurusINRAE/c_17625",
  "label": [
    {
      "value": "field experiment",
      "lang": "en"
    }
  ],
  "definition": [
    {
      "value": "A field-based experiment.",
      "lang": "en"
    }
  ],
  "terminology": "INRAETHES",
  "provider": "agroportal"
}
```

This means the plugin no longer needs to maintain a second local representation of:

- FAIRagro option IDs,
- terminology target IDs,
- mapping relations,
- curation statuses,
- mapping-set versions,
- CSV → JSON conversion,
- option URI → terminology IRI projection.

The terminology entity IRI itself can be the RDMO option identity.

## 3.2 Generic entity-set provider

The intended provider is generic, not FAIRagro-specific:

```text
rdmo_ts4nfdi/providers/entitysets.py
```

```python
class TS4NFDIEntitySetProvider(TS4NFDIBaseProvider):
    search = False
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        ...
```

The provider should:

1. read its normal provider config,
2. require an `entityset_id`,
3. request the configured Gateway `entitysets` endpoint,
4. select the configured entity set,
5. convert each entity into a standard RDMO dynamic option,
6. use `entity["uri"]` as the option `id`,
7. choose a localized label,
8. optionally build display help from `provider`, `terminology`, and definition.

Example resulting RDMO option:

```python
{
    "id": "http://opendata.inrae.fr/thesaurusINRAE/c_17625",
    "text": "field experiment",
    "help": "... AgroPortal › INRAETHES › field experiment ..."
}
```

The important invariant is:

```text
RDMO Value.external_id == selected terminology entity IRI
```

There is no intermediate plugin-owned FAIRagro option URI that then has to be projected to another IRI.

## 3.3 Configuration

Use the generic RDMO provider key:

```text
ts4nfdi_entitysets
```

Configure it with the FAIRagro entity set for this example:

```toml
[providers.ts4nfdi_entitysets]
endpoint = "entitysets"
entityset_id = "fc45621d-7e40-47ce-9616-4133f0b54edf"
```

The RDMO registration should point to:

```python
"rdmo_ts4nfdi.providers.entitysets.TS4NFDIEntitySetProvider"
```

The example catalog and FAIRagro deployment use this key. A different
entity-set configuration can use a separate generic provider key when RDMO
needs to expose more than one entity set.

## 3.4 Old semantic-option subsystem to remove

The following concepts are no longer needed for FAIRagro Data Generation:

```text
SemanticOption
SemanticTarget
SemanticOptionSet
SemanticOptionRegistry
PackageSemanticOptionRegistry
SemanticAnnotationTargetResolver mapping expansion
SemanticOptionExternalIdProjector
OptionExternalIdProjectionPolicy
mapping_set_id
mapping_set_version
option_external_id storage/projection policy
pre-save external_id projection signal
ts4nfdi_sync_external_ids management command
CSV → semantic JSON workflow
packaged FAIRagro semantic manifest
```

Likely old files/remnants to verify and delete:

```text
rdmo_ts4nfdi/application/value_projection.py
rdmo_ts4nfdi/domain/semantic_options.py
rdmo_ts4nfdi/integrations/rdmo/value_projection.py
rdmo_ts4nfdi/management/commands/ts4nfdi_sync_external_ids.py
rdmo_ts4nfdi/providers/semantic_options.py
rdmo_ts4nfdi/semantic_options.py
rdmo_ts4nfdi/data/semantic_option_sets/
docs/semantic-option-workflow.md
docs/FAIRagro Options - data_generation.csv
tests/test_value_projection.py
```

Codex should search for residual references rather than blindly deleting based only on this list.

Useful searches:

```bash
rg "SemanticOption|SemanticTarget|mapping_set_id|mapping_set_version"
rg "option_external_id|value_projection|semantic_options"
rg "fairagro-data-generation"
```

---

# 4. Annotation architecture: server returns semantic descriptors, not TSS transport props

Historically the annotation backend did too much:

1. RDMO project authorization,
2. project/value traversal,
3. matcher identification,
4. source/terminology contextualization,
5. Gateway metadata calls,
6. OLS/Skosmos response normalization,
7. TSS prop generation,
8. Gateway proxying.

The target separation is:

```text
RDMO backend
    = what annotation is this?

Browser
    = how should it be presented?

TSS
    = fetch and render rich terminology information

Gateway
    = translate/federate terminology backends
```

---

# 5. Annotation API v2

## 5.1 Keep migration additive

The refactor was intentionally designed to be additive first.

The old list/detail/proxy APIs can stay temporarily while the browser migrates.

Conceptually:

```text
v1
/projects/<project_id>/annotations/
/projects/<project_id>/annotations/<value_id>/

v2
/projects/<project_id>/annotations/v2/
```

Exact routing should be verified locally.

The v2 list endpoint should perform **zero Gateway metadata HTTP calls**.

## 5.2 Desired v2 annotation descriptor

```json
{
  "value_id": 918,
  "matcher_id": "fairagro-dataset-format",
  "kind": "entity",
  "label": "XML",
  "iri": "http://edamontology.org/format_2332",
  "source": {
    "id": "ebi",
    "label": "EBI",
    "database": "ebi",
    "backend_type": "ols2"
  },
  "terminology": {
    "id": "edam",
    "label": "EDAM"
  },
  "gateway_context": {
    "ontology_id": "edam",
    "database": "ebi",
    "backend_type": "ols2",
    "params": {}
  },
  "presentation": {
    "adapter": "tss",
    "component": "entity-info",
    "options": {
      "entity_type": "class"
    }
  }
}
```

Earlier architecture notes called the terminology identifier `artefact_id`; the later implementation direction used:

```text
gateway_context.ontology_id
```

Codex should check the local code and decide whether the API naming should remain `ontology_id` or be renamed before the contract becomes stable.

The semantic requirement is:

> A TSS/Gateway entity descriptor must contain the deterministic ontology/artefact identifier required by the Gateway OLS4 route.

## 5.3 Suggested v2 domain model

The implementation direction included classes similar to:

```python
@dataclass(frozen=True, slots=True)
class GatewayContext:
    ontology_id: str | None = None
    database: str | None = None
    backend_type: str | None = None
    params: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "ontology_id": self.ontology_id,
            "database": self.database,
            "backend_type": self.backend_type,
            "params": dict(self.params),
        }
```

and:

```python
@dataclass(frozen=True, slots=True)
class AnnotationDescriptor:
    annotation: AnnotationSummary
    gateway_context: GatewayContext | None
    presentation: PresentationPolicy
```

plus v2 occurrence/page containers.

Verify exact classes in the local checkout.

## 5.4 Public Gateway parameter allowlist

Frontend-safe descriptors must not leak server credentials or arbitrary Gateway parameters.

The discussed allowlist is:

```text
database
collectionId
lang
```

Never serialize:

```text
api_token
Authorization
server-only credentials
arbitrary unvalidated query parameters
```

The browser implementation also discussed rejecting dangerous delimiter/control characters before producing TSS's current string-based `parameter` prop.

---

# 6. Important Gateway OLS4 constraint

Rich TSS entity descriptors should use deterministic ontology-scoped entity lookup, conceptually:

```text
/ols4/api/v2/ontologies/{ontology}/entities?iri=...
```

Therefore:

> **Rich TSS entity descriptors must have a resolved ontology/artefact identifier.**

Do not retain the old normal-resolution behavior of:

```text
try ontology-specific entity lookup
→ fallback to global /entities
→ fallback to search by label
```

Normal metadata rendering should be deterministic.

---

# 7. Browser-side detail coordinator

## 7.1 Target interface

The browser controller should no longer conceptually depend on:

```javascript
api.detail(...)
```

It should depend on something like:

```javascript
details.resolve(annotation)
```

The discussed structure is:

```text
InterviewAnnotationController
    ├── annotations.list(...)
    └── details.resolve(...)
             │
             ├── TSS detail path
             └── Native/legacy fallback
```

A class discussed during implementation was:

```text
AnnotationDetailCoordinator
```

in:

```text
rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/detail_coordinator.js
```

Verify locally.

## 7.2 Migration behavior

The safe migration rule is:

```text
if annotation has a complete deterministic TSS descriptor:
    do NOT call Django detail endpoint
    construct TSS presentation client-side
else:
    fall back to the existing api.detail(...)
```

This allows the new path to run in parallel with the old path.

The controller should use v2 annotation discovery while still retaining server detail fallback for:

- native annotations,
- collection details not yet migrated,
- incomplete TSS descriptors,
- custom presentation adapters where appropriate.

---

# 8. Direct versus proxy Gateway mode

Support an explicit browser transport mode:

```text
direct
proxy
```

Avoid an implicit auto mode initially.

## Direct

```text
Browser
  ↓
public TS4NFDI API Gateway
```

Advantages:

- no Django request on annotation click,
- simpler server,
- TSS talks to the Gateway directly.

## Proxy

```text
Browser
  ↓
RDMO Gateway proxy
  ↓
TS4NFDI API Gateway
```

Retain this mode for cases involving:

- server-held API token,
- private resources,
- deployment networking restrictions,
- CORS limitations,
- operational rollback.

Never expose a server API token in direct mode.

## 8.1 Frontend config

Conceptually:

```toml
[frontend.gateway]
mode = "direct"
```

Sanitized browser config:

```json
{
  "gateway": {
    "mode": "direct",
    "base_url": "https://terminology.services.base4nfdi.de/api-gateway"
  }
}
```

For `proxy` mode, the browser does not need a secret or external base URL.

The code direction discussed uses `proxy` as the safe default when the deployment does not explicitly opt into `direct`.

Verify exact local behavior.

---

# 9. Browser TSS prop construction

The browser should translate semantic v2 descriptors into TSS props.

For an entity:

```javascript
{
    api: ".../ols4/api/",
    iri: annotation.iri,
    ontologyId: annotation.gateway_context.ontology_id,
    entityType: annotation.presentation.options?.entity_type,
    parameter: "database=ebi"
}
```

For `entity-info`, preserve presentation flags such as:

```javascript
{
    hasTitle: false,
    showBadges: true
}
```

For `metadata`, map configured tabs to TSS props:

```javascript
altNamesTab
hierarchyTab
crossRefTab
terminologyInfoTab
graphViewTab
termDepictionTab
entityInfoTab
entityRelationTab
copyButton
```

For `ontology-info`:

```javascript
{
    ontologyId: annotation.gateway_context.ontology_id
}
```

The ownership rule is:

> Python should not build complete TSS transport props anymore.

Python returns semantic context and presentation policy. JavaScript creates TSS props.

---

# 10. TSS integration and lifecycle

The plugin vendors the plain-JavaScript TSS bundle.

Target version discussed:

```text
@ts4nfdi/terminology-service-suite-js 7.1.0
```

Codex should check the local vendor manifest and assets; do not assume the local update actually happened.

### Vendor verification note (2026-08-10)

The committed `7.1.0` manifest currently records script SHA-256
`725a708d…`, while the committed `index.iife.js` hashes to `5ec37cc9…`.
Consequently `ts4nfdi_vendor --check` and its single asset-verification test
fail before or after the entity-set provenance work. Do not update that hash
blindly as part of annotation work; rerun the deliberate vendor update against
the intended official release and commit the asset and manifest together.

The browser presentation registry already has lifecycle normalization for values like:

```javascript
function
unmount()
destroy()
```

This aligns with a proposed upstream TSS feature request:

```text
Plain-JS widget factories should return a lifecycle handle with destroy()
```

Possible future upstream interface:

```typescript
interface TssWidgetHandle {
    destroy(): void;
}
```

Optional later extension:

```typescript
interface TssWidgetHandle<Props> {
    update(props: Props): void;
    destroy(): void;
}
```

`destroy()` is the important first feature.

---

# 11. TSS should own terminology metadata normalization

The old server-side `GatewayMetadataResolver` contains OLS and non-OLS branches, response-shape normalization, Skosmos fallback handling, search fallback, definition/synonym extraction, etc.

Do **not** port this resolver wholesale into JavaScript.

TSS already has the API/model layer required by its own widgets and should fetch/render rich terminology metadata directly.

Desired result:

```text
TSS-backed annotation
    ↓
browser constructs props
    ↓
TSS widget
    ↓
Gateway OLS4 API
```

No parallel plugin-side metadata normalization.

---

# 12. TSS upstream opportunities

Three possible upstream contributions were identified.

## 12.1 First priority: plain-JS lifecycle handle

Issue idea:

```text
Plain-JS widget factories: return a lifecycle handle with destroy()
```

Reason:

- third-party apps need explicit cleanup,
- dynamic drawers/modals/routes remove widget containers,
- host apps should not manipulate React roots directly.

## 12.2 Second priority: structured Gateway params

Current TSS integration uses:

```javascript
parameter: "database=ebi&collectionId=..."
```

A better API would preserve backwards compatibility and add something like:

```typescript
apiParams?: Record<string, string | number | boolean>
```

or typed Gateway params.

## 12.3 Larger RFC: supported headless TSS client

Potential future API:

```typescript
import {
    createTerminologyClient
} from "@ts4nfdi/terminology-service-suite/client";

const client = createTerminologyClient({
    api: gatewayBase
});

const entity = await client.getEntity({
    iri,
    ontologyId,
    params: {
        database: "ebi"
    },
    signal
});
```

This is not a blocker for the current refactor.

---

# 13. AGROVOC and heterogeneous backends

Historically AGROVOC was kept native because it is backed by Skosmos.

The Gateway architecture suggests that backend differences should be hidden behind the OLS4 facade.

A key follow-up spike is therefore to verify something equivalent to:

```text
GET /api-gateway/ols4/api/v2/ontologies/agrovoc/entities
    ?iri=<AGROVOC IRI>
    &database=agrovoc
```

If this works correctly with the TSS 7.1 widget contract:

1. change the AGROVOC matcher from native to TSS,
2. remove the plugin assumption that Skosmos requires a custom resolver,
3. delete more non-OLS logic from `GatewayMetadataResolver`.

Do not make the switch solely from architecture assumptions; perform a live contract test.

### Live contract status (2026-08-10)

The public Gateway accepts browser CORS requests for both checks below.

- EDAM succeeds: `GET /ols4/api/v2/ontologies/edam/entities` with
  `iri=http://edamontology.org/format_2332&database=ebi` returns one OLS4 v2
  entity, including `ontologyId: "edam"`. The supplied configuration therefore
  uses `frontend.gateway.mode = "direct"` for deterministic TSS-backed EDAM
  annotations.
- AGROVOC does **not** yet satisfy the same contract: `GET
  /ols4/api/v2/ontologies/agrovoc/entities` with
  `iri=http://aims.fao.org/aos/agrovoc/c_4826&database=agrovoc` returns HTTP
  200 but an empty `elements` list. Keep AGROVOC on the native detail path
  until the Gateway returns the selected concept through its OLS4 facade.

---

# 14. FAIRagro Data Generation annotation after `/entitysets`

There is one subtle open issue.

The entity-set response knows:

```text
provider
terminology
entity URI
label
definition
```

but normal RDMO persistence primarily keeps:

```text
Value.external_id = entity URI
Value.text        = label
```

Therefore, after selection, the annotation subsystem may no longer know the entity-set's original `provider` and `terminology` unless it can derive or recover them.

For this reason the safe migration state discussed was:

```text
FAIRagro Data Generation matcher
presentation = native
```

until deterministic Gateway/TSS context is available.

Possible future solutions:

### Option A — browser/entity-set lookup

Given the selected entity IRI, lookup the entity in the configured entity set and recover:

```text
provider
terminology
```

Then build TSS Gateway context.

### Option B — backend descriptor lookup

During annotation descriptor generation, use a small source-neutral entity-set lookup to attach provenance.

This is acceptable if it stays narrowly focused on entity-set provenance and does not grow into another general metadata resolver.

### Option C — persist provenance in RDMO

Only consider this if there is a clean generic RDMO representation for it. Avoid plugin-specific persistence hacks.

The preferred architecture is likely A or B.

### Live entity-set provenance assessment (2026-08-10)

The active FAIRagro entity set
`fc45621d-7e40-47ce-9616-4133f0b54edf` currently contains 12 entities from
five source/terminology pairs. Representative public Gateway OLS4 v2 checks
give the following result:

| Entity-set provider | Terminology | Result through the Gateway OLS4 facade |
| --- | --- | --- |
| `tib` | `ncit` | Works: `NCIT_C180602` returns one deterministic entity. |
| `agrovoc` | `agrovoc` | Does not work: HTTP 200 with an empty `elements` list. |
| `agroportal` | `AFO` | Does not work: HTTP 500. |
| `agroportal` | `INRAETHES` | Does not work: HTTP 500. |
| `agroportal` | `NALT` | Does not work: HTTP 500. |

The public `GET /entitysets` endpoint itself returns HTTP 200, but its
response omits `Access-Control-Allow-Origin`. It therefore cannot currently
be fetched directly by an RDMO interview running on another origin. This
blocks Option A in direct browser mode, even though public OLS4 routes such as
EDAM expose CORS correctly.

The plugin now implements a narrowly scoped, project-authorized
**entity-set provenance endpoint**. Only on annotation click, it recovers the
selected entity's `provider` and `terminology` from the configured Gateway
entity set and returns a semantic browser descriptor. It does not normalize
terminology metadata, mutate RDMO values, or run during v2 page listing.

The browser uses TSS only when the recovered configured source has
`backend_type = "ols2"` (the current `tib`/`ncit` case). Other sources retain
the native entity-set definition and provenance view. `GatewayClient` caches
the immutable entity-set response for its configured normal cache lifetime;
the browser also caches a resolved value for the lifetime of its controller.
Once the Gateway adds CORS support for `/entitysets`, this temporary click-time
adapter can be replaced by the direct browser lookup described in Option A.

---

# 15. Collections

TSS currently does not provide an obvious equivalent rich collection-info widget.

Collection annotations may therefore stay native.

If richer collection details are needed, use a **tiny source-neutral Gateway resource client** for collections.

Do not recreate a universal metadata resolver just to support collections.

---

# 16. Current implementation status — Codex must verify locally

The following items were the implementation direction at the end of the conversation and may already be present in the user's local checkout.

Codex should inspect the local tree and mark each item as present / partial / missing.

## 16.1 Expected to be present or partially present

- [x] Annotation API v2 domain descriptor types.
- [x] `/annotations/v2/` list route.
- [x] v2 listing does not resolve Gateway metadata.
- [x] `GatewayContext` / presentation policy included in v2 payloads.
- [x] browser-safe Gateway param allowlist.
- [x] `PluginAnnotationApi.listV2(...)`.
- [x] `AnnotationDetailCoordinator`.
- [x] `InterviewAnnotationController` accepts separated `annotations` and `details` dependencies.
- [x] browser composition uses v2 list discovery.
- [x] TSS-capable descriptors bypass `api.detail()`.
- [x] incomplete/native annotations fall back to the detail API.
- [x] explicit direct/proxy browser Gateway mode; the supplied configuration uses direct mode for public TSS descriptors.
- [x] browser constructs TSS props from semantic descriptors.
- [x] presentation-only TSS details render directly in the annotation drawer.
- [x] generic `TS4NFDIEntitySetProvider`.
- [x] `ts4nfdi_entitysets` provider key points to the entity-set provider.
- [x] FAIRagro Data Generation configured with entity-set ID `fc45621d-7e40-47ce-9616-4133f0b54edf`.
- [x] Entity-set click-time provenance endpoint; compatible `ols2` entries use TSS while other entries remain native.
- [x] Provider-backed collection and collection-terminology matchers can use a bounded click-time native-resource detail endpoint.
- [x] old semantic-option mapping/projection runtime removed.
- [x] old FAIRagro CSV/semantic JSON manifest is no longer a runtime dependency; the CSV is retained only as archived curator material.
- [x] FAIRagro Data Generation matcher stays native until provenance is deterministic.

## 16.2 Verify TSS version

Check:

```text
rdmo_ts4nfdi/vendor/terminology_service_suite.json
```

Verified target:

```text
7.1.0 (vendored in the current checkout)
```

Do not assume this upgrade happened merely because the browser code targets it.

## 16.3 Verify no accidental old dependencies remain

Suggested searches:

```bash
rg "SemanticOption|SemanticTarget|SemanticOptionSet"
rg "mapping_set_id|mapping_set_version"
rg "option_external_id|value_projection"
rg "PackageSemanticOptionRegistry"
rg "SemanticAnnotationTargetResolver"
rg "GatewayMetadataResolver"
rg "api\.detail|\.detail\("
rg "annotations/v2|listV2"
rg "entitysets|TS4NFDIEntitySetProvider"
```

`GatewayMetadataResolver` and `api.detail()` are expected to remain temporarily during the migration. The point of the search is to understand where they are still required.

---

# 17. Tests that should exist

## Backend

Important invariants:

```text
v1 remains compatible while migration is in progress
v2 api_version == "2"
v2 listing causes zero Gateway metadata resolution
v2 descriptor contains deterministic Gateway context for TSS entities
no API token reaches frontend config or descriptor
provider selection/permissions remain unchanged
entity-set provider stores entity URI directly
```

Tests should cover:

- v2 descriptor serialization,
- source/database/ontology context,
- no metadata resolver call from v2 list,
- private Gateway params filtered,
- direct entity-set option identity,
- entity-set localized labels,
- entity-set missing-ID/config failure,
- entity-set malformed item handling,
- normal RDMO providers unchanged.

## Browser

Tests should cover:

```text
controller refresh uses annotation-list dependency
controller open uses detail coordinator
TSS descriptor avoids server detail request
native descriptor uses server detail fallback
abort/stale request handling remains correct
direct Gateway base construction
proxy Gateway base construction
unsafe TSS parameters rejected
entity-info props
metadata props
ontology-info props
presentation cleanup
```

## Live/contract checks

Eventually add or retain smoke checks for:

```text
EDAM entity via Gateway OLS4
EDAM ontology
FAIRagro collectionId
AGROVOC entity via Gateway OLS4 facade
/entitysets
browser CORS in direct mode
TSS 7.1 against real Gateway
```

---

# 18. Recommended next implementation steps

## Step 1 — reconcile this handover with local code

Before editing:

```bash
git status
git log -n 10 --oneline
rg "TS4NFDIEntitySetProvider|AnnotationDetailCoordinator|listV2|GatewayContext"
```

Then compare local implementation with the checklists above.

Do not reapply conversation patches if equivalent changes are already in the checkout.

## Step 2 — finish and harden `/entitysets`

Verify the generic provider against the actual deployed endpoint response.

Check especially:

- top-level payload shape,
- entity-set lookup,
- localized labels,
- `definition` shape,
- provider naming,
- terminology naming,
- behavior when entity set is missing,
- whether pagination/versioning will appear later,
- whether returning all entities is appropriate.

Add a Gateway contract test/fixture for the actual response.

## Step 3 — make TSS-backed v2 path the normal path for deterministic descriptors

Start with the easiest matcher:

```text
EDAM
```

For EDAM:

```text
annotation v2
    ↓
gateway_context:
    ontology_id = edam
    database = ebi
    ↓
browser
    ↓
TSS EntityInfo / Metadata
    ↓
Gateway directly
```

Definition of done:

```text
click EDAM annotation in direct mode
→ no RDMO detail HTTP request
→ TSS requests Gateway
→ rich terminology detail renders
```

## Step 4 — live AGROVOC OLS4/TSS spike

Test the real Gateway + TSS contract.

If successful, move the AGROVOC matcher to TSS and remove the obsolete Skosmos-specific annotation-resolution assumptions.

## Step 5 — solve entity-set provenance for Data Generation

Decide how selected FAIRagro entity IRIs recover:

```text
database/provider
ontology/terminology
```

Prefer a minimal entity-set-specific solution.

Once deterministic provenance exists, Data Generation can also become TSS-backed.

## Step 6 — simplify native annotations (in progress)

Native detail should become descriptor-oriented:

- label,
- IRI,
- source,
- terminology,
- status/mapping info only where still genuinely applicable.

Avoid Gateway metadata calls unless a native feature actually needs them.

Collections can remain native.

The first bounded native path now exists. A matcher with
`provider_resource_detail = true` marks its v2 descriptor and the browser
calls `annotations/v2/<value_id>/provider-resource/` only when opened. The
adapter uses the same cached provider endpoint as the matching OptionSet and
selects the persisted resource identifier; it does not call the generic
`GatewayMetadataResolver`. The example collection matcher and both FAIRagro
collection-terminology matchers use this policy. Concept matchers such as
AGROVOC and broad keyword search remain on the legacy detail path because they
still need definitions or dynamically resolved source/terminology context.

## Step 7 — delete old backend detail metadata infrastructure

Once all TSS-backed matchers no longer depend on server detail resolution, remove:

```text
AnnotationDetailView
detail serializer/route
AnnotationService.detail()
GatewayMetadataResolver
ResolvedMetadata
AnnotationDetail
server-side TSS presentation materialization
```

Keep the Gateway proxy independently if `proxy` mode is still supported.

Do not tie proxy removal to detail-resolver removal.

## Step 8 — decide long-term proxy policy

Keep proxy mode if needed for:

- server tokens,
- authenticated/private resources,
- CORS restrictions,
- deployment network constraints.

Otherwise deprecate it later.

Direct mode should remain the simplest public-resource path.

---

# 19. Definition of done for the refactor

```text
[ ] v2 annotation discovery does not call Gateway metadata APIs
[ ] TSS-backed annotation click in direct mode makes no RDMO detail API request
[ ] TSS talks directly to Gateway for rich terminology metadata
[ ] plugin has no OLS-vs-Skosmos normalization layer for TSS-backed annotations
[ ] entity annotations always have deterministic ontology/artefact context
[ ] no global /entities normal fallback
[ ] no search-by-label normal metadata fallback
[ ] server credentials are never exposed to browser config
[ ] direct and proxy transport are explicit
[ ] normal RDMO dynamic providers continue to work
[ ] FAIRagro Data Generation uses Gateway /entitysets
[ ] plugin-owned CSV/semantic mapping/projection system is gone
[ ] collections still work through a small native path
[ ] old detail endpoint can be deleted without changing TSS browser behavior
[ ] TSS vendor version is intentionally pinned and verified
```

---

# 20. Architectural guardrails for future Codex work

1. **Do not move the old Python metadata resolver into JavaScript.**
2. **Do not duplicate TSS's OLS model normalization.**
3. **Do not expose Gateway API tokens to the browser.**
4. **Do not break RDMO's native dynamic OptionSet provider flow.**
5. **Do not add FAIRagro-specific logic to the generic entity-set provider unless the Gateway contract truly requires it.**
6. **Do not use search-by-label as the normal identity-resolution mechanism.**
7. **Require deterministic ontology/artefact context for TSS entity rendering.**
8. **Keep direct and proxy transport separate from presentation semantics.**
9. **Treat collection support as a small special case, not justification for a universal metadata layer.**
10. **Prefer deleting plugin code when TSS/Gateway already owns the responsibility.**

---

# 21. Short version for Codex

```text
1. Keep native RDMO OptionSet providers server-side.

2. FAIRagro Data Generation:
   replace plugin CSV/semantic mapping/projection with Gateway /entitysets.
   Store selected entity URI directly in Value.external_id.

3. Annotation backend:
   return v2 semantic descriptors only.
   No terminology metadata HTTP calls during annotation discovery.

4. Browser:
   use AnnotationDetailCoordinator.
   Complete TSS descriptors go directly to TSS.
   Native/incomplete descriptors temporarily fall back to old detail API.

5. TSS:
   fetch and render rich entity/ontology metadata.

6. Gateway:
   own backend-specific OLS/Skosmos translation.

7. direct mode:
   TSS → public Gateway.

8. proxy mode:
   TSS → RDMO proxy → Gateway when credentials/network policy require it.

9. Migrate EDAM first, then spike AGROVOC OLS4.

10. Once TSS-backed annotations no longer use server detail resolution,
    delete GatewayMetadataResolver and the old detail infrastructure.
```

---

# 22. First instruction to the Codex agent

```text
Inspect the local rdmo-plugins-ts4nfdi checkout and compare it against
RDMO_TS4NFDI_CODEX_HANDOVER.md. Do not modify code yet.

Report:
1. which "current implementation status" checklist items are present,
2. which are partial or missing,
3. the current TSS vendored version,
4. remaining references to the old semantic-option/value-projection system,
5. which annotation matchers still depend on server-side GatewayMetadataResolver,
6. whether EDAM can already use the direct TSS v2 path end-to-end,
7. the smallest next implementation commit you recommend.

Use the local source code as the source of truth when it differs from this handover.
```
