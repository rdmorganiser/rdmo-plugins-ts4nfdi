import csv
import hashlib
import importlib
import json
import sys
import types
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]


def install_rdmo_stubs(monkeypatch):
    django = types.ModuleType('django')
    django_conf = types.ModuleType('django.conf')
    django_core = types.ModuleType('django.core')
    django_core_cache = types.ModuleType('django.core.cache')
    django_template = types.ModuleType('django.template')
    django_templatetags = types.ModuleType('django.templatetags')
    django_templatetags_static = types.ModuleType('django.templatetags.static')
    django_utils = types.ModuleType('django.utils')
    django_utils_translation = types.ModuleType('django.utils.translation')
    rdmo = types.ModuleType('rdmo')
    rdmo_options = types.ModuleType('rdmo.options')
    rdmo_options_providers = types.ModuleType('rdmo.options.providers')

    class Provider:
        pass

    class Settings:
        TS4NFDI_PROVIDER = {}

    class Cache:
        def get(self, key):
            return None

        def set(self, key, value, timeout):
            return None

    class Library:
        def simple_tag(self, function=None, **kwargs):
            if function:
                return function
            return lambda decorated: decorated

    django_conf.settings = Settings()
    django.conf = django_conf
    django.core = django_core
    django_core.cache = django_core_cache
    django.template = django_template
    django.templatetags = django_templatetags
    django.utils = django_utils
    django_core_cache.cache = Cache()
    django_template.Library = Library
    django_templatetags.static = django_templatetags_static
    django_templatetags_static.static = lambda path: f'/static/{path}'
    django_utils.translation = django_utils_translation
    django_utils_translation.get_language = lambda: 'en'
    rdmo.options = rdmo_options
    rdmo_options.providers = rdmo_options_providers
    rdmo_options_providers.Provider = Provider

    monkeypatch.setitem(sys.modules, 'django', django)
    monkeypatch.setitem(sys.modules, 'django.conf', django_conf)
    monkeypatch.setitem(sys.modules, 'django.core', django_core)
    monkeypatch.setitem(sys.modules, 'django.core.cache', django_core_cache)
    monkeypatch.setitem(sys.modules, 'django.template', django_template)
    monkeypatch.setitem(sys.modules, 'django.templatetags', django_templatetags)
    monkeypatch.setitem(sys.modules, 'django.templatetags.static', django_templatetags_static)
    monkeypatch.setitem(sys.modules, 'django.utils', django_utils)
    monkeypatch.setitem(sys.modules, 'django.utils.translation', django_utils_translation)
    monkeypatch.setitem(sys.modules, 'rdmo', rdmo)
    monkeypatch.setitem(sys.modules, 'rdmo.options', rdmo_options)
    monkeypatch.setitem(sys.modules, 'rdmo.options.providers', rdmo_options_providers)

    return django_conf.settings


@pytest.fixture(scope='module')
def provider_modules():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.syspath_prepend(str(ROOT))
    settings = install_rdmo_stubs(monkeypatch)
    config = None

    try:
        config = importlib.import_module('rdmo_ts4nfdi.config')
        providers = importlib.import_module('rdmo_ts4nfdi.providers')
        annotation_metadata = importlib.import_module('rdmo_ts4nfdi.integrations.ts4nfdi.metadata')
        gateway = importlib.import_module('rdmo_ts4nfdi.integrations.ts4nfdi.gateway')
        domain = importlib.import_module('rdmo_ts4nfdi.domain')
        template_tags = importlib.import_module('rdmo_ts4nfdi.templatetags.ts4nfdi_tags')
        upstream = importlib.import_module('rdmo_ts4nfdi.upstream')
        utils = importlib.import_module('rdmo_ts4nfdi.utils')
        yield types.SimpleNamespace(
            load_config=config.load_config,
            load_source_configs=config.load_source_configs,
            load_annotation_matchers=config.load_annotation_matchers,
            load_frontend_config=config.load_frontend_config,
            settings=settings,
            gateway=gateway,
            upstream=upstream,
            utils=utils,
            annotation_metadata=annotation_metadata,
            domain=domain,
            template_tags=template_tags,
            collection_terminologies_provider=providers.TS4NFDICollectionTerminologiesProvider,
            collections_provider=providers.TS4NFDICollectionsProvider,
            fairagro_data_generation_provider=providers.FAIRAgroDataGenerationOptionSetProvider,
            ontologies_provider=providers.TS4NFDIOntologiesProvider,
        )
    finally:
        if config is not None:
            config.load_config.cache_clear()
        for module_name in list(sys.modules):
            if module_name == 'rdmo_ts4nfdi' or module_name.startswith('rdmo_ts4nfdi.'):
                sys.modules.pop(module_name, None)
        monkeypatch.undo()


def configure_provider(provider_modules, key, provider_config, sources=None):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'defaults': {
            'base_url': 'https://example.test/api',
            'limit': 20,
        },
        'providers': {
            key: provider_config,
        },
    }
    if sources:
        provider_modules.settings.TS4NFDI_PROVIDER['sources'] = sources
    provider_modules.load_config.cache_clear()


