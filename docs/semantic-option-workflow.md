# Semantic option curation and compilation

## Status

The runtime parts of this workflow are implemented:

- a versioned semantic option manifest;
- an RDMO option provider backed by that manifest;
- stable RDMO answer identities;
- zero, one, or several terminology targets for each option; and
- terminology annotations for the mapped targets.

The CSV compiler and the composition-specific sidebar are not implemented
yet. Until the compiler exists, changes to the curator CSV must also be
applied manually to the JSON manifest.

This document defines the intended curator contract so that the compiler can
be implemented without changing the spreadsheet again.

## Why the CSV is compiled

The CSV is the collaboration format for FAIRagro curators. It is convenient
for adding labels, candidate concepts, review notes, and mappings. It is not
loaded directly by the running plugin.

The plugin loads a normalized JSON manifest instead. Compilation provides a
place to:

- validate stable option identifiers and IRIs;
- reject incomplete concept mappings;
- resolve source names to configured TS4NFDI Gateway sources;
- validate mapping relations and review states;
- group repeated rows into one option with several targets;
- preserve explicit component order;
- produce deterministic output suitable for Git review; and
- record which CSV version produced the deployed manifest.

The relevant artifacts are:

- curator input:
  [`FAIRagro Options - data_generation.csv`](FAIRagro%20Options%20-%20data_generation.csv);
- deployed manifest:
  [`fairagro_data_generation.json`](../rdmo_ts4nfdi/data/semantic_option_sets/fairagro_data_generation.json);
- source registry:
  [`ts4nfdi_provider.toml`](../ts4nfdi_provider.toml); and
- example RDMO catalog:
  [`rdmo-plugins-ts4nfdi-example-catalog.xml`](../xml/rdmo-plugins-ts4nfdi-example-catalog.xml).

## CSV contract

The CSV is an extension of the original FAIRagro working file, not a
replacement schema. Its title row, original six columns, existing values,
`/` placeholders, and existing rows are retained. Compiler-specific columns
are appended after `Comment`.

Changing the name or meaning of an original column requires agreement with
the FAIRagro curators first.

### Original columns

| Existing column | Current use |
| --- | --- |
| `TermDE` | German target/concept label supplied by the curators. |
| `TermEN` | English target/concept label supplied by the curators. |
| `TerminologyConceptURI` | Target concept IRI. The existing `/` placeholder means that no target has been proposed. |
| `TerminologyLabel` | Existing human-readable terminology name. |
| `TerminologyProvider` | Existing human-readable terminology provider. |
| `Comment` | Existing free curator note. |

The compiler locates the header row by these column names and skips the
preceding question/title row.

### Appended columns

| Added column | Required | Purpose |
| --- | --- | --- |
| `OptionID` | yes | Stable key inside this mapping set. Never reuse it for a different meaning. |
| `OptionURI` | yes | Stable FAIRagro/RDMO option URI stored as the answer identity. |
| `OptionLabelDE` | recommended | German label of the FAIRagro option, which may differ from `TermDE`. |
| `OptionLabelEN` | yes | English label of the FAIRagro option, which may differ from `TermEN`. |
| `Selectable` | yes | `true` for an active choice; `false` preserves a retired option without offering it for new answers. |
| `TargetID` | with a target | Stable key for one mapping target within the option. |
| `TerminologyID` | with a target | Machine-readable terminology ID, for example `agrovoc` or `INRAETHES`. |
| `SourceKey` | with a target | Key from `[sources.*]` in `ts4nfdi_provider.toml`, for example `agrovoc`, `agroportal`, or `tib`. |
| `MappingRelation` | with a target | One of `exact`, `close`, `broad`, `narrow`, `related`, or `component`. |
| `CurationStatus` | with a target | One of `draft`, `reviewed`, or `deprecated`. |
| `CompositionID` | for a component | Stable group identifier shared by all components of one composition. |
| `CompositionOperator` | for a component | How the group is interpreted: initially `compound`, `intersection`, `union`, or `ordered_list`. |
| `ComponentOrder` | for a component | Positive integer used for deterministic display. |
| `ComponentRole` | optional | Curator-facing role such as `head`, `modifier`, `method`, or `context`. It is not an ontology property. |

The original CSV is a work-in-progress mapping sheet and does not currently
contain every option from the FAIRagro RDMO OptionSet. The compiler must
therefore merge it with an authoritative option inventory, initially the
existing semantic manifest or an exported FAIRagro RDMO OptionSet. An omitted
CSV row does not delete an existing option.

An option with several terminology targets occupies one row per target. The
appended option columns are repeated and must be identical on all of its
rows. Existing original cells are left as supplied by the curators.

### Stable identifiers

