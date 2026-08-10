"""Application services coordinating host, Gateway, and presentation adapters."""

from .annotations import AnnotationService
from .targets import AnnotationTargetResolver

__all__ = ['AnnotationService', 'AnnotationTargetResolver']
