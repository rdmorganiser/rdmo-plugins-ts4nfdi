import logging
from functools import cache

from django.conf import settings

from rdmo_ts4nfdi.utils import normalize_optional_string, require_string

logger = logging.getLogger(__name__)

ANNOTATION_RESOURCE_TYPES = frozenset({'entity', 'ontology', 'collection'})
ANNOTATION_ENTITY_TYPES = frozenset(
    {
        'term',
        'class',
        'property',
        'annotationProperty',
        'dataProperty',
        'objectProperty',
        'individual',
    }
)
ANNOTATION_TABS = frozenset(
    {
        'synonyms',
        'hierarchy',
        'crossref',
        'ontology',
        'graphview',
        'depiction',
        'entityinfo',
        'entityrelations',
    }
)
GATEWAY_PARAM_NAMES = frozenset(
    {
        'collectionId',
        'child',
        'database',
        'display',
        'exact',
        'exactMatch',
        'fieldList',
        'groupField',
        'includeObsoleteEntities',
        'iri',
        'lang',
        'obsoletes',
        'ontology',
        'ontologyId',
        'page',
        'q',
        'query',
        'queryFields',
        'rows',
        'search',
        'searchFields',
        'siblings',
        'size',
        'sort',
        'start',
        'type',
        'viewMode',
    }
)


