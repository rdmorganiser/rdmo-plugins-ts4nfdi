"""Bounded Gateway lookups for provider-backed native resources.

This is deliberately not a terminology metadata resolver.  It reuses the
same configured endpoint as an RDMO OptionSet provider, finds the already
selected collection or terminology record, and exposes only its own display
metadata for the native annotation drawer.
"""

from collections.abc import Callable
from typing import Any

from rdmo_ts4nfdi.config import load_provider_config
from rdmo_ts4nfdi.domain import (
    AnnotationMatcher,
    CollectionCollaborator,
    CollectionMetadata,
    CollectionTerminology,
    ResolvedMetadata,
    ResourceReference,
)
from rdmo_ts4nfdi.utils import is_http_iri

from .payload import extract_results, get_first_value, get_value


class GatewayProviderResourceClient:
    """Look up one selected provider resource through its configured endpoint."""

    def __init__(
        self,
        gateway,
        *,
        provider_config_loader: Callable[[str], dict[str, Any]] = load_provider_config,
    ):
        self.gateway = gateway
        self.provider_config_loader = provider_config_loader

    def resolve_metadata(self, annotation, matcher: AnnotationMatcher) -> ResolvedMetadata:
        provider_config, result = self._selected_record(annotation, matcher)
        return build_provider_metadata(matcher, result, provider_config)

    def resolve_detail(
        self,
        annotation,
        matcher: AnnotationMatcher,
    ) -> tuple[ResolvedMetadata, CollectionMetadata | None]:
        """Return the native detail model using exactly one Gateway lookup."""
        provider_config, result = self._selected_record(annotation, matcher)
        metadata = build_provider_metadata(matcher, result, provider_config)
        collection = (
            build_collection_metadata(annotation, result, provider_config)
            if matcher.resource_type == 'collection'
            else None
        )
        return metadata, collection

    def _selected_record(self, annotation, matcher: AnnotationMatcher) -> tuple[dict[str, Any], dict]:
        if not matcher.provider_key:
            raise LookupError('The annotation matcher is not backed by a provider resource.')

        provider_config = self.provider_config_loader(matcher.provider_key)
        # Gateway resources are not uniformly slash-tolerant. In particular,
        # the configured ``collections/`` endpoint is valid while
        # ``collections`` returns 404. Reuse the provider path verbatim.
        endpoint = str(provider_config.get('endpoint', ''))
        if not endpoint:
            raise LookupError('The configured provider-resource endpoint is unavailable.')
        payload, _cache_hit = self.gateway.get(
            endpoint,
            self.request_query(provider_config),
        )
        results = extract_provider_results(payload, provider_config)
        if not results and provider_config.get('fallback_endpoint'):
            fallback_endpoint = str(provider_config['fallback_endpoint'])
            if not fallback_endpoint:
                raise LookupError('The configured provider-resource fallback endpoint is unavailable.')
            payload, _cache_hit = self.gateway.get(fallback_endpoint)
            results = extract_provider_results(payload, provider_config)

        result = next(
            (
                item
                for item in results
                if annotation.iri in provider_resource_identifiers(item, provider_config)
            ),
            {},
        )
        return provider_config, result

    @staticmethod
    def request_query(provider_config: dict[str, Any]) -> list[tuple[str, Any]]:
        query = []
        for config_key, parameter_name in (
            ('collection_id', provider_config.get('collection_id_param', 'collectionId')),
            ('page', provider_config.get('page_param', 'page')),
            ('size', provider_config.get('size_param', 'size')),
        ):
            if provider_config.get(config_key) is not None:
                query.append((parameter_name, provider_config[config_key]))
        query.extend(provider_config.get('extra_params', {}).items())
        return query


def build_provider_metadata(
    matcher: AnnotationMatcher,
    result: dict,
    provider_config: dict[str, Any],
) -> ResolvedMetadata:
    return ResolvedMetadata(
        label=get_first_value(
            result,
            tuple(provider_config.get('label_fields', ('label', 'title'))),
        ),
        description=get_first_value(
            result,
            tuple(provider_config.get('help_fields', ('description', 'definition'))),
        ),
        ontology_id=(
            get_first_value(result, ('ontologyId', 'ontology_id', 'config.id'))
            or matcher.ontology_id
        ),
        source=build_source_reference(matcher, result),
        terminology=build_terminology_reference(matcher, result),
        version=get_first_value(result, ('version', 'config.version')),
    )


def build_collection_metadata(
    annotation,
    result: dict,
    provider_config: dict[str, Any],
) -> CollectionMetadata:
    """Normalize the public collection fields documented by the Gateway.

    ``/collections/`` currently returns ``TerminologyCollectionDto`` records.
    The schema has no permalink field, so the selected RDMO identifier is the
    authoritative permalink fallback.
    """
    uuid = get_first_value(result, ('id', 'uuid'))
    permalink = (
        get_first_value(result, ('permaLink', 'permalink', 'iri', 'uri'))
        or collection_permalink(uuid, provider_config)
        or annotation.iri
    )
    raw_visibility = get_value(result, 'isPublic')
    if raw_visibility is None:
        raw_visibility = get_value(result, 'is_public')

    return CollectionMetadata(
        uuid=uuid,
        permalink=permalink,
        is_public=normalize_boolean(raw_visibility),
        creator=get_first_value(result, ('creator',)),
        collaborators=collection_collaborators(result),
        terminologies=collection_terminologies(result),
    )


def collection_permalink(uuid: str | None, provider_config: dict[str, Any]) -> str | None:
    if not uuid:
        return None
    permalink_base = provider_config.get('permalink_base')
    if not permalink_base:
        return None
    return f'{str(permalink_base).rstrip("/")}/{uuid}'


def normalize_boolean(value) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {'true', '1', 'yes'}:
            return True
        if normalized in {'false', '0', 'no'}:
            return False
    return None


def collection_collaborators(result: dict) -> tuple[CollectionCollaborator, ...]:
    raw_collaborators = get_value(result, 'collaborators')
    if not isinstance(raw_collaborators, list):
        return ()

    collaborators = []
    for collaborator in raw_collaborators:
        if isinstance(collaborator, str):
            username = collaborator.strip()
            role = None
        elif isinstance(collaborator, dict):
            username = get_first_value(collaborator, ('username', 'name', 'label'))
            role = get_first_value(collaborator, ('role',))
        else:
            continue
        if username:
            collaborators.append(CollectionCollaborator(username=username, role=role))
    return tuple(collaborators)


def collection_terminologies(result: dict) -> tuple[CollectionTerminology, ...]:
    raw_terminologies = get_value(result, 'terminologies')
    if not isinstance(raw_terminologies, list):
        return ()

    terminologies = []
    for terminology in raw_terminologies:
        if not isinstance(terminology, dict):
            continue
        label = get_first_value(terminology, ('label', 'title', 'ontologyId', 'uri', 'URI'))
        if not label:
            continue
        terminologies.append(
            CollectionTerminology(
                label=label,
                source=get_first_value(terminology, ('source', 'source_name', 'sourceName')),
                uri=get_first_value(terminology, ('uri', 'URI', 'iri')),
                type=get_first_value(terminology, ('type',)),
            )
        )
    return tuple(terminologies)


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
    terminology_label = (
        matcher.badge_label
        if matcher.ontology_id
        else terminology_id or matcher.badge_label
    )
    if not any((terminology_id, terminology_iri, terminology_label)):
        return None
    return ResourceReference(
        id=terminology_id,
        label=terminology_label,
        iri=terminology_iri,
    )


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
