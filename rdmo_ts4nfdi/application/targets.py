from collections.abc import Iterable

from rdmo_ts4nfdi.domain import AnnotationCandidate, AnnotationMatcher, InterviewAnswer
from rdmo_ts4nfdi.utils import is_http_iri


class AnnotationTargetResolver:
    """Turn stored RDMO answer identifiers into annotatable resources."""

    def resolve(
        self,
        answer: InterviewAnswer,
        matcher: AnnotationMatcher,
    ) -> Iterable[AnnotationCandidate]:
        # Regular entities remain HTTP-IRI-only. Provider-backed resources can
        # additionally use their provider's stable opaque identifier.
        if is_http_iri(answer.identifier) or matcher.provider_key:
            yield AnnotationCandidate(
                question=answer.question,
                value_id=answer.value_id,
                label=answer.label,
                iri=answer.identifier,
                set_prefix=answer.set_prefix,
                set_index=answer.set_index,
                collection_index=answer.collection_index,
                answer_id=answer.identifier,
            )
