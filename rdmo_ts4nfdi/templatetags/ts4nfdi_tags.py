import logging

from django import template
from django.templatetags.static import static

from rdmo_ts4nfdi.config import load_frontend_config
from rdmo_ts4nfdi.vendor import load_tss_vendor_manifest

logger = logging.getLogger(__name__)
register = template.Library()


@register.simple_tag
def ts4nfdi_frontend_config():
    try:
        config = load_frontend_config()
    except RuntimeError:
        logger.exception('Could not load TS4NFDI frontend config.')
        return {}

    resolved_adapters = []
    for adapter in config.get('presentation_adapters', []):
        try:
            resolved_adapters.append(
                {
                    'name': adapter['name'],
                    'module_url': static(adapter['static_path']),
                    'export': adapter['export'],
                }
            )
        except (KeyError, ValueError):
            logger.exception(
                "Could not resolve static asset for TS4NFDI presentation adapter '%s'.",
                adapter.get('name'),
            )

    return {
        **config,
        'presentation_adapters': resolved_adapters,
    }


@register.simple_tag
def ts4nfdi_tss_vendor():
    try:
        return load_tss_vendor_manifest()
    except (OSError, RuntimeError, ValueError):
        logger.exception('Could not load the TS4NFDI widget vendor manifest.')
        return {}
