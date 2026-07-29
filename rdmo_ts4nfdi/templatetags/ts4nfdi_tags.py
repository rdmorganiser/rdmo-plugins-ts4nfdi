import logging

from django import template

from rdmo_ts4nfdi.config import load_frontend_config
from rdmo_ts4nfdi.vendor import load_tss_vendor_manifest

logger = logging.getLogger(__name__)
register = template.Library()


@register.simple_tag
def ts4nfdi_frontend_config():
    try:
        return load_frontend_config()
    except RuntimeError:
        logger.exception('Could not load TS4NFDI frontend config.')
        return {}


@register.simple_tag
def ts4nfdi_tss_vendor():
    try:
        return load_tss_vendor_manifest()
    except (OSError, RuntimeError, ValueError):
        logger.exception('Could not load the TS4NFDI widget vendor manifest.')
        return {}
