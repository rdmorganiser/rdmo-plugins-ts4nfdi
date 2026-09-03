from dataclasses import dataclass, field
from typing import Any, Literal

ResourceKind = Literal['entity', 'ontology', 'collection']
MetadataStatus = Literal['available', 'unavailable']


@dataclass(frozen=True, slots=True)
class ResourceReference:
    id: str | None = None
    label: str | None = None
    iri: str | None = None
    url: str | None = None
    database: str | None = None
    backend_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'id': self.id,
            'label': self.label,
            'iri': self.iri,
            'url': self.url,
            'database': self.database,
            'backend_type': self.backend_type,
        }


@dataclass(frozen=True, slots=True)
class PresentationPolicy:
    adapter: str = 'native'
    component: str | None = None
    options: tuple[tuple[str, Any], ...] = ()

    def option(self, key: str, default: Any = None) -> Any:
        return dict(self.options).get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return {
            'adapter': self.adapter,
            'component': self.component,
            'options': dict(self.options),
        }


@dataclass(frozen=True, slots=True)
class GatewayContext:
    ontology_id: str | None = None
    database: str | None = None
    backend_type: str | None = None
    params: tuple[tuple[str, Any], ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'ontology_id': self.ontology_id,
            'database': self.database,
            'backend_type': self.backend_type,
            'params': dict(self.params),
        }


@dataclass(frozen=True, slots=True)
class ContextResolutionPolicy:
    """Public browser policy for recovering missing annotation provenance."""

    adapter: Literal['gateway-search']

    def to_dict(self) -> dict[str, str]:
        return {'adapter': self.adapter}


@dataclass(frozen=True, slots=True)
class AnnotationMatcher:
    id: str
    question_uri: str
    attribute_uri: str
    optionset_uri: str
    resource_type: ResourceKind
    presentation: PresentationPolicy
    provider_key: str | None = None
    entityset_id: str | None = None
    entityset_endpoint: str | None = None
    source: ResourceReference | None = None
    badge_label: str | None = None
    ontology_id: str | None = None
    gateway_params: tuple[tuple[str, Any], ...] = ()
    resolve_summary_metadata: bool = False
    provider_resource_detail: bool = False
    context_resolution: ContextResolutionPolicy | None = None

    def matches(self, question: 'QuestionContext') -> bool:
        return (
            self.question_uri == question.question_uri
            and self.attribute_uri == question.attribute_uri
            and self.optionset_uri in question.optionset_uris
        )

    @property
    def gateway_query(self) -> tuple[tuple[str, Any], ...]:
        return self.gateway_params


@dataclass(frozen=True, slots=True)
class QuestionContext:
    question_id: int
    question_uri: str
    attribute_id: int
    attribute_uri: str
    optionset_uris: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class InterviewAnswer:
    question: QuestionContext
    value_id: int
    label: str
    identifier: str
    set_prefix: str
    set_index: int
    collection_index: int


@dataclass(frozen=True, slots=True)
class AnnotationCandidate:
    question: QuestionContext
    value_id: int
    label: str
    iri: str
    set_prefix: str
    set_index: int
    collection_index: int
    answer_id: str | None = None
    source: ResourceReference | None = None
    terminology: ResourceReference | None = None


@dataclass(frozen=True, slots=True)
class AnnotationSummary:
    value_id: int
    collection_index: int
    matcher_id: str
    kind: ResourceKind
    label: str
    iri: str
    question_id: int
    badge_label: str | None = None
    short_form: str | None = None
    source: ResourceReference | None = None
    terminology: ResourceReference | None = None
    answer_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            'value_id': self.value_id,
            'collection_index': self.collection_index,
            'matcher_id': self.matcher_id,
            'kind': self.kind,
            'label': self.label,
            'iri': self.iri,
            'badge_label': self.badge_label,
            'short_form': self.short_form,
            'source': self.source.to_dict() if self.source else None,
            'terminology': self.terminology.to_dict() if self.terminology else None,
            'answer_id': self.answer_id,
            'question_id': self.question_id,
        }


@dataclass(frozen=True, slots=True)
class AnnotationDescriptor:
    annotation: AnnotationSummary
    gateway_context: GatewayContext | None
    presentation: PresentationPolicy
    entityset_provenance: bool = False
    provider_resource_detail: bool = False
    context_resolution: ContextResolutionPolicy | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.annotation.to_dict(),
            'gateway_context': self.gateway_context.to_dict() if self.gateway_context else None,
            'presentation': self.presentation.to_dict(),
            'entityset_provenance': self.entityset_provenance,
            'provider_resource_detail': self.provider_resource_detail,
            'context_resolution': self.context_resolution.to_dict() if self.context_resolution else None,
        }


@dataclass(frozen=True, slots=True)
class EntitySetProvenance:
    """Click-time context recovered from a configured Gateway entity set.

    This intentionally contains only the entity-set record and configured source
    information. It is not a replacement for Gateway metadata normalization.
    """

    annotation: AnnotationSummary
    source: ResourceReference | None
    terminology: ResourceReference | None
    gateway_context: GatewayContext | None
    definitions: tuple[str, ...] = ()
    presentation: PresentationPolicy = field(default_factory=PresentationPolicy)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.annotation.to_dict(),
            'metadata_status': 'available',
            'ontology_id': self.gateway_context.ontology_id if self.gateway_context else None,
            'description': self.definitions[0] if self.definitions else None,
            'definitions': list(self.definitions),
            'synonyms': [],
            'entity_types': [],
            'obsolete': None,
            'version': None,
            'source': self.source.to_dict() if self.source else None,
            'terminology': self.terminology.to_dict() if self.terminology else None,
            'gateway_context': self.gateway_context.to_dict() if self.gateway_context else None,
            'presentation': self.presentation.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class AnnotationOccurrence:
    question: QuestionContext
    set_prefix: str
    set_index: int
    annotations: tuple[AnnotationSummary, ...]

    @property
    def key(self) -> str:
        return f'{self.question.question_id}:{self.set_prefix}:{self.set_index}'

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'question_id': self.question.question_id,
            'question_uri': self.question.question_uri,
            'attribute_id': self.question.attribute_id,
            'set_prefix': self.set_prefix,
            'set_index': self.set_index,
            'annotations': [annotation.to_dict() for annotation in self.annotations],
        }