def make_provider(provider_class, key, payload):
    provider = provider_class()
    provider.key = key
    provider.make_request = lambda search=None, provider_config=None: payload
    return provider


def test_ontology_provider_get_options_returns_mapped_options(provider_modules):
    key = 'ts4nfdi_ontologies'
    configure_provider(
        provider_modules,
        key,
        {
            'endpoint': 'search',
            'id_fields': ['iri'],
            'label_fields': ['label'],
            'help_fields': ['description'],
            'ontology_fields': ['ontology'],
            'ontologies': ['edam'],
            'iri_prefixes': ['http://edamontology.org/format_'],
        },
    )
    payload = {
        'response': {
            'docs': [
                {
                    'iri': 'http://edamontology.org/format_1915',
                    'label': 'JSON',
                    'description': 'JavaScript Object Notation',
                    'ontology': 'edam',
                },
                {
                    'iri': 'http://example.test/not-edam',
                    'label': 'Filtered out',
                    'ontology': 'other',
                },
            ],
        },
    }

    options = make_provider(provider_modules.ontologies_provider, key, payload).get_options(
        project=None,
        search='json',
    )

    assert options == [
        {
            'id': 'http://edamontology.org/format_1915',
            'text': 'JSON',
            'help': (
                '<span class="ts4nfdi-option-breadcrumb">'
                '<span class="ts4nfdi-option-badge ts4nfdi-option-badge--ontology">edam</span>'
                '</span>'
                '<span class="ts4nfdi-option-description">JavaScript Object Notation</span>'
            ),
        },
    ]


def test_ontology_provider_renders_source_terminology_term_breadcrumb(provider_modules):
    key = 'ts4nfdi_ontologies'
    configure_provider(
        provider_modules,
        key,
        {
            'endpoint': 'search',
            'source_key': 'ebi',
            'ontologies': ['edam'],
            'iri_prefixes': ['http://edamontology.org/format_'],
        },
        sources={
            'ebi': {
                'label': 'EBI',
                'database': 'ebi',
                'backend_type': 'ols2',
                'url': 'https://www.ebi.ac.uk/ols4/api/v2',
            },
        },
    )
    payload = [
        {
            'iri': 'http://edamontology.org/format_2332',
            'label': 'XML',
            'descriptions': ['eXtensible Markup Language format.'],
            'ontology': 'edam',
            'short_form': 'EDAM_format_2332',
            'source_name': 'ebi',
        },
    ]
    provider = make_provider(provider_modules.ontologies_provider, key, payload)

    options = provider.get_options(project=None, search='xml')
    provider_config = provider.get_provider_config()

    assert provider_config['database'] == 'ebi'
    assert provider_config['source']['label'] == 'EBI'
    assert options[0]['help'].index('>EBI</span>') < options[0]['help'].index('>edam</span>')
    assert options[0]['help'].index('>edam</span>') < options[0]['help'].index('>EDAM_format_2332</span>')
    assert 'https://www.ebi.ac.uk/ols4/api/v2' in options[0]['help']


def test_collections_provider_get_options_returns_mapped_collection_options(provider_modules):
    key = 'ts4nfdi_collections'
    configure_provider(
        provider_modules,
        key,
        {
            'endpoint': 'collections/',
            'id_fields': ['id'],
            'label_fields': ['label'],
            'uri_fields': ['iri', 'uri'],
            'permalink_base': 'https://w3id.org/ts4nfdi/collection/',
            'terminology_badge_limit': 2,
            'exclude_selected_collection_options': False,
        },
    )
    payload = {
        'collections': [
            {
                'id': 'collection-1',
                'label': 'NFDI metadata standards',
                'description': 'Relevant metadata standards',
                'creator': 'TS4NFDI',
                'isPublic': True,
                'terminologies': [
                    {'label': 'DataCite', 'source': 'base'},
                    {'label': 'Dublin Core'},
                ],
            },
            {
                'id': 'collection-2',
                'label': 'Other collection',
                'description': 'Does not match search',
            },
        ],
    }

    options = make_provider(provider_modules.collections_provider, key, payload).get_options(
        project=None,
        search='metadata',
    )

    assert len(options) == 1
    assert options[0]['id'] == 'https://w3id.org/ts4nfdi/collection/collection-1'
    assert options[0]['text'] == 'NFDI metadata standards'
    assert options[0]['uuid'] == 'collection-1'
    assert 'TS4NFDI' in options[0]['help']
    assert 'Terminologies: DataCite (base), Dublin Core' in options[0]['help']
    assert 'Relevant metadata standards' in options[0]['help']


