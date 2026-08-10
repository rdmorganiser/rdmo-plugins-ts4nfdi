"""Default production composition for replaceable plugin adapters."""

from django.conf import settings
from django.utils.module_loading import import_string

from rdmo_ts4nfdi.application import AnnotationService, AnnotationTargetResolver
from rdmo_ts4nfdi.config import load_annotation_matchers

DEFAULT_ADAPTERS = {
    'interview_host': 'rdmo_ts4nfdi.integrations.rdmo.RDMOInterviewHost',
    'gateway': 'rdmo_ts4nfdi.integrations.ts4nfdi.GatewayClient',
    'metadata_resolver': 'rdmo_ts4nfdi.integrations.ts4nfdi.GatewayMetadataResolver',
    'presentation': 'rdmo_ts4nfdi.presentation.AnnotationPresentationRegistry',
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
    return AnnotationService(
        host=adapters['interview_host'](),
        targets=AnnotationTargetResolver(),
        metadata=adapters['metadata_resolver'](gateway),
        presentation=adapters['presentation'](),
        matchers=load_annotation_matchers(),
    )
