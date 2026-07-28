# TS4NFDI use cases in the RDMO interview

## Scope

This document describes potential uses of the TS4NFDI API Gateway and
Terminology Service Suite (TSS) in an RDMO interview. The primary reference is
the [NFDI DMP Template for FAIRagro](../../xml/dmp4nfdi_v1-0-0%20%281%29-fairagro.xml),
but the same integration patterns can be configured for other catalogs.

The goal is not to turn the interview into a general ontology browser. The
terminology integration should help a respondent:

1. find a suitable controlled term;
2. understand what that term means;
3. distinguish it from similarly named terms;
4. store a stable identifier together with the readable answer; and
5. inspect additional context without leaving the interview.

In this document, a **terminology** is a controlled vocabulary such as EDAM or
AGROVOC. A **semantic artefact** is a complete terminology, ontology,
classification, or similar resource. A **concept** or **entity** is one entry
in such a resource, for example the EDAM concept for PNG or the ENVO concept
for soil. Concepts should be identified by a stable HTTP IRI; their human
readable labels may change or be translated.

TS4NFDI provides two complementary integration layers:

- The **API Gateway** provides a common search and retrieval interface over
  several terminology services.
- The **TSS widgets** provide ready-made interfaces for autocomplete, entity
  information, ontology information, hierarchies, relations, and other
  terminology views.

The plugin can use either layer. A small API-driven annotation is often more
appropriate in the interview itself, while a TSS widget is useful for an
optional details view.

## Common interaction pattern

Most of the use cases below follow the same flow:

1. An RDMO option provider searches a deliberately restricted terminology or
   TS4NFDI collection.
2. Search results show the preferred label, terminology badge, and a short
   definition where available.
3. RDMO stores the label as the visible answer and the concept IRI as the
   value's `external_id`.
4. The plugin adds a compact annotation below the completed answer, for
   example `format · EDAM · PNG`.
5. “Terminology details” opens an on-demand drawer with selected information
   such as the definition, source, IRI, synonyms, or hierarchy.

The answer must remain usable if the external service is unavailable. The
stored label and IRI should therefore be shown without a Gateway request;
remote definitions and widgets are progressive enhancement.

Searches should normally be limited by ontology, terminology collection,
backend, entity type, or IRI prefix. An unrestricted federated search can
produce many duplicates and several legitimate meanings of the same word. For
example, “soil” can refer to a subject in AGROVOC, an environmental material
in ENVO, or a sample/checklist context in MIxS. Source badges and definitions
are essential when several such results are valid.

## Overview

| Use case | FAIRagro catalog location | Terminology scope | Readiness |
| --- | --- | --- | --- |
| Data-format selection | Technical Data Description | EDAM formats | Implemented |
| Metadata-standard selection | Data Documentation | FAIRagro TS collection | Implemented |
| Dataset topics and keywords | Project Data Description / Data Documentation | AGROVOC | Catalog extension |
| Environmental and sample context | Project Data Description | ENVO and MIxS | Catalog extension |
| Plant traits and observed variables | Project Data Description | Plant Trait Ontology | Catalog extension |
| Experiment and data-creation methods | Project Data Description | PPEO and AGROVOC | Provider/catalog extension |
| Processing methods and operations | Technical Data Description | EDAM operations or domain terminology | Provider/catalog extension |
| Software, tools, and instruments | Data Documentation | SWO, OBI, CHMO, or a curated collection | Optional |
| Licenses and terms of use | Sharing | SPDX or another license vocabulary | Optional; static options may be preferable |

## UC-1: Data-format selection and explanation

**Catalog question:** “Which data formats arise in your project?”

**Question URI:**

