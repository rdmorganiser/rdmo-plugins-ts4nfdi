# Interview presentation adapters

The annotation drawer always renders the plugin's normalized, accessible
terminology details first. A presentation adapter may add an optional widget
below that information. This makes the choice reversible: a deployment can
use the native prototype, an official Terminology Service Suite (TSS) widget,
or its own JavaScript module without changing the annotation API or the RDMO
host integration.

The selection is made per annotation matcher in `TS4NFDI_PROVIDER`. If the
deployment loads that setting from `ts4nfdi_provider.toml`, changing the
matcher's `presentation` table is sufficient.

## Built-in native presentation

Use the native presentation when the normalized label, definition, synonyms,
source, terminology, identifiers, and links are enough:

```toml
[[frontend.annotations.matchers]]
id = "fairagro-dataset-format"
question_uri = "https://rdmo.fairagro.net/terms/questions/dmp4nfdi/v1-0-0/DMP/Dataset/Distribution/rdadmp_format"
attribute_uri = "https://rdmorganiser.github.io/terms/domain/project/dataset/format"
optionset_uri = "https://rdmo.fairagro.net/terms/options/ts4nfdi/file_format_grouped"
resource_type = "entity"
source_key = "ebi"
ontology_id = "edam"
presentation = { adapter = "native" }
```

No TSS bundle or deployment module is loaded for this matcher. Gateway
metadata is still resolved by the plugin when a user opens an annotation.

## Built-in TSS presentation

Select `tss` and a compatible public TSS component to add the official widget:

```toml
presentation = {
    adapter = "tss",
    component = "entity-info",
    entity_type = "class",
}
```

The supported combinations are:

| Annotation resource | TSS component | Optional settings |
| --- | --- | --- |
| `entity` | `entity-info` | `entity_type` |
| `entity` | `metadata` | `entity_type`, `tabs` |
| `ontology` | `ontology-info` | none |

For example, the metadata tabs can be selected explicitly:

```toml
presentation = {
    adapter = "tss",
    component = "metadata",
    entity_type = "class",
    tabs = ["synonyms", "hierarchy", "ontology", "crossref"],
}
```

The TSS JavaScript and CSS remain lazy: the browser loads the vendored release
only when the user expands “Additional interactive terminology view”. The
adapter receives the Gateway query parameters derived from the matcher, such
as `database=ebi`. If loading or mounting TSS fails, the native detail above it
remains usable.

## Deployment-defined JavaScript presentation

A custom adapter consists of:

1. an ES module available through the deployment's Django static files;
2. one module registration under `frontend.presentation_adapters`;
3. a matching adapter name in the annotation matcher.

Assume the RDMO app provides
`fairagro/static/fairagro/js/ts4nfdi_concept_card.js`. Register its static path:

```toml
[frontend.presentation_adapters.fairagro-concept-card]
static_path = "fairagro/js/ts4nfdi_concept_card.js"
export = "createConceptCard"
```

Then select it for one or more matchers:

```toml
[[frontend.annotations.matchers]]
id = "fairagro-dataset-format"
question_uri = "https://rdmo.fairagro.net/terms/questions/dmp4nfdi/v1-0-0/DMP/Dataset/Distribution/rdadmp_format"
attribute_uri = "https://rdmorganiser.github.io/terms/domain/project/dataset/format"
optionset_uri = "https://rdmo.fairagro.net/terms/options/ts4nfdi/file_format_grouped"
resource_type = "entity"
source_key = "ebi"
ontology_id = "edam"
presentation = {
    adapter = "fairagro-concept-card",
    component = "compact",
    accent = "green",
    show_source = true,
}
```

`component` is an optional deployment-defined variant. All other presentation
values are sent unchanged as `descriptor.props`.

The named export is a factory. It receives stable plugin context and returns an
object with a `render` method:

```javascript
export function createConceptCard({baseUrl, translate}) {
    return {
        render(element, descriptor, {detail, signal}) {
            const card = document.createElement("section");
            card.className = [
                "fairagro-concept-card",
                `fairagro-concept-card--${descriptor.props.accent || "default"}`
            ].join(" ");

            const heading = document.createElement("h3");
            heading.textContent = detail.label;
            card.appendChild(heading);

            for (const definition of detail.definitions || []) {
                const paragraph = document.createElement("p");
                paragraph.textContent = definition;
                card.appendChild(paragraph);
            }

            const link = document.createElement("a");
            link.href = detail.iri;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = translate("Open terminology identifier");
            card.appendChild(link);
            element.appendChild(card);

            return () => {
                // Remove third-party listeners, subscriptions, or framework
                // roots here. The host element itself is cleared afterward.
            };
        }
    };
}
```

The factory context currently contains:

- `baseUrl`: the deployment's RDMO base URL, including a configured subpath;
- `translate(message)`: RDMO's gettext function with a plain-text fallback.

The render context contains the complete normalized annotation `detail`
returned by the plugin API and an `AbortSignal` named `signal`. The signal is
aborted before the presentation is replaced or closed, so asynchronous widgets
should pass it to their requests and stop mounting when it is aborted. The
presentation descriptor contains `adapter`, `component`, and the
matcher-defined `props`.

The module may instead default-export an adapter object:

```javascript
export default {
    render(element, descriptor, {detail}) {
        // Mount the widget.
        return {
            unmount() {
                // Optional cleanup.
            }
        };
    }
};
```

`render` may return a cleanup function, an object with `unmount()`, or an
object with `destroy()`. Cleanup runs when another annotation is opened, the
drawer closes, the interview page changes, or the controller stops. A rejected
asynchronous render or a thrown exception is contained by the presentation
registry; it cannot remove the native detail view.

The module deliberately receives no RDMO React/Redux state. It should render
only inside the supplied `element`, use the already normalized `detail`
whenever possible, and clean up resources it owns. Deployment-specific CSS can
be loaded through the RDMO app's normal base/interview template or imported by
the module's own build output.

## Switching an RDMO deployment

To switch one matcher, change only its `presentation` value:

```toml
# Plugin-native details only
presentation = { adapter = "native" }

# Official vendored TSS enhancement
presentation = { adapter = "tss", component = "entity-info", entity_type = "class" }

# Deployment-owned ES module
presentation = { adapter = "fairagro-concept-card", component = "compact" }
```

For the custom choice, keep the corresponding
`[frontend.presentation_adapters.<name>]` registration. It may remain
configured while no matcher uses it, although removing unused registrations
avoids importing unnecessary modules.

After changing the TOML:

1. restart the Django process so `TS4NFDI_PROVIDER` and its cached validation
   are reloaded;
2. run the deployment's `collectstatic` step when a custom module or its build
   output changed;
3. hard-reload the interview in the browser.

With the development command used by the app, restart:

```shell
uv run manage.py runserver
```

Configuration errors are logged by Django. Custom adapter module load and
render errors appear in the browser console, while the native detail view
continues to function.

## What each switch does not change

Presentation selection does not change:

- the RDMO question/attribute/option-set matcher;
- saved RDMO values;
- project authorization on plugin API requests;
- Gateway metadata normalization;
- the side-loaded RDMO interview host and its stable template slot;
- the pinned TSS version in
  `rdmo_ts4nfdi/vendor/terminology_service_suite.json`.

This keeps the four domains separate: RDMO supplies interview context, this
plugin supplies annotation orchestration and normalized detail, the TS4NFDI
Gateway supplies terminology data, and either TSS or a deployment module owns
only its optional presentation.