@cache
def load_config():
    config = getattr(settings, 'TS4NFDI_PROVIDER', None)

    if config is None:
        raise RuntimeError('Missing TS4NFDI_PROVIDER setting.')

    if not isinstance(config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER must be a dictionary.')

    providers = config.get('providers', {})
    logger.debug(
        'Loaded TS4NFDI provider config with top-level keys=%s, provider keys=%s',
        sorted(config.keys()),
        sorted(providers.keys()) if isinstance(providers, dict) else providers,
    )

    return config


def load_gateway_config():
    config = load_config()
    defaults = config.get('defaults', {})
    gateway_config = config.get('gateway', {})

    if not isinstance(gateway_config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER gateway config must be a dictionary.')

    return {
        'base_url': gateway_config.get(
            'base_url',
            defaults.get(
                'base_url',
                'https://terminology.services.base4nfdi.de/api-gateway',
            ),
        ),
        'timeout': gateway_config.get('timeout', defaults.get('timeout', 10)),
        'cache_timeout': gateway_config.get('cache_timeout', 300),
        'api_token': gateway_config.get('api_token', defaults.get('api_token')),
    }


def load_annotation_matchers():
    frontend_config = _load_raw_frontend_config()
    annotations_config = frontend_config.get('annotations', {})

    if annotations_config in (None, False):
        return []
    if not isinstance(annotations_config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend annotations config must be a dictionary.')
    if not annotations_config.get('enabled', False):
        return []

    raw_matchers = annotations_config.get('matchers', [])
    if not isinstance(raw_matchers, list):
        raise RuntimeError('TS4NFDI_PROVIDER annotation matchers must be a list.')

    providers = load_config().get('providers', {})
    matchers = []
    matcher_ids = set()

    for index, raw_matcher in enumerate(raw_matchers):
        try:
            matcher = normalize_annotation_matcher(raw_matcher, index, providers)
        except RuntimeError as exc:
            logger.error('Ignoring invalid TS4NFDI annotation matcher at index %s: %s', index, exc)
            continue

        if matcher['id'] in matcher_ids:
            logger.error("Ignoring duplicate TS4NFDI annotation matcher id '%s'.", matcher['id'])
            continue

        matcher_ids.add(matcher['id'])
        matchers.append(matcher)

    return matchers


def normalize_annotation_matcher(raw_matcher, index, providers):
    if not isinstance(raw_matcher, dict):
        raise RuntimeError('matcher must be a dictionary')

    matcher_id = str(raw_matcher.get('id') or f'annotation-{index + 1}').strip()
    question_uri = require_string(raw_matcher, 'question_uri')
    attribute_uri = require_string(raw_matcher, 'attribute_uri')
    optionset_uri = require_string(raw_matcher, 'optionset_uri')
    resource_type = require_string(raw_matcher, 'resource_type')

    if resource_type not in ANNOTATION_RESOURCE_TYPES:
        raise RuntimeError(f'resource_type must be one of {sorted(ANNOTATION_RESOURCE_TYPES)}')

    provider_key = normalize_optional_string(raw_matcher.get('provider_key'))
    if resource_type in {'ontology', 'collection'}:
        if not provider_key:
            raise RuntimeError(f"provider_key is required for resource_type '{resource_type}'")
        if provider_key not in providers:
            raise RuntimeError(f"unknown provider_key '{provider_key}'")

    entity_type = normalize_optional_string(raw_matcher.get('entity_type'))
    if entity_type and entity_type not in ANNOTATION_ENTITY_TYPES:
        raise RuntimeError(f'entity_type must be one of {sorted(ANNOTATION_ENTITY_TYPES)}')

    tabs = raw_matcher.get('tabs', ['synonyms', 'hierarchy', 'ontology'])
    if not isinstance(tabs, list) or any(tab not in ANNOTATION_TABS for tab in tabs):
        raise RuntimeError(f'tabs must contain only {sorted(ANNOTATION_TABS)}')

    raw_gateway_params = raw_matcher.get('gateway_params', {})
    if not isinstance(raw_gateway_params, dict):
        raise RuntimeError('gateway_params must be a dictionary')
    gateway_params = {
        key: value
        for key, value in raw_gateway_params.items()
        if key in GATEWAY_PARAM_NAMES and value not in (None, '', [])
    }
    ignored_params = sorted(set(raw_gateway_params) - set(gateway_params))
    if ignored_params:
        logger.warning(
            "Ignoring unsupported Gateway parameters for matcher '%s': %s",
            matcher_id,
            ignored_params,
        )

    return {
        'id': matcher_id,
        'question_uri': question_uri,
        'attribute_uri': attribute_uri,
        'optionset_uri': optionset_uri,
        'resource_type': resource_type,
        'provider_key': provider_key,
        'badge_label': normalize_optional_string(raw_matcher.get('badge_label')),
        'entity_type': entity_type,
        'ontology_id': normalize_optional_string(raw_matcher.get('ontology_id')),
        'use_legacy': bool(raw_matcher.get('use_legacy', False)),
        'tabs': list(dict.fromkeys(tabs)),
        'gateway_params': gateway_params,
    }


def find_annotation_matcher(question, matchers=None):
    if matchers is None:
        matchers = load_annotation_matchers()

    if not question or not getattr(question, 'attribute', None):
        return None

    optionset_uris = {optionset.uri for optionset in question.optionsets.all()}

    for matcher in matchers:
        if (
            matcher['question_uri'] == question.uri
            and matcher['attribute_uri'] == question.attribute.uri
            and matcher['optionset_uri'] in optionset_uris
        ):
            return matcher

    return None


def load_frontend_config():
    frontend_config = dict(_load_raw_frontend_config())
    raw_annotations = frontend_config.get('annotations', {})
    if raw_annotations in (None, False):
        raw_annotations = {}
    if not isinstance(raw_annotations, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend annotations config must be a dictionary.')

    frontend_config['annotations'] = {
        'enabled': bool(raw_annotations.get('enabled', False)),
        'matchers': [
            {key: value for key, value in matcher.items() if key not in {'provider_key', 'gateway_params'}}
            for matcher in load_annotation_matchers()
        ],
    }

    return frontend_config


def _load_raw_frontend_config():
    config = load_config()
    frontend_config = config.get('frontend', {})

    if not isinstance(frontend_config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend config must be a dictionary.')

    logger.debug(
        'Loaded TS4NFDI frontend config with keys=%s',
        sorted(frontend_config.keys()),
    )
    return frontend_config