`https://rdmo.fairagro.net/terms/questions/dmp4nfdi/v1-0-0/DMP/Dataset/Distribution/rdadmp_format`

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/format`

This is the most mature use case in the plugin. The option provider searches
EDAM and restricts results to format concepts. A respondent can enter a
familiar name such as “PNG”, “xlsx”, or “XML” and select a concept carrying a
stable EDAM IRI.

The search result should display:

- the preferred format name;
- an `EDAM` badge;
- the EDAM identifier or short form; and
- a short description, if supplied by EDAM.

The annotation details can show the definition, synonyms, IRI, broader format
category, and the source ontology. A full ontology graph is unlikely to help
most respondents and should not be opened by default.

This use case improves the consistency of format names and distinguishes
formats with similar labels. The RDMO question remains creatable so that users
can enter a format that is not yet represented in EDAM. Such free-text values
should remain valid but cannot receive a semantic annotation unless they are
later matched to an IRI.

## UC-2: Selection of metadata standards and ontologies

**Catalog question:** “What standards, ontologies, classifications, etc. are
used to describe the data and contextual information?”

**Question URI:**

`https://rdmo.fairagro.net/terms/questions/dmp4nfdi/v1-0-0/DMP/Dataset/Metadata/rdadmp_metadata_standard_id/rdadmp_identifier`

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/metadata/standards`

This question selects complete semantic artefacts rather than individual
concepts. Its provider is restricted to the FAIRagro TS4NFDI collection. At
the time of writing, this collection includes ENVO, the Plant Trait Ontology
(TO), PPEO, GSC MIxS, and AGROVOC.

Autocomplete results should identify:

- the artefact title and acronym;
- the terminology provider or backend;
- a short description;
- its public URI;
- version information, where available; and
- membership in the FAIRagro collection.

After selection, an ontology-information view can explain the purpose of the
resource and link to its landing page. Entity hierarchy tabs do not apply
because the selected value represents the ontology itself, not one of its
concepts.

This use case is also useful as guidance: selecting MIxS, for example, can
remind the respondent that a community checklist may influence which
contextual metadata should be collected during the project.

## UC-3: Controlled dataset topics and discovery keywords

**Related catalog questions:**

- “What kind of dataset is it?”
- “Will search keywords be provided in the metadata to optimize the
  possibility for discovery and then potential re-use?”

The current keyword question records only a yes/no answer, while the dataset
description is free text. A useful catalog extension would add a repeatable
question such as “Which controlled subjects or keywords describe the
dataset?”.

AGROVOC is a strong default for agricultural topics, crops, practices,
materials, and processes. The field should also allow ordinary free-text
keywords because not every locally relevant term will have a suitable
controlled concept.

For a controlled keyword, the interview can display the preferred label,
AGROVOC badge, definition or scope note, alternative labels, and broader
topic. This helps respondents select a concept that improves discovery
without requiring them to understand SKOS or ontology modelling.

The controlled keyword is complementary to the project description. The
plugin should not automatically extract or assign concepts from the free-text
description without explicit user confirmation.

## UC-4: Environmental material and sample context

**Related catalog page:** Project Data Description

The question “What kind of dataset is it?” already asks for the data type and
collection method, but environmental and sample context is embedded in a
free-text answer. A repeatable structured question could ask:

> Which environmental materials, environments, or sample contexts are
> represented in this dataset?

The FAIRagro collection already provides two complementary sources:

- **ENVO** for environmental materials, environmental features, and biomes;
- **MIxS** for sample contexts and checklist-related metadata concepts.

This is a good example of why definitions and provider badges matter. A user
searching for “soil” may need to choose between a general agricultural
subject, the ENVO environmental material, or a MIxS checklist/sample class.

The details drawer should initially show the definition and terminology. One
level of parents can be helpful for orientation, but a large hierarchy should
remain optional.

## UC-5: Plant traits and observed variables

**Related catalog page:** Project Data Description

Agricultural datasets frequently contain measured plant traits, but the
catalog currently has no dedicated structured field for them. A repeatable
question could ask:

> Which plant traits or phenotypic variables are measured or derived?

The Plant Trait Ontology (TO) is the natural first search scope. Results such
as “plant height” can be distinguished from more specific traits by showing
their definition and parent concepts. The selected IRI can later help users
understand whether two datasets measure the same trait even if their local
column names differ.

This field should describe the semantic meaning of a variable, not its
complete measurement specification. Units, protocols, instruments, and local
variable names belong in separate answers or documentation.

Useful annotation details include:

- preferred label and definition;
- TO identifier and IRI;
- synonyms;
- broader trait;
- related anatomical or organism context, when available.

## UC-6: Experiment and data-creation methods

**Catalog question:** “How does your project generate new data? Which tools,
software, technologies or processes are used to generate or collect them?”

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/creation_methods`

The existing question uses a local option set for broad creation categories.
Those choices should remain because they are understandable and stable.
Terminology support can be added as a more specific follow-up, for example:

> Which experimental designs or domain-specific collection methods are used?

PPEO can provide concepts related to plant phenotyping experiments, while
AGROVOC can cover broader agricultural methods and processes. Depending on
the project, a separately curated collection may also include OBI or CHMO.

The terminology field should supplement rather than replace the existing
high-level choices. A concept definition is valuable here because similar
method names can refer to a general activity, a protocol, or an experimental
design.

## UC-7: Data-processing operations

