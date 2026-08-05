from collections.abc import Iterable

from rdmo_ts4nfdi.domain import AnnotationCandidate, AnnotationMatcher, InterviewAnswer, SemanticOptionRegistry
from rdmo_ts4nfdi.utils import is_http_iri


class SemanticAnnotationTargetResolver:
    """Turn stored answer identities into resources that can be annotated."""

    def __init__(self, registry: SemanticOptionRegistry):
        self.registry = registry

    def resolve(
        self,
        answer: InterviewAnswer,
        matcher: AnnotationMatcher,
    ) -> Iterable[AnnotationCandidate]:
        if matcher.mapping_set_id:
            mapping_set = self.registry.get(matcher.mapping_set_id)
            option = mapping_set.get(answer.identifier)
            if option is None:
                return

            for target in option.targets:
                yield AnnotationCandidate(
                    question=answer.question,
                    value_id=answer.value_id,
                    label=target.label,
                    iri=target.iri,
                    set_prefix=answer.set_prefix,
                    set_index=answer.set_index,
                    collection_index=answer.collection_index,
                    answer_id=answer.identifier,
                    answer_label=answer.label,
                    target_id=target.id,
                    target_label=target.label,
                    mapping_relation=target.relation,
                    curation_status=target.curation_status,
                    mapping_set_id=mapping_set.id,
                    mapping_set_version=mapping_set.version,
                    source=target.source,
                    terminology=target.terminology,
                )
            return

        # Free-text and regular entity annotations remain HTTP-IRI-only.
        # Provider-backed resources can additionally be resolved by the
        # provider's own stable opaque identifier.
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
                answer_label=answer.label,
            )
