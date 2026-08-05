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


@dataclass(frozen=True, slots=True)
class AnnotationMatcher:
    id: str
    question_uri: str
    attribute_uri: str
    optionset_uri: str
    resource_type: ResourceKind
    presentation: PresentationPolicy
    provider_key: str | None = None
    source: ResourceReference | None = None
    badge_label: str | None = None
    ontology_id: str | None = None
    mapping_set_id: str | None = None
    gateway_params: tuple[tuple[str, Any], ...] = ()
    resolve_summary_metadata: bool = False

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
    answer_label: str | None = None
    target_id: str | None = None
    target_label: str | None = None
    mapping_relation: str | None = None
    curation_status: str | None = None
    mapping_set_id: str | None = None
    mapping_set_version: str | None = None
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
    target_id: str | None = None
    target_label: str | None = None
    mapping_relation: str | None = None
    curation_status: str | None = None
    mapping_set_id: str | None = None
    mapping_set_version: str | None = None

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
            'target_id': self.target_id,
            'target_label': self.target_label,
            'mapping_relation': self.mapping_relation,
            'curation_status': self.curation_status,
            'mapping_set_id': self.mapping_set_id,
            'mapping_set_version': self.mapping_set_version,
            'question_id': self.question_id,
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
class ProjectAnnotations:
    project_id: int
    title: str
    catalog_uri: str | None
    pages: tuple[PageAnnotations, ...]
    api_version: str = '1'

    def to_dict(self) -> dict[str, Any]:
        return {
            'api_version': self.api_version,
            'project_id': self.project_id,
            'title': self.title,
            'catalog_uri': self.catalog_uri,
            'pages': [page.to_dict() for page in self.pages],
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
            'presentation': self.presentation.to_dict(),
        }