def test_fairagro_data_generation_provider_uses_stable_option_ids_and_mapping_help(provider_modules):
    configure_provider(
        provider_modules,
        'fairagro_data_generation',
        {},
        sources={
            'agroportal': {
                'label': 'AgroPortal',
                'database': 'agroportal',
                'backend_type': 'ontoportal',
                'url': 'https://data.agroportal.eu',
            },
            'agrovoc': {
                'label': 'FAO AGROVOC service',
                'database': 'agrovoc',
                'backend_type': 'skosmos',
                'url': 'https://agrovoc.fao.org/browse/rest/v1',
            },
            'tib': {
                'label': 'TIB Terminology Service',
                'database': 'tib',
                'backend_type': 'ols2',
                'url': 'https://api.terminology.tib.eu/api/v2',
            },
        },
    )

    provider = provider_modules.fairagro_data_generation_provider()
    provider.key = 'fairagro_data_generation'
    options = provider.get_options(project=None)

    assert provider.search is False
    assert len(options) == 22
    assert options[0]['id'] == 'https://rdmo.fairagro.net/terms/options/data_creation/experiment_data'
    assert options[0]['text'] == 'Field trials'
    assert 'AgroPortal' in options[0]['help']
    assert 'INRAE Thesaurus' in options[0]['help']
    assert 'field experiment' in options[0]['help']
    unmapped = next(option for option in options if option['id'].endswith('/field_sampling'))
    assert 'No curated terminology mapping is available yet.' in unmapped['help']


def test_fairagro_data_generation_curator_csv_matches_deployed_manifest():
    csv_path = ROOT / 'docs/FAIRagro Options - data_generation.csv'
    manifest_path = ROOT / 'rdmo_ts4nfdi/data/semantic_option_sets/fairagro_data_generation.json'
    original_columns = [
        'TermDE',
        'TermEN',
        'TerminologyConceptURI',
        'TerminologyLabel',
        'TerminologyProvider',
        'Comment',
    ]
    added_columns = [
        'OptionID',
        'OptionURI',
        'OptionLabelDE',
        'OptionLabelEN',
        'Selectable',
        'TargetID',
        'TerminologyID',
        'SourceKey',
        'MappingRelation',
        'CurationStatus',
        'CompositionID',
        'CompositionOperator',
        'ComponentOrder',
        'ComponentRole',
    ]

    csv_bytes = csv_path.read_bytes()
    with csv_path.open(encoding='utf-8', newline='') as csv_file:
        title_row = next(csv.reader(csv_file))
        reader = csv.DictReader(csv_file)
        assert title_row[0].startswith('How does your project generate new data?')
        assert reader.fieldnames == original_columns + added_columns
        rows = list(reader)

    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    assert manifest['source_sha256'] == hashlib.sha256(csv_bytes).hexdigest()

    manifest_options = {option['uri']: option for option in manifest['options']}
    csv_option_uris = {row['OptionURI'] for row in rows}
    assert csv_option_uris <= set(manifest_options)

    option_columns = [
        'OptionID',
        'OptionURI',
        'OptionLabelDE',
        'OptionLabelEN',
        'Selectable',
    ]
    target_columns = [
        'TargetID',
        'TerminologyID',
        'SourceKey',
        'MappingRelation',
        'CurationStatus',
    ]
    composition_columns = [
        'CompositionID',
        'CompositionOperator',
        'ComponentOrder',
    ]

    for option_uri in csv_option_uris:
        option = manifest_options[option_uri]
        option_rows = [row for row in rows if row['OptionURI'] == option_uri]
        assert option_rows
        for column in option_columns:
            assert len({row[column] for row in option_rows}) == 1

        first_row = option_rows[0]
        assert first_row['OptionID'] == option['id']
        assert first_row['OptionLabelEN'] == option['labels']['en']
        assert first_row['OptionLabelDE'] == option['labels']['de']
        assert (first_row['Selectable'] == 'true') == option.get('selectable', True)

        csv_targets = {
            (
                row['TargetID'],
                row['TerminologyConceptURI'],
                row['TermEN'] or row['TermDE'],
                row['TerminologyID'],
                row['SourceKey'],
                row['MappingRelation'],
                row['CurationStatus'],
            )
            for row in option_rows
            if row['TargetID']
        }
        manifest_targets = {
            (
                target['id'],
                target['iri'],
                target['label'],
                target['terminology']['id'],
                target['source_key'],
                target['relation'],
                target.get('curation_status', 'draft'),
            )
            for target in option['targets']
        }
        assert csv_targets == manifest_targets

        for row in option_rows:
            if row['TargetID']:
                assert all(row[column] for column in target_columns)
                assert row['TerminologyConceptURI'] not in {'', '/'}
            else:
                assert not any(row[column] for column in target_columns)
                assert row['TerminologyConceptURI'] in {'', '/'}

            has_composition = any(row[column] for column in composition_columns)
            if has_composition:
                assert row['MappingRelation'] == 'component'
                assert all(row[column] for column in composition_columns)
                assert int(row['ComponentOrder']) > 0
            else:
                assert row['MappingRelation'] != 'component'


