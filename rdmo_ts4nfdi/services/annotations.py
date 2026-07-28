import logging
from collections import defaultdict
from urllib.parse import quote, urlencode

from rdmo.projects.utils import check_conditions
from rdmo.questions.models import Question, QuestionSet

from rdmo_ts4nfdi.config import find_annotation_matcher, load_annotation_matchers, load_config
from rdmo_ts4nfdi.providers.utils import extract_results, get_first_value
from rdmo_ts4nfdi.utils import is_http_iri

from .annotation_metadata import (
    build_source_metadata,
    build_terminology_metadata,
    normalize_entity_metadata,
)
from .gateway import gateway_get

logger = logging.getLogger(__name__)


def build_page_annotations(project, page):
    matchers = load_annotation_matchers()
    values = list(
        project.values.filter(snapshot=None)
        .select_related('attribute', 'option')
        .order_by('attribute', 'set_prefix', 'set_index', 'collection_index')
    )
    occurrences = []

    for question in flatten_questions(page.elements):
        matcher = find_annotation_matcher(question, matchers)
        if not matcher or not question.attribute:
            continue

        scoped_values = [
            value for value in values if value.attribute_id == question.attribute_id and is_http_iri(value.external_id)
        ]
        grouped_values = defaultdict(list)
        for value in scoped_values:
            if check_conditions(question.conditions.all(), values, value.set_prefix, value.set_index):
                grouped_values[(value.set_prefix, value.set_index)].append(value)

        for (set_prefix, set_index), occurrence_values in grouped_values.items():
            annotations = [serialize_annotation_value(value, question, matcher) for value in occurrence_values]
            if annotations:
                occurrences.append(
                    {
                        'key': f'{question.id}:{set_prefix}:{set_index}',
                        'question_id': question.id,
                        'question_uri': question.uri,
                        'attribute_id': question.attribute_id,
                        'set_prefix': set_prefix,
                        'set_index': set_index,
                        'annotations': annotations,
                    }
                )

    return {
        'project_id': project.id,
        'page_id': page.id,
        'occurrences': occurrences,
    }


def serialize_annotation_value(value, question, matcher):
    return {
        'value_id': value.id,
        'collection_index': value.collection_index,
        'matcher_id': matcher['id'],
        'kind': matcher['resource_type'],
        'label': value.text,
        'iri': value.external_id,
        'badge_label': matcher.get('badge_label'),
        'source': build_source_metadata(matcher),
        'terminology': build_terminology_metadata(matcher),
        'question_id': question.id,
    }


def resolve_annotation(project, value, matcher_id=None):
    if not is_http_iri(value.external_id):
        raise LookupError('The selected value does not contain an HTTP IRI.')

    project.catalog.prefetch_elements()
    questions = [question for question in project.catalog.questions if question.attribute_id == value.attribute_id]
    matchers = load_annotation_matchers()
    question_and_matcher = next(
        (
            (question, matcher)
            for question in questions
            if (matcher := find_annotation_matcher(question, matchers))
            and (matcher_id is None or matcher['id'] == matcher_id)
        ),
        None,
    )
    if question_and_matcher is None:
        raise LookupError('No TS4NFDI annotation matcher applies to this value.')

    question, matcher = question_and_matcher
    detail = {
        **serialize_annotation_value(value, question, matcher),
        'metadata_status': 'available',
        'description': None,
        'definitions': [],
        'synonyms': [],
        'short_form': None,
        'entity_types': [],
        'obsolete': None,
        'version': None,
        'ontology_id': matcher.get('ontology_id'),
    }

    try:
        if matcher['resource_type'] == 'entity':
            detail.update(resolve_entity(value.external_id, matcher))
        else:
            detail.update(resolve_provider_resource(value, matcher))
    except Exception:
        logger.exception(
            'Could not resolve TS4NFDI annotation metadata for project=%s value=%s',
            project.id,
            value.id,
        )
        detail['metadata_status'] = 'unavailable'

    detail['widget'] = build_widget_descriptor(project, detail, matcher)
    return detail


def resolve_entity(iri, matcher):
    query = [
        ('iri', iri),
        *((key, value) for key, value in matcher['gateway_params'].items() if key != 'iri'),
    ]
    ontology_id = matcher.get('ontology_id')
    if ontology_id:
        endpoint = f'ols4/api/v2/ontologies/{quote(ontology_id, safe="")}/entities'
    else:
        endpoint = 'ols4/api/v2/entities'
    payload, _ = gateway_get(endpoint, query)
    results = extract_entity_results(payload)
    if not results:
        raise LookupError(f'No Gateway entity metadata was returned for {iri}.')

    return normalize_entity_metadata(results[0], matcher)


