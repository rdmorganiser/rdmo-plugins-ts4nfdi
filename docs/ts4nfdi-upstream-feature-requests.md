# Upstream Terminology Service Suite feature requests

These copy-ready drafts were checked against TSS 7.1.0 at commit
`0a1a0f485c0b16b4f56cfc305900975261f4c7c8`.

## Plain-JavaScript widgets need a cleanup handle

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> Plain-JavaScript widget factories should return a handle with `destroy()`

### Problem

The plain-JavaScript `create*` functions create a React root and render into a
host element, but they return nothing. A dialog, drawer, or single-page
application cannot ask TSS to unmount the widget when that element is removed.

For example, `createEntityInfo()` and `createMetadata()` store roots in a
private `WeakMap`. The host cannot reach those roots or run React cleanup.

### Proposed API

```javascript
const widget = window.ts4nfdiWidgets.createEntityInfo(props, container);

// Later, when the host removes the view:
widget.destroy();
```

### Acceptance criteria

- Every public `create*` factory returns a lifecycle handle.
- `destroy()` unmounts the React root and removes the internal root entry.
- Calling `destroy()` more than once is safe.
- Existing calls that ignore the return value keep working.
- The behavior is documented and covered by a plain-JavaScript test.

This would let any non-React host clean up TSS widgets safely without knowing
how TSS manages React internally.

## Render metadata that the host has already resolved

**Repository:**
[ts4nfdi/terminology-service-suite](https://github.com/ts4nfdi/terminology-service-suite/issues)

**Suggested title:**

> Add a plain-JavaScript widget for pre-resolved entity metadata

### Problem

Some host applications already have the selected entity's label, IRI,
description, synonyms, ontology ID, and short form. They want to display that
data with the TSS design, but `MetadataWidget` always fetches the entity before
rendering it.

Making another API request is unnecessary and can fail when the host's data
came from a source that is not fully available through the OLS routes.

### Proposed API

A single composite factory would be easier for hosts than several independent
React roots:

```javascript
const widget = window.ts4nfdiWidgets.createResolvedEntityMetadata(
  {
    label: "XML",
    iri: "http://edamontology.org/format_2332",
    ontologyId: "edam",
    shortForm: "format_2332",
    descriptions: ["Extensible Markup Language format."],
    synonyms: ["eXtensible Markup Language"]
  },
  container
);
```

The name and exact data type are open for discussion. The important contract
is that the widget renders the supplied data and makes no terminology or
Gateway request.

### Acceptance criteria

- Render a coherent title, breadcrumb, IRI/link, description, and synonyms
  from supplied values.
- Make no network request.
- Provide a stable plain-JavaScript API.
- Return the same lifecycle handle with `destroy()` proposed above.
- Export the matching React presentation component(s) publicly for React hosts.
- Handle missing optional fields without an error.

### Source check

`MetadataWidget` currently owns its entity `useQuery`. `IriWidget` is
fetch-free, and `BreadcrumbPresentation` is publicly exported, but
`TitlePresentation`, `DescriptionPresentation`, and
`AlternativeNameTabPresentation` are not public React package exports. A
composite presentation component would avoid asking a plain-JavaScript host to
mount several independent roots.