After an option has been used in RDMO, do not change its `OptionURI`.
Existing provider-backed answers keep this URI in `Value.external_id`.
Changing a label or mapping does not invalidate the answer.

If an option is retired, keep its row and set `Selectable=false`. Deleting or
reusing its URI could make existing answers impossible to interpret.

`TargetID` and `CompositionID` are internal stable keys. They should use
lowercase ASCII letters, digits, and hyphens. A target IRI may be corrected
without changing `TargetID` while the mapping is still a draft; such a
change must be visible in review.

### Simple and multiple mappings

A simple mapping has one target row and empty composition columns.

Several target rows with empty composition columns represent several
independent candidate or equivalent annotations. They do not imply that the
concepts are combined. The configured `MappingRelation` states how each
target relates to the FAIRagro option.

Use `exact` sparingly. Use `close` where the practical meanings are similar
but not guaranteed to be interchangeable, and `related` where the target
only provides useful context.

## Composed options

### What the plugin stores

A composed option remains one RDMO answer with one stable `OptionURI`.
Its component concepts are annotation targets, not additional answers. This
means that exports can contain:

1. the selected FAIRagro option URI;
2. its visible label;
3. the composition operator; and
4. the ordered component IRIs and their curation metadata.

The plugin does not mint a new concept in an external ontology. Publishing a
new formal concept requires an agreed persistent IRI, definitions, governance,
and publication in the relevant terminology.

### Do not use spreadsheet row order as semantics

Rows are frequently sorted, filtered, copied, or exported by spreadsheet
software. Their physical order must therefore have no semantic effect.

Every component row uses the same `CompositionID` and
`CompositionOperator`, plus an explicit `ComponentOrder`. The compiler
rejects missing or duplicate orders. For a logical intersection or union the
order is only presentational; for a linguistic compound it controls the
display order.

### Example: strawberry milk

“Strawberry milk” would normally use concepts for **strawberry** and **milk**,
not **straw** and **milk**. The spelling of a word is not a semantic
decomposition.

The reduced example below omits the repeated source and terminology columns:

| `OptionID` | `OptionLabelEN` | `TargetID` | `TermEN` | `MappingRelation` | `CompositionID` | `CompositionOperator` | `ComponentOrder` | `ComponentRole` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `strawberry_milk` | Strawberry milk | `strawberry` | strawberry | `component` | `strawberry-milk` | `compound` | `1` | `modifier` |
| `strawberry_milk` | Strawberry milk | `milk` | milk | `component` | `strawberry-milk` | `compound` | `2` | `head` |

`compound` is deliberately a curation and display construct. It says that
the option is explained through these components; it does not claim a formal
logical equivalence.

In particular, strawberry milk is not normally the OWL intersection
“Strawberry and Milk”: that expression describes things which are members of
both classes. A formal description might instead require a domain property
such as “milk that has flavour or ingredient strawberry”. The CSV contract
does not attempt to invent such properties.

SKOS ordered collections can preserve an ordered list of concepts, but a
SKOS collection is distinct from a SKOS concept and does not by itself define
a new combined concept. OWL supports intersection and union class
expressions, but those operators should only be emitted when a domain expert
confirms that the formal class semantics are intended:

