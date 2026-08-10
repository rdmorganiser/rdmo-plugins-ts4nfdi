import logging
from collections import OrderedDict
from collections.abc import Iterable, Sequence
from dataclasses import replace
from typing import Any, Protocol

from rdmo_ts4nfdi.domain import (
    AnnotationCandidate,
    AnnotationDescriptor,
    AnnotationDescriptorOccurrence,
    AnnotationDetail,
    AnnotationMatcher,
    AnnotationOccurrence,
    AnnotationSummary,
    GatewayContext,
    InterviewAnswer,
    PageAnnotationDescriptors,
    PageAnnotations,
    PresentationDescriptor,
    ProjectAnnotations,
    QuestionContext,
    ResolvedMetadata,
    ResourceReference,
)

logger = logging.getLogger(__name__)

PUBLIC_GATEWAY_PARAM_KEYS = frozenset({'collectionId', 'database', 'lang'})


class InterviewHost(Protocol):
    def project_id(self, project: Any) -> int: ...

    def page_id(self, page: Any) -> int: ...

    def project_title(self, project: Any) -> str: ...

    def project_catalog_uri(self, project: Any) -> str | None: ...

    def project_pages(self, project: Any) -> Iterable[Any]: ...

    def page_answers(self, project: Any, page: Any) -> Iterable[InterviewAnswer]: ...

    def value_answers(self, project: Any, value: Any) -> Iterable[InterviewAnswer]: ...


class MetadataResolver(Protocol):
    def resolve(self, candidate: AnnotationCandidate, matcher: AnnotationMatcher) -> ResolvedMetadata: ...


class TargetResolver(Protocol):
    def resolve(
        self,
        answer: InterviewAnswer,
        matcher: AnnotationMatcher,
    ) -> Iterable[AnnotationCandidate]: ...


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
        targets: TargetResolver,
        metadata: MetadataResolver,
        presentation: PresentationAdapter,
        matchers: Sequence[AnnotationMatcher],
    ):
        self.host = host
        self.targets = targets
        self.metadata = metadata
        self.presentation = presentation
        self.matchers = MatcherRegistry(matchers)

    def list_page(self, project: Any, page: Any) -> PageAnnotations:
        grouped: OrderedDict[
            tuple[int, str, int],
            tuple[QuestionContext, list[AnnotationSummary]],
        ] = OrderedDict()

        for answer in self.host.page_answers(project, page):
            matcher = self.matchers.match(answer.question)
            if matcher is None:
                continue

            for candidate in self.targets.resolve(answer, matcher):
                key = (
                    candidate.question.question_id,
                    candidate.set_prefix,
                    candidate.set_index,
                )
                if key not in grouped:
                    grouped[key] = (candidate.question, [])
                metadata = self._resolve_summary_metadata(candidate, matcher)
                grouped[key][1].append(self._summarize(candidate, matcher, metadata))

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

    def list_page_v2(self, project: Any, page: Any) -> PageAnnotationDescriptors:
        grouped: OrderedDict[
            tuple[int, str, int],
            tuple[QuestionContext, list[AnnotationDescriptor]],
        ] = OrderedDict()

        for answer in self.host.page_answers(project, page):
            matcher = self.matchers.match(answer.question)
            if matcher is None:
                continue

            for candidate in self.targets.resolve(answer, matcher):
                contextual_matcher = self._contextualize_matcher(candidate, matcher)
                key = (
                    candidate.question.question_id,
                    candidate.set_prefix,
                    candidate.set_index,
                )
                if key not in grouped:
                    grouped[key] = (candidate.question, [])
                grouped[key][1].append(
                    AnnotationDescriptor(
                        annotation=self._summarize(candidate, contextual_matcher),
                        gateway_context=self._gateway_context(contextual_matcher),
                        presentation=contextual_matcher.presentation,
                    )
                )

        occurrences = tuple(
            AnnotationDescriptorOccurrence(
                question=question,
                set_prefix=set_prefix,
                set_index=set_index,
                annotations=tuple(annotations),
            )
            for (_, set_prefix, set_index), (question, annotations) in grouped.items()
        )
        return PageAnnotationDescriptors(
            project_id=self.host.project_id(project),
            page_id=self.host.page_id(page),
            occurrences=occurrences,
        )

    def export_project(self, project: Any) -> ProjectAnnotations:
        pages = tuple(
            page_annotations
            for page in self.host.project_pages(project)
            if (page_annotations := self.list_page(project, page)).occurrences
        )
        return ProjectAnnotations(
            project_id=self.host.project_id(project),
            title=self.host.project_title(project),
            catalog_uri=self.host.project_catalog_uri(project),
            pages=pages,
        )

    def detail(
        self,
        project: Any,
        value: Any,
        matcher_id: str | None = None,
    ) -> AnnotationDetail:
        candidate_and_matcher = next(
            (
                (candidate, matcher)
                for answer in self.host.value_answers(project, value)
                if (matcher := self.matchers.match(answer.question, matcher_id)) is not None
                for candidate in self.targets.resolve(answer, matcher)
            ),
            None,
        )
        if candidate_and_matcher is None:
            raise LookupError('No TS4NFDI annotation matcher applies to this value.')

        candidate, matcher = candidate_and_matcher
        matcher = self._contextualize_matcher(candidate, matcher)
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

    def _resolve_summary_metadata(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata | None:
        if not matcher.resolve_summary_metadata:
            return None
        try:
            return self.metadata.resolve(candidate, matcher)
        except Exception as exc:
            # Summary enrichment is optional. Keep the annotation list usable
            # when the external Gateway is slow, unavailable, or ambiguous.
            logger.warning(
                'Could not enrich TS4NFDI annotation summary for value=%s matcher=%r: %s',
                candidate.value_id,
                matcher.id,
                exc,
            )
            return None

    @staticmethod
    def _summarize(
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
        metadata: ResolvedMetadata | None = None,
    ) -> AnnotationSummary:
        terminology = candidate.terminology or (metadata.terminology if metadata else None)
        if terminology is None and (matcher.ontology_id or matcher.badge_label):
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
            short_form=metadata.short_form if metadata else None,
            source=candidate.source or (metadata.source if metadata else None) or matcher.source,
            terminology=terminology,
            answer_id=candidate.answer_id,
            question_id=candidate.question.question_id,
        )

    @staticmethod
    def _gateway_context(matcher: AnnotationMatcher) -> GatewayContext | None:
        source = matcher.source
        gateway_params = dict(matcher.gateway_query)
        database = source.database if source and source.database else gateway_params.get('database')
        params = tuple(
            (key, value)
            for key, value in matcher.gateway_query
            if key in PUBLIC_GATEWAY_PARAM_KEYS and key != 'database'
        )
        context = GatewayContext(
            ontology_id=matcher.ontology_id,
            database=database,
            backend_type=source.backend_type if source else None,
            params=params,
        )
        if not any((context.ontology_id, context.database, context.backend_type, context.params)):
            return None
        return context

    @staticmethod
    def _contextualize_matcher(
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> AnnotationMatcher:
        if not candidate.source and not candidate.terminology:
            return matcher

        gateway_params = dict(matcher.gateway_query)
        if candidate.source and candidate.source.database:
            gateway_params['database'] = candidate.source.database
        return replace(
            matcher,
            source=candidate.source or matcher.source,
            ontology_id=(
                candidate.terminology.id if candidate.terminology and candidate.terminology.id else matcher.ontology_id
            ),
            badge_label=(
                candidate.terminology.label
                if candidate.terminology and candidate.terminology.label
                else matcher.badge_label
            ),
            gateway_params=tuple(gateway_params.items()),
        )
