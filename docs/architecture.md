# Plugin architecture

The plugin is a working annotation prototype with replaceable integration
boundaries. Its own application and domain layers do not depend on the current
RDMO React implementation or on a particular TS4NFDI widget.

## Dependency direction

```text
RDMO API views
      |
      v
AnnotationService  <--- plugin-owned domain models
   /       |        \
  v        v         v
RDMO     target     metadata resolver
host     resolver       |
adapter                  v
                    TS4NFDI Gateway

AnnotationService
      |
      v
presentation registry
   /             \
native        TSS descriptor
```

The production dependencies are assembled in `rdmo_ts4nfdi/composition.py`.
Tests can replace every adapter without importing RDMO or making an HTTP
request.

Deployments can replace the production classes with the `TS4NFDI_ADAPTERS`
Django setting. It accepts dotted paths for `interview_host`, `gateway`,
`entityset_provenance`, `provider_resource_detail`, `metadata_resolver`, and `presentation`. Unknown keys
fail fast. The default classes remain explicit in the composition root.

## Backend boundaries

### Domain

`rdmo_ts4nfdi.domain` contains serialisable annotation, occurrence, matcher,
metadata, and presentation models. It imports neither Django/RDMO nor Gateway
code.

### Application

`AnnotationService` provides the two use cases exposed by the plugin API:

- list annotations for the visible interview page;
- resolve one selected value and choose its presentation.

It communicates through four small protocols:

- `InterviewHost`;
- `TargetResolver`;
- `MetadataResolver`;
- `PresentationAdapter`.

The target resolver distinguishes the stored RDMO answer identity from the
external terminology resource which annotates it. Terminology providers return
the selected resource IRI directly, so provider selections resolve to
themselves.

### RDMO adapter

`RDMOInterviewHost` is the only backend annotation component that traverses
RDMO projects, catalog questions, question sets, conditions, and values. It
turns those models into occurrence-aware `InterviewAnswer` instances. It does
not decide whether a selected RDMO option URI is itself a terminology
resource.

The public dynamic option-provider class paths remain unchanged because RDMO
deployments persist them in settings. Their external HTTP operation is
delegated to `GatewayProviderClient`.

`TS4NFDIEntitySetProvider` exposes a configured Gateway `/entitysets` resource
as RDMO options. It uses every entity's URI as the provider option ID, so the
normal RDMO provider flow persists the terminology IRI without a plugin signal
or value projection. [`semantic-option-workflow.md`](semantic-option-workflow.md)
records the active upstream-curation workflow and the status of the archived
FAIRagro CSV; no semantic manifest is shipped or read at runtime.

### Browser-side inline context resolution

Dynamic RDMO providers persist a selected label and external identifier, but
not the provider `help` markup which contained the source, terminology, and
short-form breadcrumb. Annotation API v2 deliberately does not reconstruct
that metadata in Django. A broad multi-source entity matcher can instead expose
`context_resolution = { adapter = "gateway-search" }` in its public descriptor.

`AnnotationContextCoordinator` renders the stored fallback first and then asks
the browser `BrowserGatewaySearchClient` for the public `/search` response. It
keeps only results whose IRI exactly matches the stored identifier. One unique
source/terminology context enriches the in-memory annotation and triggers an
inline rerender; missing or conflicting contexts leave the fallback unchanged.
Requests and in-flight promises are deduplicated by label and IRI for the
controller lifetime.

In direct mode this request goes from the browser to the Gateway. Proxy mode
uses a narrowly scoped, project-authorized `/gateway/search` endpoint and the
normal cached `GatewayClient`. This compatibility route accepts only a bounded
`query` value. Neither path mutates RDMO values, embeds provenance in their
text, or makes Gateway metadata I/O part of the v2 page-list request.

### Entity-set provenance on annotation click

RDMO stores an entity-set choice as its label and entity IRI, whereas the
Gateway entity-set record also carries its provider and terminology. The v2
page-list response deliberately does not recover that context: it marks an
entity-set annotation with `entityset_provenance: true` and performs no Gateway
metadata request.

Only when the user opens such an annotation does the browser call the
project-authorized `annotations/v2/<value_id>/entityset-provenance/` endpoint.
The small `GatewayEntitySetProvenanceResolver` retrieves the configured
Gateway entity set through the normal cached `GatewayClient`, finds the exact
selected IRI, and returns only the upstream entity-set definition, provider,
terminology, and configured source context. It never mutates `Value`, searches
by label, or normalizes a terminology response.

When that recovered source is configured as `backend_type = "ols2"`, the
browser constructs a normal TSS `entity-info` descriptor and lets TSS call the
Gateway. Other backends retain the native drawer, showing the entity-set
definition and provenance. This is intentionally a narrow temporary adapter:
the public Gateway `/entitysets` route currently lacks browser CORS headers;
when that is corrected upstream, it can be replaced by a direct browser lookup.

