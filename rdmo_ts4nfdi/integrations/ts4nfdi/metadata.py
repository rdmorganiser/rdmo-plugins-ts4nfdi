import logging
from urllib.parse import quote

from rdmo_ts4nfdi.domain import (
    AnnotationCandidate,
    AnnotationMatcher,
    ResolvedMetadata,
)

from .gateway import GatewayClient, GatewayError
from .payload import extract_results, get_first_value, get_value, get_values
from .provider_resources import (
    GatewayProviderResourceClient,
    build_source_reference,
    build_terminology_reference,
)

logger = logging.getLogger(__name__)

OLS_BACKEND_TYPES = frozenset({'ols2', 'ols4'})


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
        # A broad multi-source matcher has no OLS database or ontology route
        # from which its selected IRI can be reconstructed. Use the same
        # source-neutral search contract as its dynamic provider.
        if not matcher.source and not matcher.ontology_id:
            return self._resolve_entity_from_search(candidate, matcher)

        if (
            matcher.source
            and matcher.source.backend_type
            and matcher.source.backend_type.lower() not in OLS_BACKEND_TYPES
        ):
            return self._resolve_non_ols_entity(candidate, matcher)

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

    def _resolve_non_ols_entity(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        try:
            return self._resolve_entity_from_artefact(candidate, matcher)
        except (GatewayError, LookupError) as exc:
            logger.warning(
                'TS4NFDI Gateway concept-detail lookup failed for matcher=%r iri=%r; '
                'falling back to Gateway search: %s',
                matcher.id,
                candidate.iri,
                exc,
            )
            return self._resolve_entity_from_search(candidate, matcher)

    def _resolve_entity_from_artefact(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        if not matcher.ontology_id:
            raise LookupError('The Gateway artefact concept-detail route requires an ontology identifier.')

        endpoint = f'artefacts/{quote(matcher.ontology_id, safe="")}/resources/concepts/{quote(candidate.iri, safe="")}'
        query = [(key, value) for key, value in matcher.gateway_query if key not in {'iri', 'q', 'query', 'search'}]
        payload, _ = self.gateway.get(endpoint, query)
        result = next(
            (
                item
                for item in extract_entity_results(payload)
                if get_first_value(item, ('iri', '@id', 'uri', 'id')) == candidate.iri
            ),
            None,
        )
        if result is None:
            raise LookupError(f'No Gateway concept metadata was returned for {candidate.iri}.')
        return normalize_entity_metadata(result, matcher)

    def _resolve_entity_from_search(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        query = [
            ('query', candidate.label),
            *(
                (key, value)
                for key, value in matcher.gateway_query
                if key not in {'iri', 'q', 'query', 'search', 'display'}
            ),
        ]
        payload, _ = self.gateway.get('search', query)
        results = [
            item
            for item in extract_results(payload)
            if get_first_value(item, ('iri', '@id', 'uri', 'id')) == candidate.iri
        ]
        if not results:
            raise LookupError(f'No Gateway search metadata was returned for {candidate.iri}.')

        contexts = {
            (
                get_first_value(result, ('source_name', 'sourceName', 'source')),
                get_first_value(result, ('ontologyId', 'ontology_id', 'ontology')),
                get_first_value(result, ('backend_type', 'backendType')),
            )
            for result in results
        }
        if len(contexts) > 1:
            raise LookupError(
                f'Gateway search returned conflicting source contexts for {candidate.iri}.'
            )
        return normalize_entity_metadata(results[0], matcher)

    def _resolve_provider_resource(
        self,
        candidate: AnnotationCandidate,
        matcher: AnnotationMatcher,
    ) -> ResolvedMetadata:
        metadata = GatewayProviderResourceClient(self.gateway).resolve_metadata(candidate, matcher)
        return ResolvedMetadata(
            label=metadata.label or candidate.label,
            description=metadata.description,
            definitions=metadata.definitions,
            synonyms=metadata.synonyms,
            short_form=metadata.short_form,
            entity_types=metadata.entity_types,
            obsolete=metadata.obsolete,
            version=metadata.version,
            ontology_id=metadata.ontology_id,
            source=metadata.source,
            terminology=metadata.terminology,
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
        ontology_id=(
            get_first_value(result, ('ontologyId', 'ontology_name', 'ontology_id', 'ontology')) or matcher.ontology_id
        ),
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
        if get_first_value(payload, ('iri', '@id', 'uri', 'id')):
            return [payload]
        elements = payload.get('elements')
        if isinstance(elements, list):
            return elements
        embedded = payload.get('_embedded')
        if isinstance(embedded, dict):
            for value in embedded.values():
                if isinstance(value, list):
                    return value
    return extract_results(payload)
