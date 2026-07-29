from collections.abc import Iterable

from rdmo.projects.utils import check_conditions
from rdmo.questions.models import Question, QuestionSet

from rdmo_ts4nfdi.domain import AnnotationCandidate, QuestionContext
from rdmo_ts4nfdi.utils import is_http_iri


class RDMOInterviewHost:
    """Translate public RDMO project models into plugin-owned domain models."""

    @staticmethod
    def project_id(project) -> int:
        return project.id

    @staticmethod
    def page_id(page) -> int:
        return page.id

    def page_candidates(self, project, page) -> Iterable[AnnotationCandidate]:
        values = self._project_values(project)

        for question in self._flatten_questions(page.elements):
            if not question.attribute:
                continue

            question_context = self._question_context(question)
            for value in values:
                if value.attribute_id != question.attribute_id or not is_http_iri(value.external_id):
                    continue
                if not check_conditions(
                    question.conditions.all(),
                    values,
                    value.set_prefix,
                    value.set_index,
                ):
                    continue
                yield self._candidate(question_context, value)

    def value_candidates(self, project, value) -> Iterable[AnnotationCandidate]:
        if not is_http_iri(value.external_id):
            raise LookupError('The selected value does not contain an HTTP IRI.')

        project.catalog.prefetch_elements()
        values = self._project_values(project)
        for question in project.catalog.questions:
            if question.attribute_id != value.attribute_id:
                continue
            if not check_conditions(
                question.conditions.all(),
                values,
                value.set_prefix,
                value.set_index,
            ):
                continue
            yield self._candidate(self._question_context(question), value)

    @staticmethod
    def _project_values(project):
        return list(
            project.values.filter(snapshot=None)
            .select_related('attribute', 'option')
            .order_by('attribute', 'set_prefix', 'set_index', 'collection_index')
        )

    @staticmethod
    def _question_context(question) -> QuestionContext:
        return QuestionContext(
            question_id=question.id,
            question_uri=question.uri,
            attribute_id=question.attribute_id,
            attribute_uri=question.attribute.uri,
            optionset_uris=tuple(optionset.uri for optionset in question.optionsets.all()),
        )

    @staticmethod
    def _candidate(question: QuestionContext, value) -> AnnotationCandidate:
        return AnnotationCandidate(
            question=question,
            value_id=value.id,
            label=value.text,
            iri=value.external_id,
            set_prefix=value.set_prefix,
            set_index=value.set_index,
            collection_index=value.collection_index,
        )

    @classmethod
    def _flatten_questions(cls, elements):
        for element in elements:
            if isinstance(element, Question):
                yield element
            elif isinstance(element, QuestionSet):
                yield from cls._flatten_questions(element.elements)
