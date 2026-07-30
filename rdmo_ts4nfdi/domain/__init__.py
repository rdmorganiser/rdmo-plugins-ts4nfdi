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
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
)
from .semantic_options import SemanticOption, SemanticOptionRegistry, SemanticOptionSet, SemanticTarget

__all__ = [
    'AnnotationCandidate',
    'AnnotationDetail',
    'AnnotationMatcher',
    'AnnotationOccurrence',
    'AnnotationSummary',
    'InterviewAnswer',
    'PageAnnotations',
    'PresentationDescriptor',
    'PresentationPolicy',
    'QuestionContext',
    'ResolvedMetadata',
    'ResourceReference',
    'SemanticOption',
    'SemanticOptionRegistry',
    'SemanticOptionSet',
    'SemanticTarget',
]
