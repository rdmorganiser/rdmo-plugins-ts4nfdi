# ruff: noqa: E402

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace
from xml.etree import ElementTree

import django

from rdmo.core import settings as rdmo_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rdmo.core.settings')
rdmo_settings.STATIC_ROOT = '/tmp/rdmo-ts4nfdi-test-static'
rdmo_settings.COMPRESS_ROOT = rdmo_settings.STATIC_ROOT
django.setup()

from rdmo_ts4nfdi.domain import AnnotationSummary, ResourceReference
from rdmo_ts4nfdi.export_renderers import (
    render_annotated_json,
    render_annotated_xml,
)
from rdmo_ts4nfdi.integrations.rdmo.exports import (
    EXPORT_FORMAT,
    RDMOAnnotatedAnswersBuilder,
)
from rdmo_ts4nfdi.integrations.rdmo.interview import RDMOInterviewHost

ENTITY_IRI = 'http://purl.obolibrary.org/obo/FOODON_03400740'
OPTION_IRI = 'https://rdmo.fairagro.net/terms/options/data_creation/experiment_data'


class Values(list):
    def __init__(self, values):
        super().__init__(values)
        self.snapshot = None

    def filter(self, *, snapshot):
        self.snapshot = snapshot
        return self

    def select_related(self, *args):
        return self

    def order_by(self, *args):
        return self


class AnnotationService:
    def __init__(self, annotation):
        self.annotation = annotation
        self.snapshots = []

    def list_page_v2(self, project, page, snapshot=None):
        self.snapshots.append(snapshot)
        descriptor = SimpleNamespace(annotation=self.annotation)
        occurrence = SimpleNamespace(annotations=(descriptor,))
        return SimpleNamespace(occurrences=(occurrence,))


