"""Framework-independent terminology annotation models."""

from .annotations import (
    AnnotationCandidate,
    AnnotationDetail,
    AnnotationMatcher,
    AnnotationOccurrence,
    AnnotationSummary,
    InterviewAnswer,
    PageAnnotations,
    PresentationDescriptor,
    PresentationPolicy,
    ProjectAnnotations,
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
)
from .semantic_options import (
    SEMANTIC_CURATION_STATUSES,
    SEMANTIC_MAPPING_RELATIONS,
    OptionExternalIdProjectionPolicy,
    SemanticOption,
    SemanticOptionRegistry,
    SemanticOptionSet,
    SemanticTarget,
)

__all__ = [
    'SEMANTIC_CURATION_STATUSES',
    'SEMANTIC_MAPPING_RELATIONS',
    'AnnotationCandidate',
    'AnnotationDetail',
    'AnnotationMatcher',
    'AnnotationOccurrence',
    'AnnotationSummary',
    'InterviewAnswer',
    'OptionExternalIdProjectionPolicy',
    'PageAnnotations',
    'PresentationDescriptor',
    'PresentationPolicy',
    'ProjectAnnotations',
    'QuestionContext',
    'ResolvedMetadata',
    'ResourceReference',
    'SemanticOption',
    'SemanticOptionRegistry',
    'SemanticOptionSet',
    'SemanticTarget',
]
