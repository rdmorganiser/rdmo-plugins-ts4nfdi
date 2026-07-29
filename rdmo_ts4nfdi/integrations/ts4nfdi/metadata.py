from urllib.parse import quote

from rdmo_ts4nfdi.config import load_config
from rdmo_ts4nfdi.domain import (
    AnnotationCandidate,
    AnnotationMatcher,
    ResolvedMetadata,
    ResourceReference,
)
from rdmo_ts4nfdi.utils import is_http_iri

from .gateway import GatewayClient
from .payload import extract_results, get_first_value, get_value, get_values


class GatewayMetadataResolver:
    """Resolve plugin annotation candidates through public Gateway responses."""

    def __init__(self, gateway: GatewayClient):
        self.gateway = gateway

    def resolve(self, candidate: AnnotationCandidate, matcher: AnnotationMatcher) -> ResolvedMetadata:
        if matcher.resource_type == 'entity':
            return self._resolve_entity(candidate, matcher)
        return self._resolve_provider_resource(candidate, matcher)

    def _resolve_entity(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        query = [
            ('iri', candidate.iri),
            *((key, value) for key, value in matcher.gateway_query if key != 'iri'),
        ]
        endpoint = (
            f'ols4/api/v2/ontologies/{quote(matcher.ontology_id, safe="")}/entities'
            if matcher.ontology_id
            else 'ols4/api/v2/entities'
        )
        payload, _ = self.gateway.get(endpoint, query)
        results = extract_entity_results(payload)
        if not results:
            raise LookupError(f'No Gateway entity metadata was returned for {candidate.iri}.')
        return normalize_entity_metadata(results[0], matcher)

    def _resolve_provider_resource(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        config = load_config()
        provider_config = {
            **config.get('defaults', {}),
            **config['providers'][matcher.provider_key],
        }

        query = []
        for config_key, parameter_name in (
            ('collection_id', provider_config.get('collection_id_param', 'collectionId')),
            ('page', provider_config.get('page_param', 'page')),
            ('size', provider_config.get('size_param', 'size')),
        ):
            if provider_config.get(config_key) is not None:
                query.append((parameter_name, provider_config[config_key]))
        query.extend(provider_config.get('extra_params', {}).items())

        payload, _ = self.gateway.get(provider_config.get('endpoint', ''), query)
        results = extract_provider_results(payload, provider_config)
        if not results and provider_config.get('fallback_endpoint'):
            payload, _ = self.gateway.get(provider_config['fallback_endpoint'])
            results = extract_provider_results(payload, provider_config)

        result = next(
            (item for item in results if candidate.iri in provider_resource_identifiers(item, provider_config)),
            {},
        )
        source = build_source_reference(matcher, result)
        return ResolvedMetadata(
            label=(
                get_first_value(
                    result,
                    tuple(provider_config.get('label_fields', ('label', 'title'))),
                )
                or candidate.label
            ),
            description=get_first_value(
                result,
                tuple(provider_config.get('help_fields', ('description', 'definition'))),
            ),
            ontology_id=(get_first_value(result, ('ontologyId', 'ontology_id', 'config.id')) or matcher.ontology_id),
            source=source,
            terminology=build_terminology_reference(matcher, result),
            version=get_first_value(result, ('version', 'config.version')),
        )


def build_source_reference(
    matcher: AnnotationMatcher,
    result: dict | None = None,
) -> ResourceReference | None:
    configured = matcher.source
    result = result or {}
    result_id = get_first_value(result, ('source_name', 'sourceName'))
    result_source = get_first_value(result, ('source',))

    source_id = configured.id if configured else result_id
    source_label = configured.label if configured else source_id
    source_url = configured.url if configured else result_source if is_http_iri(result_source) else None
    if not source_id and result_source and not source_url:
        source_id = result_source
        source_label = result_source

    if not any((source_id, source_label, source_url)):
        return None
    return ResourceReference(
        id=source_id,
        label=source_label,
        database=configured.database if configured else source_id,
        backend_type=(
            configured.backend_type if configured else get_first_value(result, ('backend_type', 'backendType'))
        ),
        url=source_url,
    )


def build_terminology_reference(
    matcher: AnnotationMatcher,
    result: dict | None = None,
) -> ResourceReference | None:
    result = result or {}
    terminology_id = get_first_value(result, ('ontologyId', 'ontology_id', 'ontology')) or matcher.ontology_id
    terminology_iri = get_first_value(result, ('ontologyIri', 'ontology_iri'))
    terminology_label = matcher.badge_label or terminology_id
    if not any((terminology_id, terminology_iri, terminology_label)):
        return None
    return ResourceReference(
        id=terminology_id,
        label=terminology_label,
        iri=terminology_iri,
    )


def normalize_entity_metadata(result: dict, matcher: AnnotationMatcher) -> ResolvedMetadata:
    definitions = get_values(
        result,
        ('definition', 'definitions', 'descriptions', 'description'),
    )
    synonyms = get_values(
        result,
        ('synonym', 'synonyms', 'alternativeLabels', 'alternative_labels'),
    )
    obsolete_value = get_value(result, 'isObsolete')
    if obsolete_value is None:
        obsolete_value = get_value(result, 'obsolete')

    return ResolvedMetadata(
        label=get_first_value(result, ('label', 'prefLabel')),
        description=definitions[0] if definitions else None,
        definitions=tuple(definitions),
        synonyms=tuple(synonyms),
        short_form=get_first_value(result, ('shortForm', 'short_form', 'obo_id')),
        entity_types=tuple(get_values(result, ('type',))),
        obsolete=normalize_boolean(obsolete_value),
        ontology_id=(get_first_value(result, ('ontologyId', 'ontology_name', 'ontology_id')) or matcher.ontology_id),
        source=build_source_reference(matcher, result),
        terminology=build_terminology_reference(matcher, result),
    )


def normalize_boolean(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes'}:
            return True
        if normalized in {'false', '0', 'no'}:
            return False
    return None


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