def test_collection_terminologies_provider_get_options_returns_collection_terms(provider_modules):
    key = 'ts4nfdi_collection_terminologies'
    configure_provider(
        provider_modules,
        key,
        {
            'endpoint': 'collections/collection-1/terminologies',
            'collection_id': 'collection-1',
            'collection_label': 'NFDI metadata standards',
            'id_fields': ['URI', 'uri'],
            'label_fields': ['config.title', 'label'],
            'help_fields': ['config.description'],
        },
    )
    payload = {
        'terminologies': [
            {
                'ontologyId': 'datacite',
                'URI': 'https://schema.datacite.org',
                'source': 'base',
                'type': 'ontology',
                'config': {
                    'title': 'DataCite Metadata Schema',
                    'description': 'Metadata schema for research data',
                    'version': '4.5',
                },
            },
            {
                'ontologyId': 'other',
                'URI': 'https://example.test/other',
                'config': {
                    'title': 'Other Terminology',
                },
            },
        ],
    }

    options = make_provider(
        provider_modules.collection_terminologies_provider,
        key,
        payload,
    ).get_options(project=None, search='datacite')

    assert len(options) == 1
    assert options[0]['id'] == 'https://schema.datacite.org'
    assert options[0]['text'] == 'DataCite Metadata Schema'
    assert options[0]['ontology_id'] == 'datacite'
    assert 'NFDI metadata standards' in options[0]['help']
    assert 'Metadata schema for research data' in options[0]['help']
    assert 'version: 4.5' in options[0]['help']


def test_annotation_config_is_validated_and_sanitized(provider_modules):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'providers': {
            'ts4nfdi_ontologies': {
                'endpoint': 'search',
            },
        },
        'frontend': {
            'annotations': {
                'enabled': True,
                'matchers': [
                    {
                        'id': 'valid',
                        'question_uri': 'https://example.test/question',
                        'attribute_uri': 'https://example.test/attribute',
                        'optionset_uri': 'https://example.test/optionset',
                        'resource_type': 'entity',
                        'mapping_set_id': 'example-mappings',
                        'presentation': {
                            'adapter': 'tss',
                            'component': 'entity-info',
                            'entity_type': 'class',
                        },
                        'provider_key': 'internal-provider-key',
                        'gateway_params': {
                            'database': 'ols',
                            'unsafe': 'ignored',
                        },
                    },
                    {
                        'id': 'invalid',
                        'question_uri': 'https://example.test/question',
                        'resource_type': 'unknown',
                    },
                ],
            },
        },
    }
    provider_modules.load_config.cache_clear()

    matchers = provider_modules.load_annotation_matchers()
    frontend_config = provider_modules.load_frontend_config()

    assert len(matchers) == 1
    assert matchers[0].id == 'valid'
    assert matchers[0].presentation.adapter == 'tss'
    assert matchers[0].presentation.component == 'entity-info'
    assert matchers[0].mapping_set_id == 'example-mappings'
    assert matchers[0].gateway_query == (('database', 'ols'),)
    assert frontend_config == {
        'annotations': {
            'api_version': '1',
            'enabled': True,
        },
        'presentation_adapters': [],
    }


def test_custom_frontend_presentation_adapter_config_is_normalized(provider_modules):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'providers': {},
        'frontend': {
            'presentation_adapters': {
                'fairagro-concept-card': {
                    'static_path': 'fairagro/js/ts4nfdi_concept_card.js',
                    'export': 'createConceptCard',
                },
            },
        },
    }
    provider_modules.load_config.cache_clear()

    assert provider_modules.load_frontend_config()['presentation_adapters'] == [
        {
            'name': 'fairagro-concept-card',
            'static_path': 'fairagro/js/ts4nfdi_concept_card.js',
            'export': 'createConceptCard',
        }
    ]


def test_frontend_template_config_resolves_custom_adapter_static_url(provider_modules):
    config = {
        'annotations': {
            'api_version': '1',
            'enabled': True,
        },
        'presentation_adapters': [
            {
                'name': 'fairagro-concept-card',
                'static_path': 'fairagro/js/ts4nfdi_concept_card.js',
                'export': 'createConceptCard',
            }
        ],
    }

    with mock.patch.object(
        provider_modules.template_tags,
        'load_frontend_config',
        return_value=config,
    ):
        resolved = provider_modules.template_tags.ts4nfdi_frontend_config()

    assert resolved == {
        'annotations': {
            'api_version': '1',
            'enabled': True,
        },
        'presentation_adapters': [
            {
                'name': 'fairagro-concept-card',
                'module_url': '/static/fairagro/js/ts4nfdi_concept_card.js',
                'export': 'createConceptCard',
            }
        ],
    }


def test_custom_matcher_requires_a_registered_frontend_adapter(provider_modules):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'providers': {},
        'frontend': {
            'annotations': {
                'enabled': True,
                'matchers': [
                    {
                        'id': 'custom',
                        'question_uri': 'https://example.test/question',
                        'attribute_uri': 'https://example.test/attribute',
                        'optionset_uri': 'https://example.test/optionset',
                        'resource_type': 'entity',
                        'presentation': {
                            'adapter': 'missing-concept-card',
                        },
                    },
                ],
            },
        },
    }
    provider_modules.load_config.cache_clear()

    with pytest.raises(RuntimeError, match='unregistered frontend presentation adapters'):
        provider_modules.load_frontend_config()