def make_export(monkeypatch, snapshot=None, *, applicable=True, empty=False):
    page_model = SimpleNamespace(id=20)
    catalog_payload = {
        'sections': [
            {
                'id': 10,
                'uri': 'https://example.test/section',
                'title': 'Data',
                'pages': [
                    {
                        'id': 20,
                        'uri': 'https://example.test/page',
                        'title': 'Generation',
                        'elements': [
                            {
                                'id': 30,
                                'uri': 'https://example.test/question',
                                'text': 'Which terms apply?',
                                'attribute': 'https://example.test/attribute',
                            }
                        ],
                    }
                ],
            }
        ]
    }
    wrapper = SimpleNamespace(catalog=catalog_payload)
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.ProjectWrapper',
        lambda project, selected_snapshot: wrapper,
    )

    value_dicts = [
        {
            'id': 1,
            'collection_index': 0,
            'value_type': 'text',
            'text': 'Milk',
            'value_and_unit': 'Milk',
            'unit': '',
            'option_uri': None,
            'option_text': '',
            'external_id': ENTITY_IRI,
            'is_empty': False,
        },
        {
            'id': 2,
            'collection_index': 1,
            'value_type': 'text',
            'text': '',
            'value_and_unit': 'Field trials',
            'unit': '',
            'option_uri': OPTION_IRI,
            'option_text': 'Field trials',
            'external_id': '',
            'is_empty': False,
        },
        {
            'id': 3,
            'collection_index': 2,
            'value_type': 'text',
            'text': 'local-id',
            'value_and_unit': 'Unmatched provider value',
            'unit': '',
            'option_uri': None,
            'option_text': '',
            'external_id': 'local-id',
            'is_empty': False,
        },
        {
            'id': 4,
            'collection_index': 3,
            'value_type': 'text',
            'text': 'Own term',
            'value_and_unit': 'Own term',
            'unit': '',
            'option_uri': None,
            'option_text': '',
            'external_id': '',
            'is_empty': False,
        },
    ]
    if empty:
        for value_dict in value_dicts:
            value_dict['is_empty'] = True
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.view_tags.get_set_prefixes',
        lambda *args, **kwargs: [''],
    )
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.view_tags.get_set_indexes',
        lambda *args, **kwargs: [0],
    )
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.view_tags.check_element',
        lambda *args, **kwargs: applicable,
    )
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.view_tags.get_values',
        lambda *args, **kwargs: value_dicts,
    )
    monkeypatch.setattr(
        'rdmo_ts4nfdi.integrations.rdmo.exports.view_tags.get_labels',
        lambda *args, **kwargs: [],
    )

    catalog = SimpleNamespace(
        uri='https://example.test/catalog',
        pages=(page_model,),
        prefetch_elements=lambda: None,
    )
    values = Values(
        [
            SimpleNamespace(id=1, external_id=ENTITY_IRI),
            SimpleNamespace(id=2, external_id=''),
            SimpleNamespace(id=3, external_id='local-id'),
            SimpleNamespace(id=4, external_id=''),
        ]
    )
    project = SimpleNamespace(
        id=5,
        title='Ännotated project',
        description='Description',
        catalog=catalog,
        values=values,
        created=datetime(2026, 1, 1, tzinfo=timezone.utc),
        updated=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    annotation = AnnotationSummary(
        value_id=1,
        collection_index=0,
        matcher_id='food',
        kind='entity',
        label='Milk',
        iri=ENTITY_IRI,
        question_id=30,
        source=ResourceReference(id='tib', label='TIB'),
        terminology=ResourceReference(id='foodon', label='FOODON'),
    )
    service = AnnotationService(annotation)
    payload = RDMOAnnotatedAnswersBuilder(service).build(project, snapshot)
    return payload, values, service


def test_annotated_export_distinguishes_semantic_external_and_option_identity(monkeypatch):
    payload, _, _ = make_export(monkeypatch)
    values = payload['sections'][0]['pages'][0]['answers'][0]['values']

    assert payload['format'] == EXPORT_FORMAT
    assert payload['snapshot'] is None
    assert values[0]['external_id'] == ENTITY_IRI
    assert values[0]['annotation']['iri'] == ENTITY_IRI
    assert values[1]['option'] == {'uri': OPTION_IRI, 'label': 'Field trials'}
    assert values[1]['annotation'] is None
    assert values[2]['external_id'] == 'local-id'
    assert values[2]['annotation'] is None
    assert values[3]['external_id'] is None
    assert values[3]['option'] is None


def test_annotated_export_selects_snapshot_values(monkeypatch):
    snapshot = SimpleNamespace(
        id=9,
        title='Release',
        description='Frozen answers',
        created=datetime(2026, 2, 1, tzinfo=timezone.utc),
        updated=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    payload, values, service = make_export(monkeypatch, snapshot)

    assert payload['snapshot']['id'] == 9
    assert values.snapshot is snapshot
    assert service.snapshots == [snapshot]


def test_annotated_export_omits_inapplicable_and_empty_answers(monkeypatch):
    inapplicable, _, _ = make_export(monkeypatch, applicable=False)
    empty, _, _ = make_export(monkeypatch, empty=True)

    assert inapplicable['sections'] == []
    assert empty['sections'] == []


def test_json_and_xml_render_the_same_annotation_contract(monkeypatch):
    payload, _, _ = make_export(monkeypatch)

    json_payload = json.loads(render_annotated_json(payload))
    assert json_payload['project']['title'] == 'Ännotated project'
    assert (
        json_payload['sections'][0]['pages'][0]['answers'][0]['values'][0]['annotation']['iri']
        == ENTITY_IRI
    )

    root = ElementTree.fromstring(render_annotated_xml(payload))
    assert root.tag == 'annotated-answers'
    assert root.attrib['schema-version'] == '1'
    assert root.findtext('.//annotation/iri') == ENTITY_IRI
    assert root.find('.//value[@id="2"]/annotation') is None
    assert root.find('.//value[@id="2"]/option').attrib['uri'] == OPTION_IRI


def test_local_rdmo_option_is_not_an_annotation_identifier():
    option = SimpleNamespace(uri=OPTION_IRI)
    assert RDMOInterviewHost._value_identifier(
        SimpleNamespace(option=option, external_id='')
    ) is None
    assert RDMOInterviewHost._value_identifier(
        SimpleNamespace(option=option, external_id=ENTITY_IRI)
    ) == ENTITY_IRI
