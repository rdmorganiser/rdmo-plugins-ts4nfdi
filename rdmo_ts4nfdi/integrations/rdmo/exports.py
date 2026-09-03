from typing import Any

from django.utils.encoding import force_str

from rdmo.views.templatetags import view_tags
from rdmo.views.utils import ProjectWrapper

EXPORT_FORMAT = 'rdmo-ts4nfdi-annotated-answers'
EXPORT_SCHEMA_VERSION = '1'


class RDMOAnnotatedAnswersBuilder:
    """Build one condition-aware export model for JSON, XML, and PDF."""

    def __init__(self, annotation_service):
        self.annotation_service = annotation_service

    def build(self, project, snapshot=None) -> dict[str, Any]:
        project.catalog.prefetch_elements()
        project_wrapper = ProjectWrapper(project, snapshot)
        values = list(
            project.values.filter(snapshot=snapshot)
            .select_related('attribute', 'option')
            .order_by('attribute', 'set_prefix', 'set_index', 'collection_index')
        )
        values_by_id = {value.id: value for value in values}
        annotations_by_value_id = self._annotations_by_value_id(
            project,
            snapshot,
            values_by_id,
        )

        sections = []
        for section in project_wrapper.catalog.get('sections', []):
            pages = []
            for page in section.get('pages', []):
                answers = self._build_answers(
                    page.get('elements', []),
                    project_wrapper,
                    values_by_id,
                    annotations_by_value_id,
                )
                if answers:
                    pages.append(
                        {
                            'id': page.get('id'),
                            'uri': page.get('uri'),
                            'title': force_str(page.get('title') or ''),
                            'answers': answers,
                        }
                    )
            if pages:
                sections.append(
                    {
                        'id': section.get('id'),
                        'uri': section.get('uri'),
                        'title': force_str(section.get('title') or ''),
                        'pages': pages,
                    }
                )

        return {
            'format': EXPORT_FORMAT,
            'schema_version': EXPORT_SCHEMA_VERSION,
            'project': self._project(project),
            'snapshot': self._snapshot(snapshot),
            'sections': sections,
        }

    def _annotations_by_value_id(self, project, snapshot, values_by_id):
        annotations = {}
        for page in project.catalog.pages:
            payload = self.annotation_service.list_page_v2(
                project,
                page,
                snapshot=snapshot,
            )
            for occurrence in payload.occurrences:
                for descriptor in occurrence.annotations:
                    annotation = descriptor.annotation
                    value = values_by_id.get(annotation.value_id)
                    external_id = self._external_id(value)
                    # Local RDMO option URIs are identifiers for catalog choices,
                    # not terminology annotations. Only persisted provider identity
                    # is eligible for the semantic annotation block.
                    if external_id and external_id == annotation.iri.strip():
                        annotations[annotation.value_id] = annotation.to_dict()
        return annotations

    def _build_answers(
        self,
        elements,
        project_wrapper,
        values_by_id,
        annotations_by_value_id,
    ):
        answers = []
        for question in self._questions(elements):
            attribute_uri = question.get('attribute')
            if not attribute_uri:
                continue
            set_prefixes = view_tags.get_set_prefixes(
                {},
                attribute_uri,
                project=project_wrapper,
            )
            for set_prefix in set_prefixes:
                set_indexes = view_tags.get_set_indexes(
                    {},
                    attribute_uri,
                    set_prefix=set_prefix,
                    project=project_wrapper,
                )
                for set_index in set_indexes:
                    if not view_tags.check_element(
                        {},
                        question,
                        set_prefix=set_prefix,
                        set_index=set_index,
                        project=project_wrapper,
                    ):
                        continue
                    value_dicts = view_tags.get_values(
                        {},
                        attribute_uri,
                        set_prefix=set_prefix,
                        set_index=set_index,
                        project=project_wrapper,
                    )
                    value_dicts = [value for value in value_dicts if not value.get('is_empty', True)]
                    if not value_dicts:
                        continue
                    labels = view_tags.get_labels(
                        {},
                        question,
                        set_prefix=set_prefix,
                        set_index=set_index,
                        project=project_wrapper,
                    )
                    answers.append(
                        {
                            'question': {
                                'id': question.get('id'),
                                'uri': question.get('uri'),
                                'text': force_str(question.get('text') or ''),
                            },
                            'attribute_uri': attribute_uri,
                            'set_prefix': set_prefix,
                            'set_index': set_index,
                            'set_labels': [force_str(label) for label in labels],
                            'values': [
                                self._value(
                                    value_dict,
                                    values_by_id,
                                    annotations_by_value_id,
                                )
                                for value_dict in value_dicts
                            ],
                        }
                    )
        return answers

    @classmethod
    def _value(cls, value_dict, values_by_id, annotations_by_value_id):
        value_id = value_dict.get('id')
        value = values_by_id.get(value_id)
        external_id = cls._external_id(value) or cls._clean(value_dict.get('external_id'))
        option_uri = cls._clean(value_dict.get('option_uri'))
        option = None
        if option_uri:
            option = {
                'uri': option_uri,
                'label': force_str(value_dict.get('option_text') or ''),
            }

        file = None
        if value_dict.get('file_name'):
            file = {
                'name': force_str(value_dict['file_name']),
                'url': cls._clean(value_dict.get('file_url')),
            }

        annotation = annotations_by_value_id.get(value_id)
        if annotation and external_id != cls._clean(annotation.get('iri')):
            annotation = None

        return {
            'id': value_id,
            'collection_index': value_dict.get('collection_index', 0),
            'value_type': value_dict.get('value_type'),
            'text': force_str(value_dict.get('text') or ''),
            'label': force_str(value_dict.get('value_and_unit') or ''),
            'unit': cls._clean(value_dict.get('unit')),
            'option': option,
            'external_id': external_id,
            'annotation': annotation,
            'file': file,
        }

    @staticmethod
    def _questions(elements):
        for element in elements:
            children = element.get('elements')
            if children is None:
                yield element
            else:
                yield from RDMOAnnotatedAnswersBuilder._questions(children)

    @staticmethod
    def _project(project):
        return {
            'id': project.id,
            'title': force_str(project.title),
            'description': force_str(project.description or ''),
            'catalog_uri': project.catalog.uri if project.catalog else None,
            'created': RDMOAnnotatedAnswersBuilder._isoformat(project.created),
            'updated': RDMOAnnotatedAnswersBuilder._isoformat(project.updated),
        }

    @staticmethod
    def _snapshot(snapshot):
        if snapshot is None:
            return None
        return {
            'id': snapshot.id,
            'title': force_str(snapshot.title),
            'description': force_str(snapshot.description or ''),
            'created': RDMOAnnotatedAnswersBuilder._isoformat(snapshot.created),
            'updated': RDMOAnnotatedAnswersBuilder._isoformat(snapshot.updated),
        }

    @staticmethod
    def _external_id(value):
        return RDMOAnnotatedAnswersBuilder._clean(
            value.external_id if value is not None else None
        )

    @staticmethod
    def _clean(value):
        if value is None:
            return None
        value = force_str(value).strip()
        return value or None

    @staticmethod
    def _isoformat(value):
        return value.isoformat() if value is not None else None