**Catalog question:** “In what way is the data processed in your project?”

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/usage_description`

The existing textarea is appropriate for documenting a processing workflow
and should remain the primary answer. An optional repeatable concept field
could capture common operations such as conversion, normalization, image
analysis, sequence analysis, or statistical processing.

EDAM contains data-analysis operations and topics in addition to formats.
Unlike the format provider, this provider would need to restrict results to
the relevant EDAM operation branch. Domain-specific operations may instead
come from PPEO or another curated collection.

The controlled operations provide an overview; they do not replace the
ordered workflow, parameters, software versions, or executable workflow
documentation requested by the free-text question.

## UC-8: Software, tools, and instruments

**Catalog question:** “What software, processes or technologies are required
to use the data?”

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/usage_technology`

The existing field is creatable and backed by a local option set. It could be
augmented with terminology results from resources such as the Software
Ontology (SWO), OBI, or CHMO, provided that a suitable curated collection is
selected.

This use case should be treated as optional because software registries and
persistent software identifiers may be a better source for concrete software
products and versions. Terminologies are more suitable for classes of
software, instruments, or methods than for every product release.

## UC-9: Licenses and terms of use

**Catalog question:** “Under which terms of use or license will the dataset
be published or shared?”

**Attribute URI:**

`https://rdmorganiser.github.io/terms/domain/project/dataset/sharing/conditions`

SPDX terminology data could provide canonical software-license names and
identifiers. An annotation could explain the selected license and link to its
official identifier.

This is not a first-priority use case. Creative Commons and common dataset
licenses form a relatively small, stable list, and local catalog options may
provide a faster and more reliable interview experience. Terminology lookup
is useful only if it offers broader coverage or better identifiers than the
maintained static list.

## Cross-cutting use cases

### Semantic review of completed answers

On an interview review page, the plugin could summarize all values carrying
concept IRIs and flag:

- duplicate concepts entered under different labels;
- values whose IRI can no longer be resolved;
- obsolete concepts, if the source reports them;
- free-text entries next to semantically annotated values; and
- answers from a terminology outside the catalog's recommended collection.

These should be warnings or suggestions, not automatic changes to project
answers.

### Contextual help before selection

Question help can explain which terminology is searched and what kind of
concept the user is expected to choose. For example, the plant-trait question
should say that TO describes the measured characteristic, not the unit or
measurement method.

### Curated terminology collections

Catalog maintainers can configure each provider around a TS4NFDI collection
rather than exposing every connected terminology. This makes search results
more relevant and lets FAIRagro domain experts change the recommended
terminology set without rewriting the interview integration.

## Technical and UX principles

1. **Store stable IRIs.** Labels are for display; the IRI is the semantic
   identity of a selected concept.
2. **Keep search scopes narrow.** Prefer a catalog-specific collection or a
   small ontology list over unrestricted federated search.
3. **Show provenance.** Every result and annotation should identify its
   terminology and, where useful, its backend/provider.
4. **Do not force a semantic match.** Creatable fields and explicit “no
   suitable term” behavior are important when coverage is incomplete.
5. **Load details on demand.** Definitions are useful during selection;
   hierarchies, graphs, relations, and ontology metadata belong in an optional
   details view.
6. **Degrade gracefully.** A Gateway or widget failure must not prevent users
   from reading, editing, or saving their RDMO answers.
7. **Do not infer annotations silently.** Suggestions derived from free text
   require user confirmation before an IRI is stored.
8. **Treat upstream components as external dependencies.** Pin the vendored
   TSS release, keep the integration configuration-driven, and avoid copying
   Gateway response adapters or ontology-specific business logic into this
   plugin.

## Suggested implementation order

1. Stabilize the existing EDAM data-format and FAIRagro
   metadata-standard annotations.
2. Add an example controlled-keyword question using AGROVOC.
3. Add environmental/sample-context and plant-trait questions using the
   current FAIRagro collection.
4. Evaluate PPEO for a specific experiment-method follow-up question.
5. Add semantic review warnings only after several real catalogs and projects
   have used the controlled fields.
6. Evaluate software, units, methods, and licenses separately; do not expand
   the default collection until there is a concrete catalog question and a
   clear benefit for respondents.

## References

- [TS4NFDI service documentation](https://terminology.services.base4nfdi.de/documentation)
- [Terminology Service Suite](https://terminology.services.base4nfdi.de/tss/comp/latest/)
- [TS4NFDI API Gateway](https://ts4nfdi.github.io/api-gateway/)
- [TS4NFDI public collections](https://terminology.services.base4nfdi.de/api-gateway/collections/)
