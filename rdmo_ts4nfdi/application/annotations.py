import logging
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from typing import Any, Protocol

from rdmo_ts4nfdi.domain import (
    AnnotationCandidate,
    AnnotationDetail,
    AnnotationMatcher,
    AnnotationOccurrence,
    AnnotationSummary,
    PageAnnotations,
    PresentationDescriptor,
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
)

logger = logging.getLogger(__name__)


class InterviewHost(Protocol):
    def project_id(self, project: Any) -> int: ...

    def page_id(self, page: Any) -> int: ...

    def page_candidates(self, project: Any, page: Any) -> Iterable[AnnotationCandidate]: ...

    def value_candidates(self, project: Any, value: Any) -> Iterable[AnnotationCandidate]: ...


class MetadataResolver(Protocol):
    def resolve(self, candidate: AnnotationCandidate, matcher: AnnotationMatcher) -> ResolvedMetadata: ...


class PresentationAdapter(Protocol):
    def build(
        self,
        project_id: int,
        annotation: AnnotationSummary,
        metadata: ResolvedMetadata,
        matcher: AnnotationMatcher,
    ) -> PresentationDescriptor: ...


class MatcherRegistry:
    def __init__(self, matchers: Sequence[AnnotationMatcher]):
        self._matchers = tuple(matchers)

    def match(self, question: QuestionContext, matcher_id: str | None = None) -> AnnotationMatcher | None:
        return next(
            (
                matcher
                for matcher in self._matchers
                if (matcher_id is None or matcher.id == matcher_id) and matcher.matches(question)
            ),
            None,
        )


class AnnotationService:
    """Framework-independent annotation use cases.

    RDMO model traversal, TS4NFDI response handling, and widget construction are
    delegated to replaceable adapters.
    """

    def __init__(
        self,
        *,
        host: InterviewHost,
        metadata: MetadataResolver,
        presentation: PresentationAdapter,
        matchers: Sequence[AnnotationMatcher],
    ):
        self.host = host
        self.metadata = metadata
        self.presentation = presentation
        self.matchers = MatcherRegistry(matchers)

    def list_page(self, project: Any, page: Any) -> PageAnnotations:
        grouped: OrderedDict[
            tuple[int, str, int],
            tuple[QuestionContext, list[AnnotationSummary]],
        ] = OrderedDict()

        for candidate in self.host.page_candidates(project, page):
            matcher = self.matchers.match(candidate.question)
            if matcher is None:
                continue

            key = (
                candidate.question.question_id,
                candidate.set_prefix,
                candidate.set_index,
            )
            if key not in grouped:
                grouped[key] = (candidate.question, [])
            grouped[key][1].append(self._summarize(candidate, matcher))

        occurrences = tuple(
            AnnotationOccurrence(
                question=question,
                set_prefix=set_prefix,
                set_index=set_index,
                annotations=tuple(annotations),
            )
            for (_, set_prefix, set_index), (question, annotations) in grouped.items()
        )
        return PageAnnotations(
            project_id=self.host.project_id(project),
            page_id=self.host.page_id(page),
            occurrences=occurrences,
        )

    def detail(self, project: Any, value: Any, matcher_id: str | None = None) -> AnnotationDetail:
        candidate_and_matcher = next(
            (
                (candidate, matcher)
                for candidate in self.host.value_candidates(project, value)
                if (matcher := self.matchers.match(candidate.question, matcher_id)) is not None
            ),
            None,
        )
        if candidate_and_matcher is None:
            raise LookupError('No TS4NFDI annotation matcher applies to this value.')

        candidate, matcher = candidate_and_matcher
        annotation = self._summarize(candidate, matcher)
        status = 'available'
        try:
            metadata = self.metadata.resolve(candidate, matcher)
        except Exception:
            logger.exception(
                'Could not resolve TS4NFDI annotation metadata for project=%s value=%s',
                self.host.project_id(project),
                candidate.value_id,
            )
            status = 'unavailable'
            metadata = ResolvedMetadata(ontology_id=matcher.ontology_id)

        presentation = self.presentation.build(
            self.host.project_id(project),
            annotation,
            metadata,
            matcher,
        )
        return AnnotationDetail(
            annotation=annotation,
            metadata_status=status,
            metadata=metadata,
            presentation=presentation,
        )

    @staticmethod
    def _summarize(candidate: AnnotationCandidate, matcher: AnnotationMatcher) -> AnnotationSummary:
        terminology = None
        if matcher.ontology_id or matcher.badge_label:
            terminology = ResourceReference(
                id=matcher.ontology_id,
                label=matcher.badge_label or matcher.ontology_id,
            )

        return AnnotationSummary(
            value_id=candidate.value_id,
            collection_index=candidate.collection_index,
            matcher_id=matcher.id,
            kind=matcher.resource_type,
            label=candidate.label,
            iri=candidate.iri,
            badge_label=matcher.badge_label,
            source=matcher.source,
            terminology=terminology,
            question_id=candidate.question.question_id,
        )
