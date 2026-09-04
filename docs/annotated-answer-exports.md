# Annotated answer exports

The plugin adds semantic context to RDMO answers without introducing a second
annotation database. RDMO remains the source of truth, and the plugin derives
annotations when it renders the answer view or creates an export.

## What is stored

RDMO stores the selected answer as a `Value`. Depending on the question and
provider, the relevant fields include:

- the answer text, from which RDMO provides the display label;
- its `value_type`;
- the selected static RDMO option, when applicable; and
- the provider identifier in `Value.external_id`.

TS4NFDI option providers use the terminology resource identifier as the dynamic
option ID. RDMO therefore persists that identifier in `Value.external_id`. It
can be an HTTP IRI, such as an EDAM concept or an ontology IRI, or a stable
provider-specific identifier such as `agrovoc`.

`AnnotationService` does **not** store annotation records, copy answers, or
modify `Value`. It holds the configured adapters and annotation matchers and
constructs immutable domain objects while processing a request. The RDMO host
may cache the values loaded for a project during that service instance, and the
browser may cache resolved detail for its controller lifetime. These are
temporary performance caches, not persistent annotation storage.

## How an annotation is derived

For each visible answer, the service performs the following steps:

1. `RDMOInterviewHost` reads the stored `Value.external_id` and the question
   occurrence.
2. The matcher registry requires the configured question URI, attribute URI,
   and OptionSet URI to match. An external identifier alone is not enough.
3. `AnnotationTargetResolver` turns an accepted stored identifier into an
   annotation candidate.
4. `AnnotationService` creates a transient `AnnotationSummary` and groups it by
   question occurrence.

The summary and its surrounding occurrence contain:

- the RDMO value and question IDs, set indexes, and collection index;
- the matcher ID and resource kind (`entity`, `ontology`, or `collection`);
- the displayed label and resource IRI;
- a badge label and short form, when available; and
- source, terminology, and provider answer identity.

The v2 page descriptor additionally carries presentation and public resolution
policies for the interactive annotation UI. Those UI policies are not persisted
with the RDMO answer and are not part of the semantic export annotation.

## Export data flow

`AnnotatedJSONExport`, `AnnotatedXMLExport`, and `AnnotatedPDFExport` all use
`RDMOAnnotatedAnswersBuilder`:

```text
RDMO project or snapshot
        |
        +--> condition-aware RDMO answer tree
        |
        +--> AnnotationService.list_page_v2()
                         |
                         v
              annotations keyed by Value.id
        |
        v
versioned annotated-answer payload
        |
        +--> JSON
        +--> XML
        `--> PDF
```

The builder uses RDMO's project wrapper and template helpers, so it includes the
same applicable, non-empty question occurrences as the normal answer tree. It
then asks `AnnotationService` for the matcher-qualified summaries on every
catalog page and associates them with answers by `Value.id`.

Before adding an annotation block, the builder verifies that the summary IRI is
still identical to the stored `Value.external_id`. This prevents stale or
unrelated metadata from being attached to an answer.

Export generation uses `list_page_v2()`, which builds descriptors from stored
answers and configuration without resolving terminology metadata. It therefore
does not call the TS4NFDI API Gateway. Optional metadata and provenance lookups
used when opening the interactive drawer are deliberately outside the export
path.

## Identifiers in the export

The annotated payload preserves three identities separately:

- `external_id` is the identifier stored on the RDMO value;
- `annotation` is present only when a configured matcher accepts that value and
  its IRI equals the stored external identifier; and
- `option` contains the URI and label of a static RDMO catalog option.

Consequently, an unmatched external identifier remains visible but is not
claimed as a semantic annotation. A static option URI, for example a local
RDMO vocabulary term, remains an option identifier. Values without either kind
of identifier are exported normally with no annotation block.

All three annotated formats originate from the same versioned payload. JSON
exposes the complete payload directly. XML represents the same hierarchy and
places repeated IDs on their containing value and question elements. PDF
presents the answer label followed by a visible semantic annotation containing
its kind, IRI, terminology, and source.

These exports are human- and machine-readable answer reports. They are not a
replacement for RDMO's archival project export and cannot be imported to
recreate a project.

## Links in normal answer views

The normal RDMO “View Answers” page and its answer PDF use the same
matcher-qualified page summaries to link stored HTTP(S) IRIs. The visible link
text remains the answer label; the IRI is the link target. This applies to
matched entities, ontologies, and collections regardless of whether RDMO
records the answer with `value_type="option"` or another value type.

Opaque provider identifiers, unsafe schemes, unmatched values, and values
without an external identifier remain plain text. Rendering these links also
does not persist any additional data or contact the Gateway.