@pytest.mark.parametrize(
    'adapter_config',
    (
        {'tss': {'static_path': 'deployment/tss.js'}},
        {'custom': {'static_path': '../outside.js'}},
        {'custom': {'static_path': 'https://example.test/widget.js'}},
        {'custom': {'static_path': 'deployment/widget.css'}},
        {'custom': {'static_path': 'deployment/widget.js', 'unexpected': True}},
    ),
)
def test_invalid_custom_frontend_presentation_adapter_config_fails(
    provider_modules,
    adapter_config,
):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'providers': {},
        'frontend': {
            'presentation_adapters': adapter_config,
        },
    }
    provider_modules.load_config.cache_clear()

    with pytest.raises(RuntimeError):
        provider_modules.load_frontend_config()


def test_annotation_source_config_supplies_gateway_database(provider_modules):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        'sources': {
            'ebi': {
                'label': 'EBI',
                'database': 'ebi',
                'backend_type': 'ols2',
                'url': 'https://www.ebi.ac.uk/ols4/api/v2',
            },
        },
        'providers': {},
        'frontend': {
            'annotations': {
                'enabled': True,
                'matchers': [
                    {
                        'id': 'edam-format',
                        'question_uri': 'https://example.test/question',
                        'attribute_uri': 'https://example.test/attribute',
                        'optionset_uri': 'https://example.test/optionset',
                        'resource_type': 'entity',
                        'source_key': 'ebi',
                        'ontology_id': 'edam',
                    },
                ],
            },
        },
    }
    provider_modules.load_config.cache_clear()

    matcher = provider_modules.load_annotation_matchers()[0]

    assert matcher.gateway_query == (('database', 'ebi'),)
    assert matcher.source == provider_modules.domain.ResourceReference(
        id='ebi',
        label='EBI',
        database='ebi',
        backend_type='ols2',
        url='https://www.ebi.ac.uk/ols4/api/v2',
    )


def test_entity_metadata_normalizes_gateway_fields(provider_modules):
    metadata = provider_modules.annotation_metadata.normalize_entity_metadata(
        {
            'iri': 'http://edamontology.org/format_2332',
            'label': 'XML',
            'shortForm': 'EDAM_format_2332',
            'ontologyId': 'edam',
            'ontologyIri': 'http://edamontology.org',
            'definition': ['First definition.', 'Second definition.'],
            'synonym': ['eXtensible Markup Language'],
            'type': ['class'],
            'isObsolete': False,
        },
        provider_modules.domain.AnnotationMatcher(
            id='edam-format',
            question_uri='https://example.test/question',
            attribute_uri='https://example.test/attribute',
            optionset_uri='https://example.test/optionset',
            resource_type='entity',
            presentation=provider_modules.domain.PresentationPolicy(
                adapter='tss',
                component='entity-info',
            ),
            badge_label='EDAM',
            ontology_id='edam',
            source=provider_modules.domain.ResourceReference(
                id='ebi',
                label='EBI',
                database='ebi',
                backend_type='ols2',
                url='https://www.ebi.ac.uk/ols4/api/v2',
            ),
        ),
    )

    assert metadata.description == 'First definition.'
    assert metadata.definitions == ('First definition.', 'Second definition.')
    assert metadata.synonyms == ('eXtensible Markup Language',)
    assert metadata.short_form == 'EDAM_format_2332'
    assert metadata.entity_types == ('class',)
    assert metadata.obsolete is False
    assert metadata.source.label == 'EBI'
    assert metadata.terminology == provider_modules.domain.ResourceReference(
        id='edam',
        label='EDAM',
        iri='http://edamontology.org',
    )


def make_skosmos_annotation_context(provider_modules):
    concept_iri = 'http://aims.fao.org/aos/agrovoc/c_7156'
    matcher = provider_modules.domain.AnnotationMatcher(
        id='agrovoc-keyword',
        question_uri='https://example.test/question',
        attribute_uri='https://example.test/attribute',
        optionset_uri='https://example.test/optionset',
        resource_type='entity',
        presentation=provider_modules.domain.PresentationPolicy(adapter='native'),
        badge_label='AGROVOC',
        ontology_id='agrovoc',
        source=provider_modules.domain.ResourceReference(
            id='agrovoc',
            label='FAO AGROVOC service',
            database='agrovoc',
            backend_type='skosmos',
            url='https://agrovoc.fao.org/browse/rest/v1',
        ),
        gateway_params=(('database', 'agrovoc'),),
    )
    candidate = provider_modules.domain.AnnotationCandidate(
        question=provider_modules.domain.QuestionContext(
            question_id=1,
            question_uri=matcher.question_uri,
            attribute_id=2,
            attribute_uri=matcher.attribute_uri,
            optionset_uris=(matcher.optionset_uri,),
        ),
        value_id=3,
        label='soil',
        iri=concept_iri,
        set_prefix='',
        set_index=0,
        collection_index=0,
    )
    return matcher, candidate


