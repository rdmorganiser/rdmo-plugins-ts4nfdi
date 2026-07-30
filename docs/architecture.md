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
RDMO     semantic   metadata resolver
host     target         |
adapter  resolver       v
          |       TS4NFDI Gateway
          v
   semantic option registry

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
`metadata_resolver`, `presentation`, and `semantic_options`. Unknown keys fail
fast. The default classes remain explicit in the composition root.

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
external terminology resource which annotates it. Direct provider selections
resolve to themselves. A curated option can instead expand through a semantic
option set to zero, one, or several terminology targets.

### RDMO adapter

`RDMOInterviewHost` is the only backend annotation component that traverses
RDMO projects, catalog questions, question sets, conditions, and values. It
turns those models into occurrence-aware `InterviewAnswer` instances. It does
not decide whether a selected RDMO option URI is itself a terminology
resource.

The public dynamic option-provider class paths remain unchanged because RDMO
deployments persist them in settings. Their external HTTP operation is
delegated to `GatewayProviderClient`.

`PackageSemanticOptionRegistry` loads versioned, normalized mapping manifests.
The FAIRagro data-generation provider projects one such manifest into RDMO
options, while annotations use the same manifest to resolve selected option
URIs into target concepts. This keeps CSV/import concerns out of both the RDMO
adapter and the Gateway adapter.

### TS4NFDI adapters

`GatewayClient` owns the authenticated, cached, allowlisted Gateway transport
used by annotation details and the browser proxy.

`GatewayMetadataResolver` owns knowledge of current Gateway result fields. It
maps external payloads to plugin domain metadata. Neither RDMO nor the browser
renderer needs to understand raw Gateway response shapes.

### Presentation registry

The presentation registry maps the configured adapter name to a descriptor.
The built-in choices are:

- `native`, which needs no external widget;
- `tss`, which produces public Terminology Service Suite component props.

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
- `InterviewAnnotationController`;
- `NativeInlineAnnotationRenderer`;
- `NativeAnnotationDrawer`;
- `TssPresentationAdapter`.

Only `RDMOTemplateInterviewHost` knows current RDMO DOM selectors or detects
React navigation with mutation observers. It returns ordinary mount elements
and immutable annotation payloads to the controller. The controller does not
read or mutate the RDMO Redux store.

The TSS adapter is lazy. It loads the pinned external bundle only after the
user expands the interactive view. A failure stays inside that adapter and the
native annotation details remain usable.

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
