"""Default production composition for replaceable plugin adapters."""

from functools import cache

from django.conf import settings
from django.utils.module_loading import import_string

from rdmo_ts4nfdi.application import (
    AnnotationService,
    SemanticAnnotationTargetResolver,
    SemanticOptionExternalIdProjector,
)
from rdmo_ts4nfdi.config import load_annotation_matchers, load_option_external_id_projection_policy

DEFAULT_ADAPTERS = {
    'interview_host': 'rdmo_ts4nfdi.integrations.rdmo.RDMOInterviewHost',
    'gateway': 'rdmo_ts4nfdi.integrations.ts4nfdi.GatewayClient',
    'metadata_resolver': 'rdmo_ts4nfdi.integrations.ts4nfdi.GatewayMetadataResolver',
    'presentation': 'rdmo_ts4nfdi.presentation.AnnotationPresentationRegistry',
    'semantic_options': 'rdmo_ts4nfdi.semantic_options.PackageSemanticOptionRegistry',
}


def load_adapter_classes() -> dict:
    configured = getattr(settings, 'TS4NFDI_ADAPTERS', {})
    if not isinstance(configured, dict):
        raise RuntimeError('TS4NFDI_ADAPTERS must be a dictionary.')

    unknown = sorted(set(configured) - set(DEFAULT_ADAPTERS))
    if unknown:
        raise RuntimeError(f'Unknown TS4NFDI_ADAPTERS keys: {unknown}')
    return {name: import_string(configured.get(name, dotted_path)) for name, dotted_path in DEFAULT_ADAPTERS.items()}


def build_annotation_service() -> AnnotationService:
    adapters = load_adapter_classes()
    gateway = adapters['gateway']()
    semantic_options = adapters['semantic_options']()
    return AnnotationService(
        host=adapters['interview_host'](),
        targets=SemanticAnnotationTargetResolver(semantic_options),
        metadata=adapters['metadata_resolver'](gateway),
        presentation=adapters['presentation'](),
        matchers=load_annotation_matchers(),
    )


@cache
def build_option_external_id_projector() -> SemanticOptionExternalIdProjector:
    adapters = load_adapter_classes()
    return SemanticOptionExternalIdProjector(
        registry=adapters['semantic_options'](),
        policy=load_option_external_id_projection_policy(),
    )
