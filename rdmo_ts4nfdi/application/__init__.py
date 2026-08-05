"""Application services coordinating host, Gateway, and presentation adapters."""

from .annotations import AnnotationService
from .targets import SemanticAnnotationTargetResolver
from .value_projection import SemanticOptionExternalIdProjector

__all__ = [
    'AnnotationService',
    'SemanticAnnotationTargetResolver',
    'SemanticOptionExternalIdProjector',
]
