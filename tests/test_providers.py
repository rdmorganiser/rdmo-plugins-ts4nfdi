import importlib
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def install_rdmo_stubs(monkeypatch):
    django = types.ModuleType("django")
    django_conf = types.ModuleType("django.conf")
    rdmo = types.ModuleType("rdmo")
    rdmo_options = types.ModuleType("rdmo.options")
    rdmo_options_providers = types.ModuleType("rdmo.options.providers")

    class Provider:
        pass

    class Settings:
        TS4NFDI_PROVIDER = {}

    django_conf.settings = Settings()
    django.conf = django_conf
    rdmo.options = rdmo_options
    rdmo_options.providers = rdmo_options_providers
    rdmo_options_providers.Provider = Provider

    monkeypatch.setitem(sys.modules, "django", django)
    monkeypatch.setitem(sys.modules, "django.conf", django_conf)
    monkeypatch.setitem(sys.modules, "rdmo", rdmo)
    monkeypatch.setitem(sys.modules, "rdmo.options", rdmo_options)
    monkeypatch.setitem(sys.modules, "rdmo.options.providers", rdmo_options_providers)

    return django_conf.settings


@pytest.fixture(scope="module")
def provider_modules():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.syspath_prepend(str(ROOT))
    settings = install_rdmo_stubs(monkeypatch)
    config = None

    try:
        config = importlib.import_module("rdmo_ts4nfdi.config")
        providers = importlib.import_module("rdmo_ts4nfdi.providers")
        yield types.SimpleNamespace(
            load_config=config.load_config,
            settings=settings,
            collection_terminologies_provider=providers.TS4NFDICollectionTerminologiesProvider,
            collections_provider=providers.TS4NFDICollectionsProvider,
            ontologies_provider=providers.TS4NFDIOntologiesProvider,
        )
    finally:
        if config is not None:
            config.load_config.cache_clear()
        for module_name in list(sys.modules):
            if module_name == "rdmo_ts4nfdi" or module_name.startswith("rdmo_ts4nfdi."):
                sys.modules.pop(module_name, None)
        monkeypatch.undo()


def configure_provider(provider_modules, key, provider_config):
    provider_modules.settings.TS4NFDI_PROVIDER = {
        "defaults": {
            "base_url": "https://example.test/api",
            "dedupe_fields": ["id"],
            "limit": 20,
        },
        "providers": {
            key: provider_config,
        },
    }
    provider_modules.load_config.cache_clear()


def make_provider(provider_class, key, payload):
    provider = provider_class()
    provider.key = key
    provider.make_request = lambda search=None, provider_config=None: payload
    return provider


def test_ontology_provider_get_options_returns_mapped_options(provider_modules):
    key = "ts4nfdi_ontologies"
    configure_provider(
        provider_modules,
        key,
        {
            "endpoint": "search",
            "id_fields": ["iri"],
            "label_fields": ["label"],
            "help_fields": ["description"],
            "ontology_fields": ["ontology"],
            "ontologies": ["edam"],
            "iri_prefixes": ["http://edamontology.org/format_"],
        },
    )
    payload = {
        "response": {
            "docs": [
                {
                    "iri": "http://edamontology.org/format_1915",
                    "label": "JSON",
                    "description": "JavaScript Object Notation",
                    "ontology": "edam",
                },
                {
                    "iri": "http://example.test/not-edam",
                    "label": "Filtered out",
                    "ontology": "other",
                },
            ],
        },
    }

    options = make_provider(provider_modules.ontologies_provider, key, payload).get_options(
        project=None,
        search="json",
    )

    assert options == [
        {
            "id": "http://edamontology.org/format_1915",
            "text": "JSON",
            "help": (
                '<span class="ts4nfdi-option-breadcrumb">'
                '<span class="ts4nfdi-option-badge ts4nfdi-option-badge--ontology">edam</span>'
                "</span>"
                '<span class="ts4nfdi-option-description">JavaScript Object Notation</span>'
            ),
        },
    ]


def test_collections_provider_get_options_returns_mapped_collection_options(provider_modules):
    key = "ts4nfdi_collections"
    configure_provider(
        provider_modules,
        key,
        {
            "endpoint": "collections/",
            "id_fields": ["id"],
            "label_fields": ["label"],
            "uri_fields": ["iri", "uri"],
            "permalink_base": "https://w3id.org/ts4nfdi/collection/",
            "terminology_badge_limit": 2,
            "exclude_selected_collection_options": False,
        },
    )
    payload = {
        "collections": [
            {
                "id": "collection-1",
                "label": "NFDI metadata standards",
                "description": "Relevant metadata standards",
                "creator": "TS4NFDI",
                "isPublic": True,
                "terminologies": [
                    {"label": "DataCite", "source": "base"},
                    {"label": "Dublin Core"},
                ],
            },
            {
                "id": "collection-2",
                "label": "Other collection",
                "description": "Does not match search",
            },
        ],
    }

    options = make_provider(provider_modules.collections_provider, key, payload).get_options(
        project=None,
        search="metadata",
    )

    assert len(options) == 1
    assert options[0]["id"] == "https://w3id.org/ts4nfdi/collection/collection-1"
    assert options[0]["text"] == "NFDI metadata standards"
    assert options[0]["uuid"] == "collection-1"
    assert "TS4NFDI" in options[0]["help"]
    assert "Terminologies: DataCite (base), Dublin Core" in options[0]["help"]
    assert "Relevant metadata standards" in options[0]["help"]


def test_collection_terminologies_provider_get_options_returns_collection_terms(provider_modules):
    key = "ts4nfdi_collection_terminologies"
    configure_provider(
        provider_modules,
        key,
        {
            "endpoint": "collections/collection-1/terminologies",
            "collection_id": "collection-1",
            "collection_label": "NFDI metadata standards",
            "id_fields": ["URI", "uri"],
            "label_fields": ["config.title", "label"],
            "help_fields": ["config.description"],
        },
    )
    payload = {
        "terminologies": [
            {
                "ontologyId": "datacite",
                "URI": "https://schema.datacite.org",
                "source": "base",
                "type": "ontology",
                "config": {
                    "title": "DataCite Metadata Schema",
                    "description": "Metadata schema for research data",
                    "version": "4.5",
                },
            },
            {
                "ontologyId": "other",
                "URI": "https://example.test/other",
                "config": {
                    "title": "Other Terminology",
                },
            },
        ],
    }

    options = make_provider(
        provider_modules.collection_terminologies_provider,
        key,
        payload,
    ).get_options(project=None, search="datacite")

    assert len(options) == 1
    assert options[0]["id"] == "https://schema.datacite.org"
    assert options[0]["text"] == "DataCite Metadata Schema"
    assert options[0]["ontology_id"] == "datacite"
    assert "NFDI metadata standards" in options[0]["help"]
    assert "Metadata schema for research data" in options[0]["help"]
    assert "version: 4.5" in options[0]["help"]