def resolve_provider_resource(value, matcher):
    config = load_config()
    provider_config = {
        **config.get('defaults', {}),
        **config['providers'][matcher['provider_key']],
    }

    endpoint = provider_config.get('endpoint', '')
    query = []
    for config_key, parameter_name in (
        ('collection_id', provider_config.get('collection_id_param', 'collectionId')),
        ('page', provider_config.get('page_param', 'page')),
        ('size', provider_config.get('size_param', 'size')),
    ):
        if provider_config.get(config_key) is not None:
            query.append((parameter_name, provider_config[config_key]))
    query.extend(provider_config.get('extra_params', {}).items())

    payload, _ = gateway_get(endpoint, query)
    results = extract_provider_results(payload, provider_config)
    if not results and provider_config.get('fallback_endpoint'):
        payload, _ = gateway_get(provider_config['fallback_endpoint'])
        results = extract_provider_results(payload, provider_config)

    result = next(
        (item for item in results if value.external_id in provider_resource_identifiers(item, provider_config)),
        {},
    )

    return {
        'label': (
            get_first_value(result, tuple(provider_config.get('label_fields', ('label', 'title')))) or value.text
        ),
        'description': get_first_value(
            result,
            tuple(provider_config.get('help_fields', ('description', 'definition'))),
        ),
        'ontology_id': (
            get_first_value(result, ('ontologyId', 'ontology_id', 'config.id')) or matcher.get('ontology_id')
        ),
        'source': get_first_value(result, ('source', 'source_name')),
        'version': get_first_value(result, ('version', 'config.version')),
    }


def build_widget_descriptor(project, detail, matcher):
    proxy_api = f'/api/v1/ts4nfdi/projects/{project.id}/gateway/ols4/api/'
    parameter = urlencode(matcher['gateway_params'])
    widget_type = matcher['widget_type']

    if widget_type == 'none':
        return {'type': 'none', 'props': {}}

    if detail['kind'] == 'entity':
        props = {
            'api': proxy_api,
            'iri': detail['iri'],
            'ontologyId': detail.get('ontology_id'),
            'entityType': matcher.get('entity_type'),
            'parameter': parameter,
            'useLegacy': matcher['use_legacy'],
        }
        if widget_type == 'entity_info':
            props.update(
                {
                    'hasTitle': False,
                    'showBadges': True,
                }
            )
            return {
                'type': 'entity_info',
                'props': props,
            }

        tabs = set(matcher['tabs'])
        props.update(
            {
                'altNamesTab': 'synonyms' in tabs,
                'hierarchyTab': 'hierarchy' in tabs,
                'crossRefTab': 'crossref' in tabs,
                'terminologyInfoTab': 'ontology' in tabs,
                'graphViewTab': 'graphview' in tabs,
                'termDepictionTab': 'depiction' in tabs,
                'entityInfoTab': 'entityinfo' in tabs,
                'entityRelationTab': 'entityrelations' in tabs,
                'copyButton': 'right',
            }
        )
        return {
            'type': 'metadata',
            'props': props,
        }

    if widget_type == 'ontology_info' and detail.get('ontology_id'):
        return {
            'type': 'ontology_info',
            'props': {
                'api': proxy_api,
                'ontologyId': detail['ontology_id'],
                'parameter': parameter,
                'useLegacy': matcher['use_legacy'],
            },
        }

    return {'type': widget_type, 'props': {}}


def flatten_questions(elements):
    for element in elements:
        if isinstance(element, Question):
            yield element
        elif isinstance(element, QuestionSet):
            yield from flatten_questions(element.elements)


def extract_entity_results(payload):
    if isinstance(payload, dict):
        elements = payload.get('elements')
        if isinstance(elements, list):
            return elements
        embedded = payload.get('_embedded')
        if isinstance(embedded, dict):
            for value in embedded.values():
                if isinstance(value, list):
                    return value
    return extract_results(payload)


def extract_provider_results(payload, provider_config):
    if isinstance(payload, dict):
        embedded = payload.get('_embedded')
        if isinstance(embedded, dict) and isinstance(embedded.get('ontologies'), list):
            return embedded['ontologies']

        collection_id = provider_config.get('collection_id')
        collections = extract_results(payload)
        if collection_id:
            collection = next(
                (
                    item
                    for item in collections
                    if isinstance(item, dict) and get_first_value(item, ('id', 'uuid')) == collection_id
                ),
                None,
            )
            if collection and isinstance(collection.get('terminologies'), list):
                return collection['terminologies']

    return extract_results(payload)


def provider_resource_identifiers(item, provider_config):
    identifiers = {
        get_first_value(
            item,
            tuple(provider_config.get('id_fields', ('iri', 'uri', 'id'))),
        ),
        get_first_value(
            item,
            tuple(provider_config.get('uri_fields', ('iri', 'uri'))),
        ),
        get_first_value(item, ('URI', 'config.id', 'id')),
    }
    item_id = get_first_value(item, ('id', 'uuid'))
    if item_id:
        permalink_base = provider_config.get(
            'permalink_base',
            'https://w3id.org/ts4nfdi/collection/',
        )
        identifiers.add(f'{permalink_base.rstrip("/")}/{item_id}')
    return identifiers - {None}