- [SKOS Reference: Concept Collections](https://www.w3.org/TR/skos-reference/#collections)
- [OWL 2 Primer: class intersections and unions](https://www.w3.org/TR/owl-primer/#Advanced_Class_Relationships)

The SKOS Reference is a W3C Recommendation. The OWL Primer is an informative
introduction to the formal OWL constructs; the relevant section is “Advanced
Class Relationships”.

### Initial operator meanings

| Operator | Meaning in this plugin |
| --- | --- |
| `compound` | Ordered components explain one curated compound label; no formal logical claim. Recommended for “strawberry milk”. |
| `ordered_list` | Ordered concepts are grouped for presentation, without claiming that they define a new concept. |
| `intersection` | Candidate “all of” semantics. Must remain `draft` until reviewed by a domain/ontology expert. |
| `union` | Candidate “any of” semantics. Must remain `draft` until reviewed by a domain/ontology expert. |

The first compiler should preserve all four values but must not generate OWL
from them. Formal ontology serialization is a separate, explicitly reviewed
feature.

## Proposed sidebar presentation

The current annotation API already supports multiple targets for one selected
answer. A composition-aware native sidebar can build on that payload:

- a **Combined meaning** tab shows the option label, operator, ordered
  components, mapping status, and curator-approved explanation;
- one tab per component shows its terminology, source, definition, synonyms,
  hierarchy, IRI, and Gateway/TSS details;
- independently mapped alternatives can use one target tab each without a
  “Combined meaning” claim; and
- unavailable Gateway details affect only the relevant component tab.

Tab order comes from `ComponentOrder`, never from an API response or CSV row
position. On narrow screens the tabs may be rendered as an accessible
accordion.

## Current manual update workflow

Until the compiler is implemented:

1. Update the curator CSV without renaming, reordering, or reinterpreting the
   original six columns.
2. Preserve the question/title row and all original cells, including existing
   `/` placeholders.
3. Preserve published `OptionID` and `OptionURI` values in the appended
   columns.
4. Add or update appended machine-readable fields for mapped rows.
5. Represent multiple independent mappings by repeating an option row with
   empty composition columns.
6. Represent a composition as repeated rows with
   `MappingRelation=component` and complete composition columns.
7. Apply the same changes manually to
   `fairagro_data_generation.json`.
8. Increment the manifest `version`.
9. Update its `source_sha256` to the SHA-256 hash of the curator CSV.
10. Run the plugin tests and review the CSV and JSON diff together.
11. Deploy and restart the Django processes so the package resource is
    reloaded.

The RDMO example catalog does not need to be re-imported when only labels,
mappings, curation status, or composition metadata changes. It needs a new
import only when the page/question structure, provider key, or OptionSet URI
changes.

## Target compiler workflow

The planned management command should make the manual JSON steps unnecessary:

```bash
python manage.py ts4nfdi_semantic_options compile \
    --set fairagro-data-generation \
    --input "docs/FAIRagro Options - data_generation.csv" \
    --base-manifest \
        "rdmo_ts4nfdi/data/semantic_option_sets/fairagro_data_generation.json" \
    --check
```

`--check` should validate and print a summary without writing. Without
`--check`, the command should atomically replace the package manifest.

The command should report at least:

- total, selectable, and retired options after merging the mapping CSV with
  the authoritative option inventory;
- mapped and unmapped options;
- target counts by source and curation status;
- options with several independent targets;
- composition groups and operators;
- added, removed, or changed stable identifiers;
- unknown Gateway source keys;
- invalid or non-HTTP concept IRIs; and
- the source SHA-256 stored in the generated manifest.

Compilation must be deterministic: running it twice with the same CSV
produces byte-identical JSON.

## Review and deployment checklist

Before accepting an updated CSV:

- [ ] The original title row, six columns, values, and placeholders are
      preserved.
- [ ] Every CSV mapping row has a stable appended option ID, URI, and English
      option label.
- [ ] Repeated rows have identical appended option columns.
- [ ] Retired mapped options remain present with `Selectable=false`.
- [ ] Every mapped target has an IRI, label, terminology, source, relation,
      and curation status.
- [ ] Every `source_key` exists in `ts4nfdi_provider.toml`.
- [ ] `exact` mappings have been explicitly reviewed.
- [ ] Component groups have one operator and unique consecutive orders.
- [ ] A compound is not accidentally represented as an OWL intersection.
- [ ] CSV and generated manifest changes are reviewed together.
- [ ] Existing answer URIs remain resolvable.
- [ ] Provider, annotation, and export tests pass.

## RDMO OptionSets and exports

A native static RDMO option does not need `Value.external_id`: its stable
identity is available through `Value.option.uri`. A provider-backed option
stores its returned ID in `Value.external_id`. The plugin supports both
paths.

A static RDMO OptionSet is therefore possible, but an RDMO option still has
only one own URI and no native fields for several terminology targets,
mapping relations, component order, or curation status. The semantic mapping
manifest remains useful even if FAIRagro later manages the option labels and
URIs in RDMO itself.

The recommended export model keeps these layers separate:

```text
selected option
  option URI: stable FAIRagro classification identity
  label: human-readable answer
  semantic mappings:
    relation/status
    composition metadata, when present
    one or more terminology concept IRIs
```

This preserves the original interview answer even when a draft terminology
mapping is later corrected.

The plugin implements this model as two optional RDMO project exports:

- `rdmo_ts4nfdi.exports.SemanticJSONExport`;
- `rdmo_ts4nfdi.exports.SemanticXMLExport`.

Both exports use the same application-layer payload. `answer_id` is the URI
actually selected and stored by RDMO; each annotation's `iri` is the direct or
mapped terminology concept. Mapped annotations also include
`mapping_set_id`, `mapping_set_version`, relation, and curation status. The
exports contain annotation summaries and do not issue one Gateway detail
request per concept. Registering the formats in `PROJECT_EXPORTS` is described
in the repository README. Use the RDMO-compatible internal keys
`ts-for-nfdi-json` and `ts-for-nfdi-xml`; RDMO 2.5.x does not accept digits in
the format segment of an export URL.
