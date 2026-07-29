from collections.abc import Callable
from urllib.parse import urlencode

from rdmo_ts4nfdi.domain import (
    AnnotationMatcher,
    AnnotationSummary,
    PresentationDescriptor,
    ResolvedMetadata,
)

PresentationFactory = Callable[
    [int, AnnotationSummary, ResolvedMetadata, AnnotationMatcher],
    PresentationDescriptor,
]


class AnnotationPresentationRegistry:
    """Select a presentation adapter without coupling the application service to TSS."""

    def __init__(self):
        self._factories: dict[str, PresentationFactory] = {
            'native': self._native,
            'tss': self._tss,
        }

    def register(self, name: str, factory: PresentationFactory) -> None:
        if not name or name in self._factories:
            raise ValueError(f"Presentation adapter '{name}' is already registered.")
        self._factories[name] = factory

    def build(
        self,
        project_id: int,
        annotation: AnnotationSummary,
        metadata: ResolvedMetadata,
        matcher: AnnotationMatcher,
    ) -> PresentationDescriptor:
        factory = self._factories.get(matcher.presentation.adapter)
        if factory:
            return factory(project_id, annotation, metadata, matcher)

        # Deployment-defined browser adapters receive their matcher options
        # unchanged. They do not require a Python adapter merely to select a
        # different renderer.
        return PresentationDescriptor(
            adapter=matcher.presentation.adapter,
            component=matcher.presentation.component,
            props=dict(matcher.presentation.options),
        )

    @staticmethod
    def _native(
        project_id: int,
        annotation: AnnotationSummary,
        metadata: ResolvedMetadata,
        matcher: AnnotationMatcher,
    ) -> PresentationDescriptor:
        return PresentationDescriptor(adapter='native')

    @staticmethod
    def _tss(
        project_id: int,
        annotation: AnnotationSummary,
        metadata: ResolvedMetadata,
        matcher: AnnotationMatcher,
    ) -> PresentationDescriptor:
        component = matcher.presentation.component
        ontology_id = metadata.ontology_id or matcher.ontology_id
        if component == 'ontology-info' and not ontology_id:
            return PresentationDescriptor(adapter='native')

        props = {
            'api': f'/api/v1/ts4nfdi/projects/{project_id}/gateway/ols4/api/',
            'parameter': urlencode(matcher.gateway_query),
        }
        if annotation.kind == 'entity':
            props.update(
                {
                    'iri': annotation.iri,
                    'ontologyId': ontology_id,
                    'entityType': matcher.presentation.option('entity_type'),
                }
            )
        if component == 'entity-info':
            props.update(
                {
                    'hasTitle': False,
                    'showBadges': True,
                }
            )
        elif component == 'metadata':
            tabs = set(matcher.presentation.option('tabs', ()))
            props.update(
                {
                    'altNamesTab': 'synonyms' in tabs,
                    'hierarchyTab': 'hierarchy' in tabs,
                    'crossRefTab': 'crossref' in tabs,
                    'terminologyInfoTab': 'ontology' in tabs,
                    'graphViewTab': 'graphview' in tabs,
                    'termDepictionTab': 'depiction' in tabs,
                    'entityInfoTab': 'entityinfo' in tabs,
                    'entityRelationTab': 'entityrelations' in tabs,
                    'copyButton': 'right',
                }
            )
        elif component == 'ontology-info':
            props['ontologyId'] = ontology_id

        return PresentationDescriptor(
            adapter='tss',
            component=component,
            props={key: value for key, value in props.items() if value is not None},
        )
