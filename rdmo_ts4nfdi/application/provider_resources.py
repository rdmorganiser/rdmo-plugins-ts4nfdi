"""Native annotation details for bounded provider-backed resources."""

from rdmo_ts4nfdi.domain import (
    AnnotationDetail,
    AnnotationMatcher,
    AnnotationSummary,
    GatewayContext,
    PresentationDescriptor,
)
from rdmo_ts4nfdi.integrations.ts4nfdi.provider_resources import GatewayProviderResourceClient


class GatewayProviderResourceDetailResolver:
    """Build a native detail payload from the selected provider record only."""

    def __init__(self, gateway, **kwargs):
        self.resources = GatewayProviderResourceClient(gateway, **kwargs)

    def resolve(
        self,
        annotation: AnnotationSummary,
        matcher: AnnotationMatcher,
    ) -> AnnotationDetail:
        if not matcher.provider_resource_detail:
            raise LookupError('The annotation matcher has no provider-resource detail policy.')

        metadata, collection = self.resources.resolve_detail(annotation, matcher)
        gateway_context = self.gateway_context(metadata)
        return AnnotationDetail(
            annotation=annotation,
            metadata_status='available',
            metadata=metadata,
            presentation=self.presentation(matcher, gateway_context),
            gateway_context=gateway_context,
            collection=collection,
            api_version='2',
        )

    @staticmethod
    def gateway_context(metadata) -> GatewayContext | None:
        source = metadata.source
        ontology_id = metadata.ontology_id or (metadata.terminology.id if metadata.terminology else None)
        context = GatewayContext(
            ontology_id=ontology_id,
            database=source.database if source else None,
            backend_type=source.backend_type if source else None,
        )
        if not any((context.ontology_id, context.database, context.backend_type)):
            return None
        return context

    @staticmethod
    def presentation(
        matcher: AnnotationMatcher,
        context: GatewayContext | None,
    ) -> PresentationDescriptor:
        requested = matcher.presentation
        if (
            matcher.resource_type == 'ontology'
            and requested.adapter == 'tss'
            and requested.component == 'ontology-info'
            and context
            and context.ontology_id
            and context.database
            and context.backend_type in {'ols2', 'ols4'}
        ):
            return PresentationDescriptor(
                adapter='tss',
                component='ontology-info',
                props={'useLegacy': False},
            )
        return PresentationDescriptor(adapter='native')