@dataclass(frozen=True, slots=True)
class AnnotationDescriptorOccurrence:
    question: QuestionContext
    set_prefix: str
    set_index: int
    annotations: tuple[AnnotationDescriptor, ...]

    @property
    def key(self) -> str:
        return f'{self.question.question_id}:{self.set_prefix}:{self.set_index}'

    def to_dict(self) -> dict[str, Any]:
        return {
            'key': self.key,
            'question_id': self.question.question_id,
            'question_uri': self.question.question_uri,
            'attribute_id': self.question.attribute_id,
            'set_prefix': self.set_prefix,
            'set_index': self.set_index,
            'annotations': [annotation.to_dict() for annotation in self.annotations],
        }


@dataclass(frozen=True, slots=True)
class PageAnnotations:
    project_id: int
    page_id: int
    occurrences: tuple[AnnotationOccurrence, ...]
    api_version: str = '1'

    def to_dict(self) -> dict[str, Any]:
        return {
            'api_version': self.api_version,
            'project_id': self.project_id,
            'page_id': self.page_id,
            'occurrences': [occurrence.to_dict() for occurrence in self.occurrences],
        }


@dataclass(frozen=True, slots=True)
class PageAnnotationDescriptors:
    project_id: int
    page_id: int
    occurrences: tuple[AnnotationDescriptorOccurrence, ...]
    api_version: str = '2'

    def to_dict(self) -> dict[str, Any]:
        return {
            'api_version': self.api_version,
            'project_id': self.project_id,
            'page_id': self.page_id,
            'occurrences': [occurrence.to_dict() for occurrence in self.occurrences],
        }


@dataclass(frozen=True, slots=True)
class ResolvedMetadata:
    label: str | None = None
    description: str | None = None
    definitions: tuple[str, ...] = ()
    synonyms: tuple[str, ...] = ()
    short_form: str | None = None
    entity_types: tuple[str, ...] = ()
    obsolete: bool | None = None
    version: str | None = None
    ontology_id: str | None = None
    source: ResourceReference | None = None
    terminology: ResourceReference | None = None


@dataclass(frozen=True, slots=True)
class CollectionCollaborator:
    """One collaborator returned by the Gateway collection resource."""

    username: str
    role: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            'username': self.username,
            'role': self.role,
        }


@dataclass(frozen=True, slots=True)
class CollectionTerminology:
    """A terminology membership suitable for native collection presentation."""

    label: str
    source: str | None = None
    uri: str | None = None
    type: str | None = None

    def to_dict(self) -> dict[str, str | None]:
        return {
            'label': self.label,
            'source': self.source,
            'uri': self.uri,
            'type': self.type,
        }


@dataclass(frozen=True, slots=True)
class CollectionMetadata:
    """The stable, display-safe subset of a Gateway collection record.

    The native RDMO drawer uses this model instead of a raw Gateway response.
    It deliberately excludes owner-only and implementation-specific fields.
    """

    uuid: str | None = None
    permalink: str | None = None
    is_public: bool | None = None
    creator: str | None = None
    collaborators: tuple[CollectionCollaborator, ...] = ()
    terminologies: tuple[CollectionTerminology, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            'uuid': self.uuid,
            'permalink': self.permalink,
            'is_public': self.is_public,
            'creator': self.creator,
            'collaborators': [collaborator.to_dict() for collaborator in self.collaborators],
            'terminologies': [terminology.to_dict() for terminology in self.terminologies],
        }


@dataclass(frozen=True, slots=True)
class PresentationDescriptor:
    adapter: str
    component: str | None = None
    props: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            'adapter': self.adapter,
            'component': self.component,
            'props': self.props,
        }


@dataclass(frozen=True, slots=True)
class AnnotationDetail:
    annotation: AnnotationSummary
    metadata_status: MetadataStatus
    metadata: ResolvedMetadata
    presentation: PresentationDescriptor
    gateway_context: GatewayContext | None = None
    collection: CollectionMetadata | None = None
    api_version: str = '1'

    def to_dict(self) -> dict[str, Any]:
        return {
            'api_version': self.api_version,
            **self.annotation.to_dict(),
            'metadata_status': self.metadata_status,
            'label': self.metadata.label or self.annotation.label,
            'description': self.metadata.description,
            'definitions': list(self.metadata.definitions),
            'synonyms': list(self.metadata.synonyms),
            'short_form': self.metadata.short_form,
            'entity_types': list(self.metadata.entity_types),
            'obsolete': self.metadata.obsolete,
            'version': self.metadata.version,
            'ontology_id': self.metadata.ontology_id,
            'source': (
                self.metadata.source.to_dict()
                if self.metadata.source
                else self.annotation.source.to_dict()
                if self.annotation.source
                else None
            ),
            'terminology': (
                self.metadata.terminology.to_dict()
                if self.metadata.terminology
                else self.annotation.terminology.to_dict()
                if self.annotation.terminology
                else None
            ),
            'gateway_context': self.gateway_context.to_dict() if self.gateway_context else None,
            'presentation': self.presentation.to_dict(),
            'collection': self.collection.to_dict() if self.collection else None,
        }
