import logging
import re
from functools import cache
from typing import Any

from django.conf import settings

from rdmo_ts4nfdi.domain import AnnotationMatcher, PresentationPolicy, ResourceReference
from rdmo_ts4nfdi.utils import is_http_iri, normalize_optional_string, require_string

logger = logging.getLogger(__name__)

ANNOTATION_RESOURCE_TYPES = frozenset({'entity', 'ontology', 'collection'})
ANNOTATION_PRESENTATIONS = {
    'entity': frozenset({'metadata', 'entity-info'}),
    'ontology': frozenset({'ontology-info'}),
    'collection': frozenset(),
}
DEFAULT_ANNOTATION_PRESENTATIONS = {
    'entity': PresentationPolicy(
        adapter='tss',
        component='metadata',
        options=(('tabs', ('synonyms', 'hierarchy', 'ontology')),),
    ),
    'ontology': PresentationPolicy(adapter='tss', component='ontology-info'),
    'collection': PresentationPolicy(adapter='native'),
}
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
def load_config() -> dict[str, Any]:
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


def load_gateway_config() -> dict[str, Any]:
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


def load_source_configs() -> dict[str, dict[str, str | None]]:
    raw_sources = load_config().get('sources', {})
    if not isinstance(raw_sources, dict):
        raise RuntimeError('TS4NFDI_PROVIDER sources config must be a dictionary.')

    sources = {}
    for source_key, raw_source in raw_sources.items():
        if not isinstance(raw_source, dict):
            raise RuntimeError(f"TS4NFDI source '{source_key}' must be a dictionary.")

        source_url = normalize_optional_string(raw_source.get('url'))
        if source_url and not is_http_iri(source_url):
            raise RuntimeError(f"TS4NFDI source '{source_key}' url must be an HTTP(S) URL.")

        sources[source_key] = {
            'id': source_key,
            'label': require_string(raw_source, 'label'),
            'database': require_string(raw_source, 'database'),
            'backend_type': normalize_optional_string(raw_source.get('backend_type')),
            'url': source_url,
        }
    return sources


def attach_source_config(config: dict[str, Any], *, context: str) -> dict[str, Any]:
    resolved = dict(config)
    source_key = normalize_optional_string(resolved.get('source_key'))
    if not source_key:
        return resolved

    sources = load_source_configs()
    if source_key not in sources:
        raise RuntimeError(f"{context} references unknown source_key '{source_key}'.")

    source = dict(sources[source_key])
    configured_database = normalize_optional_string(resolved.get('database'))
    if configured_database and configured_database != source['database']:
        raise RuntimeError(
            f"{context} database '{configured_database}' does not match "
            f"source '{source_key}' database '{source['database']}'."
        )

    resolved['source_key'] = source_key
    resolved['source'] = source
    resolved['database'] = source['database']
    return resolved