### Provider-resource detail on annotation click

Collections and collection-provided terminologies are not TSS entity widgets,
but users still need their descriptions. A matcher can therefore explicitly set
`provider_resource_detail = true`. Its v2 descriptor remains metadata-free;
only when opened does the browser call the project-authorized
`annotations/v2/<value_id>/provider-resource/` endpoint.

`GatewayProviderResourceDetailResolver` reuses the exact defaults-expanded
provider configuration that populated the RDMO OptionSet. It uses the cached
`GatewayClient`, retrieves the bounded provider response, and selects the
stored resource identifier. The response contains only the resource's label,
description, version, source, and terminology context for the native drawer.
For a Gateway `TerminologyCollectionDto`, it also exposes a typed, display-safe
collection card model: UUID, permalink, visibility, creator, collaborators,
and terminology memberships. The browser presents that model in the native
drawer; it does not embed the Service Portal or issue one request per member
terminology. It does not search by label or normalize terminology-concept
metadata.

This currently serves the example collection matcher and both FAIRagro
collection-terminology matchers. The browser caches each resolved detail for
the lifetime of its interview controller. Other native concept matchers retain
the legacy detail fallback because their definitions or dynamic provenance are
still supplied by `GatewayMetadataResolver`.

### TS4NFDI adapters

`GatewayClient` owns the authenticated, cached, allowlisted Gateway transport
used by dynamic providers, native annotation details, and the optional browser
proxy. A complete TSS v2 descriptor instead lets the browser call the public
Gateway directly; it does not use this client for terminology metadata.

`GatewayMetadataResolver` owns the remaining concept-detail fallback logic:
OLS and non-OLS lookups, definitions, synonyms, and dynamic search context.
Provider-backed collection/terminology records use the separate bounded
provider-resource adapter above. Neither resolver is a dependency of the
TSS-backed v2 path; TSS owns OLS model normalization and rich terminology
rendering there.

### Presentation registry

The presentation registry maps the configured adapter name to a descriptor.
The built-in choices are:

- `native`, which needs no external widget;
- `tss`, for which the browser constructs public Terminology Service Suite
  component props from a semantic descriptor.

Other adapter names pass their matcher options through as a browser descriptor.
A deployment can register the corresponding ES module under
`frontend.presentation_adapters` without adding a Python adapter. Adding or
switching a presentation adapter does not change the application service.

Matcher configuration uses a nested `presentation` table. This keeps RDMO
resource matching (`question_uri`, `attribute_uri`, and `optionset_uri`)
separate from renderer selection and renderer-specific options. The previous
top-level widget keys are intentionally not supported by this clean-cut
architecture.

## Browser boundaries

The browser entry point in
`rdmo_ts4nfdi/static/rdmo_ts4nfdi/js/interview/main.js` is a composition root.
It connects:

- `RDMOTemplateInterviewHost`;
- `PluginAnnotationApi`;
- `AnnotationContextCoordinator` and `BrowserGatewaySearchClient`;
- `InterviewAnnotationController`;
- `NativeInlineAnnotationRenderer`;
- `NativeAnnotationDrawer`;
- `TssPresentationAdapter`.

Only `RDMOTemplateInterviewHost` knows current RDMO DOM selectors or detects
React navigation with mutation observers. It returns ordinary mount elements
and immutable annotation payloads to the controller. The controller does not
read or mutate the RDMO Redux store.

The TSS adapter loads the pinned external bundle after a user opens an
annotation. A presentation-only v2 descriptor mounts its widget directly in
the plugin drawer. In direct mode, it calls the public Gateway with the
browser-safe descriptor context; in proxy mode, it uses the authenticated RDMO
proxy. Native provider-resource descriptors and entity-set annotations use
their dedicated click-time endpoints instead of the legacy metadata resolver.
Other native or incomplete descriptors retain the legacy detail fallback. A
failure stays inside that adapter and the native details remain usable.

Deployment-defined presentation modules are loaded from Django staticfiles by
the browser composition root. They receive normalized plugin detail and mount
only into a plugin-owned element. The presentation registry owns their cleanup
lifecycle and contains module/render failures. The complete configuration and
JavaScript contract are documented in `docs/presentation-adapters.md`.

## Replacing the current RDMO integration

When RDMO exposes an official extension registry and interview slots, add a
host implementing the same browser responsibilities:

1. expose project and page context;
2. provide question-occurrence mount elements;
3. notify the controller about mount, update, and unmount lifecycle;
4. clear plugin-owned slot contents during cleanup.

Select that host in `main.js` through RDMO capability detection. No changes
should be required in the REST client, annotation controller, Gateway adapters,
or presentation adapters. Once supported RDMO versions all provide the public
extension API, delete the template host and the question-help marker.

The related upstream proposals and compatibility criteria are in
`docs/rdmo-upstream-feature-requests.md`.
