"""Native annotation details for bounded provider-backed resources."""

from rdmo_ts4nfdi.domain import (
    AnnotationDetail,
    AnnotationMatcher,
    AnnotationSummary,
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
        return AnnotationDetail(
            annotation=annotation,
            metadata_status='available',
            metadata=metadata,
            presentation=PresentationDescriptor(adapter='native'),
            collection=collection,
            api_version='2',
        )