def test_skosmos_entity_metadata_uses_gateway_artefact_concept_details(provider_modules):
    matcher, candidate = make_skosmos_annotation_context(provider_modules)

    class Gateway:
        def __init__(self):
            self.calls = []

        def get(self, path, query=None):
            self.calls.append((path, query))
            return (
                {
                    'iri': candidate.iri,
                    'label': 'soil',
                    'descriptions': ['The unconsolidated material on the immediate surface of the earth.'],
                    'synonyms': ['earth'],
                    'short_form': 'c_7156',
                    'ontology': 'agrovoc',
                    'ontology_iri': 'http://aims.fao.org/aos/agrovoc',
                    'source': 'https://agrovoc.fao.org/browse/rest/v1',
                    'source_name': 'agrovoc',
                    'backend_type': 'skosmos',
                    'type': 'skos:Concept',
                },
                False,
            )

    gateway = Gateway()
    metadata = provider_modules.annotation_metadata.GatewayMetadataResolver(gateway).resolve(
        candidate,
        matcher,
    )

    assert gateway.calls[0][0] == (
        'artefacts/agrovoc/resources/concepts/http%3A%2F%2Faims.fao.org%2Faos%2Fagrovoc%2Fc_7156'
    )
    query = dict(gateway.calls[0][1])
    assert query['database'] == 'agrovoc'
    assert metadata.label == 'soil'
    assert metadata.description.startswith('The unconsolidated material')
    assert metadata.synonyms == ('earth',)
    assert metadata.short_form == 'c_7156'
    assert metadata.ontology_id == 'agrovoc'
    assert metadata.source.label == 'FAO AGROVOC service'
    assert metadata.source.backend_type == 'skosmos'
    assert metadata.terminology == provider_modules.domain.ResourceReference(
        id='agrovoc',
        label='AGROVOC',
        iri='http://aims.fao.org/aos/agrovoc',
    )


def test_skosmos_entity_metadata_falls_back_to_gateway_search(provider_modules):
    matcher, candidate = make_skosmos_annotation_context(provider_modules)

    class Gateway:
        def __init__(self):
            self.calls = []

        def get(self, path, query=None):
            self.calls.append((path, query))
            if path.startswith('artefacts/'):
                raise provider_modules.gateway.GatewayError('Concept details unavailable.')
            return (
                [
                    {
                        'iri': candidate.iri,
                        'label': 'soil',
                        'descriptions': [],
                        'synonyms': [],
                        'short_form': 'c_7156',
                        'ontology': 'agrovoc',
                        'source': 'https://agrovoc.fao.org/browse/rest/v1',
                        'source_name': 'agrovoc',
                        'backend_type': 'skosmos',
                        'type': 'skos:Concept',
                    },
                ],
                False,
            )

    gateway = Gateway()
    metadata = provider_modules.annotation_metadata.GatewayMetadataResolver(gateway).resolve(
        candidate,
        matcher,
    )

    assert [call[0] for call in gateway.calls] == [
        ('artefacts/agrovoc/resources/concepts/http%3A%2F%2Faims.fao.org%2Faos%2Fagrovoc%2Fc_7156'),
        'search',
    ]
    fallback_query = dict(gateway.calls[1][1])
    assert fallback_query['query'] == 'soil'
    assert fallback_query['database'] == 'agrovoc'
    assert 'descriptions' in fallback_query['display']
    assert 'synonyms' in fallback_query['display']
    assert metadata.label == 'soil'
    assert metadata.description is None
    assert metadata.synonyms == ()


def test_gateway_path_and_query_allowlists(provider_modules):
    gateway = provider_modules.gateway

    assert gateway.validate_gateway_path('ols4/api/v2/entities') == 'ols4/api/v2/entities'
    concept_path = 'artefacts/agrovoc/resources/concepts/http%3A%2F%2Faims.fao.org%2Faos%2Fagrovoc%2Fc_7156'
    assert gateway.validate_gateway_path(concept_path) == concept_path

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('ols4/api/../../auth/me')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('auth/me')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('ols4/api/v2/ontologies/%252e%252e/auth')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('artefacts/agrovoc/resources/concepts')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('artefacts/agrovoc/resources/properties/example')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('artefacts/%252e%252e/resources/concepts/example')

    with pytest.raises(gateway.GatewayRequestError):
        gateway.validate_gateway_path('artefacts/agrovoc/resources/concepts/example?token=secret')

    class QueryParams(dict):
        def getlist(self, key):
            return self[key]

    filtered = gateway.filter_gateway_query(
        QueryParams(
            {
                'iri': ['https://example.test/entity'],
                'database': ['ols'],
                'token': ['secret'],
            }
        )
    )

    assert filtered == [
        ('iri', 'https://example.test/entity'),
        ('database', 'ols'),
    ]


def test_shared_string_and_iri_utilities(provider_modules):
    utils = provider_modules.utils

    assert utils.normalize_optional_string('  EDAM  ') == 'EDAM'
    assert utils.normalize_optional_string('  ') is None
    assert utils.require_string({'key': ' value '}, 'key') == 'value'
    assert utils.is_http_iri('https://example.test/terms/1') is True
    assert utils.is_http_iri('javascript:alert(1)') is False

    with pytest.raises(RuntimeError, match='key is required'):
        utils.require_string({}, 'key')


def test_vendored_tss_assets_match_manifest(provider_modules):
    manifest = provider_modules.upstream.read_manifest()

    assert manifest['package'] == '@ts4nfdi/terminology-service-suite-js'
    assert manifest['version']
    assert provider_modules.upstream.run_vendor_action(check=True) == [
        f'Vendored TSS {manifest["version"]}: local assets verified.'
    ]


