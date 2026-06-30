import logging

from django import template

from rdmo_ts4nfdi.config import load_frontend_config

logger = logging.getLogger(__name__)
register = template.Library()


@register.simple_tag
def ts4nfdi_frontend_config():
    try:
        return load_frontend_config()
    except RuntimeError:
        logger.exception("Could not load TS4NFDI frontend config.")
        return {}
