from collections.abc import Iterable

from rdmo.projects.utils import check_conditions
from rdmo.questions.models import Question, QuestionSet

from rdmo_ts4nfdi.domain import InterviewAnswer, QuestionContext
from rdmo_ts4nfdi.utils import is_http_iri


class RDMOInterviewHost:
    """Translate public RDMO project models into plugin-owned domain models."""

    @staticmethod
    def project_id(project) -> int:
        return project.id

    @staticmethod
    def page_id(page) -> int:
        return page.id

    @staticmethod
    def project_title(project) -> str:
        return project.title

    @staticmethod
    def project_catalog_uri(project) -> str | None:
        return project.catalog.uri if project.catalog else None

    @staticmethod
    def project_pages(project):
        if project.catalog is None:
            return ()
        project.catalog.prefetch_elements()
        return tuple(project.catalog.pages)

    def page_answers(self, project, page) -> Iterable[InterviewAnswer]:
        values = self._project_values(project)

        for question in self._flatten_questions(page.elements):
            if not question.attribute:
                continue

            question_context = self._question_context(question)
            for value in values:
                if value.attribute_id != question.attribute_id:
                    continue
                identifier = self._value_identifier(value)
                if not identifier:
                    continue
                if not check_conditions(
                    question.conditions.all(),
                    values,
                    value.set_prefix,
                    value.set_index,
                ):
                    continue
                yield self._answer(question_context, value, identifier)

    def value_answers(self, project, value) -> Iterable[InterviewAnswer]:
        identifier = self._value_identifier(value)
        if not identifier:
            raise LookupError('The selected value does not contain an option or HTTP IRI.')

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
            yield self._answer(self._question_context(question), value, identifier)

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
    def _answer(question: QuestionContext, value, identifier: str) -> InterviewAnswer:
        return InterviewAnswer(
            question=question,
            value_id=value.id,
            label=value.label or value.text,
            identifier=identifier,
            set_prefix=value.set_prefix,
            set_index=value.set_index,
            collection_index=value.collection_index,
        )

    @staticmethod
    def _value_identifier(value) -> str | None:
        if value.option and is_http_iri(value.option.uri):
            return value.option.uri
        if is_http_iri(value.external_id):
            return value.external_id
        return None

    @classmethod
    def _flatten_questions(cls, elements):
        for element in elements:
            if isinstance(element, Question):
                yield element
            elif isinstance(element, QuestionSet):
                yield from cls._flatten_questions(element.elements)