def load_annotation_matchers() -> tuple[AnnotationMatcher, ...]:
    frontend_config = _load_raw_frontend_config()
    annotations_config = frontend_config.get('annotations', {})

    if annotations_config in (None, False):
        return ()
    if not isinstance(annotations_config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend annotations config must be a dictionary.')
    if not annotations_config.get('enabled', False):
        return ()

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

        if matcher.id in matcher_ids:
            logger.error("Ignoring duplicate TS4NFDI annotation matcher id '%s'.", matcher.id)
            continue

        matcher_ids.add(matcher.id)
        matchers.append(matcher)
    return tuple(matchers)


def normalize_annotation_matcher(
    raw_matcher: dict[str, Any],
    index: int,
    providers: dict[str, Any],
) -> AnnotationMatcher:
    if not isinstance(raw_matcher, dict):
        raise RuntimeError('matcher must be a dictionary')

    removed_keys = sorted(set(raw_matcher) & {'widget_type', 'entity_type', 'tabs', 'use_legacy'})
    if removed_keys:
        raise RuntimeError(
            f'legacy presentation keys {removed_keys} are no longer supported; configure the nested presentation table'
        )

    matcher_id = str(raw_matcher.get('id') or f'annotation-{index + 1}').strip()
    resource_type = require_string(raw_matcher, 'resource_type')
    if resource_type not in ANNOTATION_RESOURCE_TYPES:
        raise RuntimeError(f'resource_type must be one of {sorted(ANNOTATION_RESOURCE_TYPES)}')

    provider_key = normalize_optional_string(raw_matcher.get('provider_key'))
    if resource_type in {'ontology', 'collection'}:
        if not provider_key:
            raise RuntimeError(f"provider_key is required for resource_type '{resource_type}'")
        if provider_key not in providers:
            raise RuntimeError(f"unknown provider_key '{provider_key}'")

    source_config = attach_source_config(
        {
            'source_key': raw_matcher.get('source_key'),
            'database': raw_matcher.get('gateway_params', {}).get('database')
            if isinstance(raw_matcher.get('gateway_params', {}), dict)
            else None,
        },
        context=f"annotation matcher '{matcher_id}'",
    )
    source = source_config.get('source')

    raw_gateway_params = raw_matcher.get('gateway_params', {})
    if not isinstance(raw_gateway_params, dict):
        raise RuntimeError('gateway_params must be a dictionary')
    gateway_params = {
        key: value
        for key, value in raw_gateway_params.items()
        if key in GATEWAY_PARAM_NAMES and value not in (None, '', [])
    }
    if source_config.get('database'):
        gateway_params['database'] = source_config['database']
    ignored_params = sorted(set(raw_gateway_params) - set(gateway_params))
    if ignored_params:
        logger.warning(
            "Ignoring unsupported Gateway parameters for matcher '%s': %s",
            matcher_id,
            ignored_params,
        )

    return AnnotationMatcher(
        id=matcher_id,
        question_uri=require_string(raw_matcher, 'question_uri'),
        attribute_uri=require_string(raw_matcher, 'attribute_uri'),
        optionset_uri=require_string(raw_matcher, 'optionset_uri'),
        resource_type=resource_type,
        presentation=normalize_presentation(raw_matcher.get('presentation'), resource_type),
        provider_key=provider_key,
        source=ResourceReference(**source) if source else None,
        badge_label=normalize_optional_string(raw_matcher.get('badge_label')),
        ontology_id=normalize_optional_string(raw_matcher.get('ontology_id')),
        gateway_params=tuple(gateway_params.items()),
    )


def normalize_presentation(raw_presentation: Any, resource_type: str) -> PresentationPolicy:
    if raw_presentation is None:
        return DEFAULT_ANNOTATION_PRESENTATIONS[resource_type]
    if not isinstance(raw_presentation, dict):
        raise RuntimeError('presentation must be a dictionary')

    adapter = normalize_optional_string(raw_presentation.get('adapter')) or 'native'
    component = normalize_optional_string(raw_presentation.get('component'))
    if not re.fullmatch(r'[a-z][a-z0-9_.-]*', adapter):
        raise RuntimeError('presentation adapter must be a lower-case identifier')
    if adapter == 'native':
        if component:
            raise RuntimeError('native presentation does not accept a component')
        return PresentationPolicy(adapter='native')
    if adapter != 'tss':
        return PresentationPolicy(
            adapter=adapter,
            component=component,
            options=tuple(
                (key, value) for key, value in raw_presentation.items() if key not in {'adapter', 'component'}
            ),
        )
    if component not in ANNOTATION_PRESENTATIONS[resource_type]:
        raise RuntimeError(
            f"TSS component for resource_type '{resource_type}' must be one of "
            f'{sorted(ANNOTATION_PRESENTATIONS[resource_type])}'
        )

    options = {key: value for key, value in raw_presentation.items() if key not in {'adapter', 'component'}}
    entity_type = normalize_optional_string(options.get('entity_type'))
    if entity_type and entity_type not in ANNOTATION_ENTITY_TYPES:
        raise RuntimeError(f'presentation entity_type must be one of {sorted(ANNOTATION_ENTITY_TYPES)}')

    tabs = options.get('tabs', ['synonyms', 'hierarchy', 'ontology'])
    if not isinstance(tabs, list) or any(tab not in ANNOTATION_TABS for tab in tabs):
        raise RuntimeError(f'presentation tabs must contain only {sorted(ANNOTATION_TABS)}')
    options['tabs'] = tuple(dict.fromkeys(tabs))

    return PresentationPolicy(
        adapter='tss',
        component=component,
        options=tuple(options.items()),
    )


def load_frontend_config() -> dict[str, Any]:
    raw_annotations = _load_raw_frontend_config().get('annotations', {})
    if raw_annotations in (None, False):
        raw_annotations = {}
    if not isinstance(raw_annotations, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend annotations config must be a dictionary.')

    matchers = load_annotation_matchers()
    return {
        'annotations': {
            'api_version': '1',
            'enabled': bool(raw_annotations.get('enabled', False) and matchers),
        }
    }


def _load_raw_frontend_config() -> dict[str, Any]:
    frontend_config = load_config().get('frontend', {})
    if not isinstance(frontend_config, dict):
        raise RuntimeError('TS4NFDI_PROVIDER frontend config must be a dictionary.')

    logger.debug(
        'Loaded TS4NFDI frontend config with keys=%s',
        sorted(frontend_config.keys()),
    )
    return frontend_config
