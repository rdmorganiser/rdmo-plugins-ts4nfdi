"""Small Gateway entity-set provenance adapter.

This module deliberately reads only the configured entity-set entry selected by
an RDMO value. It does not fetch or normalize terminology metadata; TSS keeps
that responsibility for compatible OLS2 sources.
"""

from collections.abc import Iterable

from rdmo_ts4nfdi.domain import (
    AnnotationMatcher,
    AnnotationSummary,
    EntitySetProvenance,
    GatewayContext,
    PresentationPolicy,
    ResourceReference,
)
from rdmo_ts4nfdi.utils import normalize_optional_string


class GatewayEntitySetProvenanceResolver:
    """Recover source and terminology context for one Gateway entity-set IRI."""

    def __init__(self, gateway, *, sources):
        self.gateway = gateway
        self.sources = sources

    def resolve(
        self,
        annotation: AnnotationSummary,
        matcher: AnnotationMatcher,
        *,
        language: str | None = None,
    ) -> EntitySetProvenance:
        if not matcher.entityset_id or not matcher.entityset_endpoint:
            raise LookupError('The annotation matcher is not backed by a Gateway entity set.')

        endpoint = matcher.entityset_endpoint.rstrip('/')
        if not endpoint:
            raise LookupError('The configured Gateway entity-set endpoint is unavailable.')
        payload, _cache_hit = self.gateway.get(endpoint)
        entityset = self.find_entityset(payload, matcher.entityset_id)
        if entityset is None:
            raise LookupError('The configured Gateway entity set is unavailable.')

        entity = self.find_entity(entityset, annotation.iri)
        if entity is None:
            raise LookupError('The selected value is not present in the configured Gateway entity set.')

        source = self.source_reference(entity)
        terminology = self.terminology_reference(entity)
        gateway_context = GatewayContext(
            ontology_id=terminology.id if terminology else None,
            database=source.database if source else None,
            backend_type=source.backend_type if source else None,
        )
        if not any((gateway_context.ontology_id, gateway_context.database, gateway_context.backend_type)):
            gateway_context = None

        return EntitySetProvenance(
            annotation=annotation,
            source=source,
            terminology=terminology,
            gateway_context=gateway_context,
            definitions=tuple(self.localized_values(entity.get('definition'), language)),
            presentation=self.presentation(source, terminology),
        )

    @staticmethod
    def find_entityset(payload, entityset_id):
        if isinstance(payload, dict):
            if str(payload.get('id') or '').strip() == entityset_id:
                return payload
            entitysets = (
                payload.get('entitysets')
                or payload.get('items')
                or payload.get('results')
                or []
            )
        elif isinstance(payload, list):
            entitysets = payload
        else:
            return None

        return next(
            (
                entityset
                for entityset in entitysets
                if isinstance(entityset, dict)
                and str(entityset.get('id') or '').strip() == entityset_id
            ),
            None,
        )

    @staticmethod
    def find_entity(entityset, iri):
        return next(
            (
                entity
                for entity in entityset.get('entities', [])
                if isinstance(entity, dict)
                and str(entity.get('uri') or '').strip() == iri
            ),
            None,
        )

    def source_reference(self, entity):
        provider_id = normalize_optional_string(entity.get('provider'))
        if not provider_id:
            return None

        configured = self.sources.get(provider_id)
        if configured:
            return ResourceReference(**configured)
        return ResourceReference(id=provider_id, label=provider_id)

    @staticmethod
    def terminology_reference(entity):
        terminology_id = normalize_optional_string(entity.get('terminology'))
        if not terminology_id:
            return None
        return ResourceReference(id=terminology_id, label=terminology_id)

    @staticmethod
    def presentation(source, terminology):
        if (
            source
            and source.database
            and source.backend_type == 'ols2'
            and terminology
            and terminology.id
        ):
            return PresentationPolicy(adapter='tss', component='entity-info')
        return PresentationPolicy(adapter='native')

    @classmethod
    def localized_values(cls, values, language) -> Iterable[str]:
        value = cls.localized_text(values, language)
        return (value,) if value else ()

    @staticmethod
    def localized_text(values, language):
        if isinstance(values, str):
            return normalize_optional_string(values)
        if isinstance(values, dict):
            if 'value' in values or 'label' in values:
                values = [values]
            else:
                values = [
                    {'lang': key, 'value': value}
                    for key, value in values.items()
                ]
        if not isinstance(values, list):
            return None

        language = (language or 'en').lower()
        primary_language = language.split('-', 1)[0]
        candidates = []
        for item in values:
            if isinstance(item, str):
                candidates.append((None, normalize_optional_string(item)))
            elif isinstance(item, dict):
                candidates.append(
                    (
                        normalize_optional_string(item.get('lang')),
                        normalize_optional_string(item.get('value') or item.get('label')),
                    )
                )
        candidates = [(lang, value) for lang, value in candidates if value]
        for preferred in (language, primary_language, 'en'):
            match = next(
                (value for lang, value in candidates if lang and lang.lower() == preferred),
                None,
            )
            if match:
                return match
        return candidates[0][1] if candidates else None