def test_example_catalog_contains_data_format_annotation_question():
    catalog_path = ROOT / 'xml/rdmo-plugins-ts4nfdi-example-catalog.xml'
    root = ElementTree.parse(catalog_path).getroot()
    uri_attribute = '{http://purl.org/dc/elements/1.1/}uri'
    base_uri = 'https://ts4nfdi.github.io/terms/questions/rdmo-plugins-ts4nfdi-example-catalog'

    elements = {element.get(uri_attribute): element for element in root if element.get(uri_attribute)}
    page = elements[f'{base_uri}/technical-data-description']
    question = elements[f'{base_uri}/data-formats']

    assert page.findtext('is_collection') == 'True'
    assert page.find('questions/question').get(uri_attribute) == f'{base_uri}/data-formats'
    assert question.findtext('is_collection') == 'True'
    assert question.findtext("text[@lang='en']") == 'Which data formats arise in your project?'
    assert question.find('attribute').get(uri_attribute) == (
        'https://rdmorganiser.github.io/terms/domain/project/dataset/format'
    )
    assert question.find('optionsets/optionset').get(uri_attribute) == (
        'https://rdmo.fairagro.net/terms/options/file_format_ts4nfdi'
    )


def test_example_catalog_contains_controlled_agrovoc_keyword_question():
    catalog_path = ROOT / 'xml/rdmo-plugins-ts4nfdi-example-catalog.xml'
    root = ElementTree.parse(catalog_path).getroot()
    uri_attribute = '{http://purl.org/dc/elements/1.1/}uri'
    base_uri = 'https://ts4nfdi.github.io/terms/questions/rdmo-plugins-ts4nfdi-example-catalog'
    attribute_uri = 'https://ts4nfdi.github.io/domain/rdmo-plugins-ts4nfdi/dataset-keywords'
    optionset_uri = 'https://ts4nfdi.github.io/terms/options/rdmo-plugins-ts4nfdi/agrovoc-keywords'

    elements = {element.get(uri_attribute): element for element in root if element.get(uri_attribute)}
    section = elements[f'{base_uri}/section']
    page = elements[f'{base_uri}/dataset-topics-and-keywords']
    question = elements[f'{base_uri}/dataset-keywords']
    attribute = elements[attribute_uri]
    optionset = elements[optionset_uri]

    assert section.find("pages/page[@order='3']").get(uri_attribute) == (f'{base_uri}/dataset-topics-and-keywords')
    assert page.find('questions/question').get(uri_attribute) == f'{base_uri}/dataset-keywords'
    assert question.findtext('is_collection') == 'True'
    assert question.findtext('is_optional') == 'True'
    assert question.findtext('widget_type') == 'select_creatable'
    assert question.findtext('value_type') == 'option'
    assert question.find('attribute').get(uri_attribute) == attribute_uri
    assert question.find('optionsets/optionset').get(uri_attribute) == optionset_uri
    assert attribute.findtext('key') == 'dataset-keywords'
    assert optionset.findtext('provider_key') == 'ts4nfdi_agrovoc_keywords'


def test_example_catalog_explains_first_page_resource_levels():
    catalog_path = ROOT / 'xml/rdmo-plugins-ts4nfdi-example-catalog.xml'
    root = ElementTree.parse(catalog_path).getroot()
    uri_attribute = '{http://purl.org/dc/elements/1.1/}uri'
    base_uri = 'https://ts4nfdi.github.io/terms/questions/rdmo-plugins-ts4nfdi-example-catalog'
    elements = {element.get(uri_attribute): element for element in root if element.get(uri_attribute)}

    page = elements[f'{base_uri}/page']
    concept_question = elements[f'{base_uri}/ontologies']
    collection_question = elements[f'{base_uri}/collections']
    terminology_question = elements[f'{base_uri}/collection-terminologies']
    question_references = page.findall('questions/question')

    assert page.findtext("title[@lang='en']") == 'Terminology providers and annotations'
    assert page.find('questionsets') is not None
    assert len(page.find('questionsets')) == 0
    assert [reference.get(uri_attribute) for reference in question_references] == [
        f'{base_uri}/ontologies',
        f'{base_uri}/collections',
        f'{base_uri}/collection-terminologies',
    ]
    assert concept_question.findtext("text[@lang='en']") == 'EDAM terminology concepts'
    assert 'concept' in concept_question.findtext("help[@lang='en']")
    assert collection_question.findtext("text[@lang='en']") == 'Terminology collections'
    assert terminology_question.findtext("text[@lang='en']") == (
        'Terminologies from the preselected FAIRagro TS collection'
    )
    terminology_help = terminology_question.findtext("help[@lang='en']")
    assert 'ff5491d1-d0a9-481e-ac90-0fad065fa097' in terminology_help
    assert 'do not change this search scope' in terminology_help


