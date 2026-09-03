# ruff: noqa: E402

import os
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import django
from django.template import Context, Engine

from rdmo.core import settings as rdmo_settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'rdmo.core.settings')
rdmo_settings.STATIC_ROOT = '/tmp/rdmo-ts4nfdi-test-static'
rdmo_settings.COMPRESS_ROOT = rdmo_settings.STATIC_ROOT
django.setup()

from rdmo_ts4nfdi.integrations.rdmo.interview import RDMOInterviewHost
from rdmo_ts4nfdi.templatetags import ts4nfdi_answer_tags

ROOT = Path(__file__).resolve().parents[1]
ENTITY_IRI = 'http://purl.obolibrary.org/obo/FOODON_03400740'
ONTOLOGY_IRI = 'https://example.test/ontology'


def annotation(value_id, kind, iri):
    return SimpleNamespace(value_id=value_id, kind=kind, iri=iri)


def test_answer_link_map_keeps_only_matched_http_entity_iris(monkeypatch):
    snapshot = SimpleNamespace(id=9)
    pages = (SimpleNamespace(id=1), SimpleNamespace(id=2))
    project = SimpleNamespace(catalog=SimpleNamespace(pages=pages))
    calls = []

    class Service:
        def list_page_v2(self, selected_project, page, snapshot=None):
            calls.append((selected_project, page, snapshot))
            annotations = {
                1: (
                    annotation(10, 'entity', ENTITY_IRI),
                    annotation(11, 'ontology', ONTOLOGY_IRI),
                ),
                2: (
                    annotation(12, 'entity', 'opaque-provider-id'),
                    annotation(13, 'entity', 'javascript:alert(1)'),
                ),
            }[page.id]
            descriptors = tuple(SimpleNamespace(annotation=item) for item in annotations)
            return SimpleNamespace(
                occurrences=(SimpleNamespace(annotations=descriptors),),
            )

    composition = types.ModuleType('rdmo_ts4nfdi.composition')
    composition.build_annotation_service = Service
    monkeypatch.setitem(sys.modules, 'rdmo_ts4nfdi.composition', composition)

    links = ts4nfdi_answer_tags.build_answer_link_map(project, snapshot)

    assert links == {10: ENTITY_IRI}
    assert calls == [
        (project, pages[0], snapshot),
        (project, pages[1], snapshot),
    ]


def test_answer_link_tag_falls_back_when_annotation_setup_fails(monkeypatch, caplog):
    project = SimpleNamespace(pk=42)

    def fail(*args, **kwargs):
        raise RuntimeError('invalid annotation configuration')

    monkeypatch.setattr(ts4nfdi_answer_tags, 'build_answer_link_map', fail)

    assert ts4nfdi_answer_tags.ts4nfdi_answer_links(project) == {}
    assert 'Could not build TS4NFDI answer links for project=42.' in caplog.text


def test_rdmo_host_reuses_loaded_values_for_multiple_pages():
    class Values:
        def __init__(self):
            self.filter_calls = []

        def filter(self, *, snapshot):
            self.filter_calls.append(snapshot)
            return self

        def select_related(self, *args):
            return self

        def order_by(self, *args):
            return [SimpleNamespace(id=1)]

    values = Values()
    project = SimpleNamespace(values=values)
    snapshot = SimpleNamespace(id=9)
    host = RDMOInterviewHost()

    first = host._project_values(project, snapshot)
    second = host._project_values(project, snapshot)

    assert first is second
    assert values.filter_calls == [snapshot]


def test_answer_tree_renders_label_and_visible_link(monkeypatch):
    value = {
        'id': 10,
        'set_prefix': '',
        'set_index': 0,
        'is_empty': False,
        'file_url': None,
        'value_and_unit': 'Milk',
    }

    class ProjectWrapper:
        catalog = {
            'sections': [
                {
                    'title': 'Section',
                    'pages': [
                        {
                            'title': 'Page',
                            'elements': [
                                {
                                    'text': 'Which concept?',
                                    'attribute': 'https://example.test/attribute',
                                    'ancestors': [],
                                    'conditions': [],
                                }
                            ],
                        }
                    ],
                }
            ]
        }

        def _get_values(self, *args, **kwargs):
            return [value]

        def _check_element(self, *args, **kwargs):
            return True

    monkeypatch.setattr(
        ts4nfdi_answer_tags,
        'build_answer_link_map',
        lambda project, snapshot=None: {10: ENTITY_IRI},
    )
    engine = Engine(
        dirs=[
            str(ROOT / 'rdmo_ts4nfdi' / 'templates'),
            str(ROOT / '.external_code' / 'rdmorganiser' / 'rdmo' / 'rdmo' / 'views' / 'templates'),
        ],
        libraries={
            'core_tags': 'rdmo.core.templatetags.core_tags',
            'i18n': 'django.templatetags.i18n',
            'view_tags': 'rdmo.views.templatetags.view_tags',
            'ts4nfdi_answer_tags': 'rdmo_ts4nfdi.templatetags.ts4nfdi_answer_tags',
        },
    )
    rendered = engine.get_template('projects/project_answers_tree.html').render(
        Context(
            {
                'project': SimpleNamespace(pk=42),
                'current_snapshot': None,
                'project_wrapper': ProjectWrapper(),
            }
        )
    )

    assert f'href="{ENTITY_IRI}"' in rendered
    assert '>Milk</a>' in rendered
    assert f'>{ENTITY_IRI}</a>' not in rendered
    assert 'Terminology IRI:' not in rendered


def test_answer_value_without_link_keeps_the_standard_rendering():
    engine = Engine(
        dirs=[
            str(ROOT / 'rdmo_ts4nfdi' / 'templates'),
            str(ROOT / '.external_code' / 'rdmorganiser' / 'rdmo' / 'rdmo' / 'views' / 'templates'),
        ],
        libraries={
            'ts4nfdi_answer_tags': 'rdmo_ts4nfdi.templatetags.ts4nfdi_answer_tags',
        },
    )
    rendered = engine.get_template('rdmo_ts4nfdi/answer_value.html').render(
        Context(
            {
                'value': {
                    'id': 20,
                    'file_url': None,
                    'value_and_unit': 'Own term',
                },
                'ts4nfdi_answer_link_map': {},
            }
        )
    )

    assert '<span>Own term</span>' in rendered
    assert 'Terminology IRI:' not in rendered
    assert '<a ' not in rendered