def test_example_catalog_first_page_has_annotation_matchers():
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip('tomllib is part of Python 3.11 and newer')

    config_path = ROOT / 'ts4nfdi_provider.toml'
    config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    matchers = {matcher['id']: matcher for matcher in config['frontend']['annotations']['matchers']}

    concept = matchers['example-edam-concept']
    assert concept['resource_type'] == 'entity'
    assert concept['presentation']['adapter'] == 'tss'
    assert concept['presentation']['component'] == 'entity-info'

    collection = matchers['example-collection']
    assert collection['resource_type'] == 'collection'
    assert collection['provider_key'] == 'ts4nfdi_collections'
    assert collection['presentation']['adapter'] == 'native'

    terminology = matchers['example-fairagro-collection-terminology']
    assert terminology['resource_type'] == 'ontology'
    assert terminology['provider_key'] == 'ts4nfdi_fairagro_collection_terminologies'
    assert terminology['badge_label'] == 'FAIRagro TS collection'
    assert terminology['gateway_params']['collectionId'] == ('ff5491d1-d0a9-481e-ac90-0fad065fa097')
    assert terminology['presentation']['component'] == 'ontology-info'


def test_example_catalog_agrovoc_provider_and_annotation_matcher():
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip('tomllib is part of Python 3.11 and newer')

    config_path = ROOT / 'ts4nfdi_provider.toml'
    config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    provider = config['providers']['ts4nfdi_agrovoc_keywords']
    source = config['sources']['agrovoc']
    matchers = {matcher['id']: matcher for matcher in config['frontend']['annotations']['matchers']}
    matcher = matchers['example-agrovoc-keyword']

    assert provider['endpoint'] == 'search'
    assert provider['source_key'] == 'agrovoc'
    assert provider['ontologies'] == ['agrovoc']
    assert provider['iri_prefixes'] == ['http://aims.fao.org/aos/agrovoc/']
    assert source['database'] == 'agrovoc'
    assert source['backend_type'] == 'skosmos'
    assert matcher['resource_type'] == 'entity'
    assert matcher['source_key'] == 'agrovoc'
    assert matcher['ontology_id'] == 'agrovoc'
    assert matcher['presentation']['adapter'] == 'native'


def test_example_catalog_contains_provider_backed_fairagro_data_generation_question_set():
    catalog_path = ROOT / 'xml/rdmo-plugins-ts4nfdi-example-catalog.xml'
    root = ElementTree.parse(catalog_path).getroot()
    uri_attribute = '{http://purl.org/dc/elements/1.1/}uri'
    base_uri = 'https://ts4nfdi.github.io/terms/questions/rdmo-plugins-ts4nfdi-example-catalog'
    optionset_uri = 'https://ts4nfdi.github.io/terms/options/rdmo-plugins-ts4nfdi/fairagro-data-generation'
    elements = {element.get(uri_attribute): element for element in root if element.get(uri_attribute)}

    section = elements[f'{base_uri}/section']
    page = elements[f'{base_uri}/data-generation']
    questionset = elements[f'{base_uri}/data-generation/questions']
    methods = elements[f'{base_uri}/data-generation-methods']
    details = elements[f'{base_uri}/data-generation-details']
    optionset = elements[optionset_uri]

    assert section.find("pages/page[@order='4']").get(uri_attribute) == f'{base_uri}/data-generation'
    assert page.find('questionsets/questionset').get(uri_attribute) == f'{base_uri}/data-generation/questions'
    assert questionset.findtext('is_collection') == 'False'
    assert [question.get(uri_attribute) for question in questionset.findall('questions/question')] == [
        f'{base_uri}/data-generation-methods',
        f'{base_uri}/data-generation-details',
    ]
    assert methods.findtext('is_collection') == 'True'
    assert methods.findtext('widget_type') == 'select_creatable'
    assert methods.find('attribute').get(uri_attribute) == (
        'https://rdmorganiser.github.io/terms/domain/project/dataset/creation_methods'
    )
    assert methods.find('optionsets/optionset').get(uri_attribute) == optionset_uri
    assert details.findtext('widget_type') == 'textarea'
    assert details.findtext('is_optional') == 'True'
    assert optionset.findtext('provider_key') == 'fairagro_data_generation'


def test_fairagro_data_generation_annotation_matcher_uses_semantic_mapping_set():
    try:
        import tomllib
    except ModuleNotFoundError:
        pytest.skip('tomllib is part of Python 3.11 and newer')

    config_path = ROOT / 'ts4nfdi_provider.toml'
    config = tomllib.loads(config_path.read_text(encoding='utf-8'))
    matchers = {matcher['id']: matcher for matcher in config['frontend']['annotations']['matchers']}
    matcher = matchers['example-fairagro-data-generation']

    assert matcher['mapping_set_id'] == 'fairagro-data-generation'
    assert matcher['resource_type'] == 'entity'
    assert matcher['presentation']['adapter'] == 'native'
    assert matcher['optionset_uri'] == (
        'https://ts4nfdi.github.io/terms/options/rdmo-plugins-ts4nfdi/fairagro-data-generation'
    )
    assert config['sources']['agroportal']['database'] == 'agroportal'
    assert config['sources']['tib']['database'] == 'tib'
