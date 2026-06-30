import logging
from functools import cache

from django.conf import settings

logger = logging.getLogger(__name__)


@cache
def load_config():
    config = getattr(settings, "TS4NFDI_PROVIDER", None)

    if config is None:
        raise RuntimeError("Missing TS4NFDI_PROVIDER setting.")

    if not isinstance(config, dict):
        raise RuntimeError("TS4NFDI_PROVIDER must be a dictionary.")

    providers = config.get("providers", {})
    logger.debug(
        "Loaded TS4NFDI provider config with top-level keys=%s, provider keys=%s",
        sorted(config.keys()),
        sorted(providers.keys()) if isinstance(providers, dict) else providers,
    )

    return config


def load_frontend_config():
    config = load_config()
    frontend_config = config.get("frontend", {})

    if not isinstance(frontend_config, dict):
        raise RuntimeError("TS4NFDI_PROVIDER frontend config must be a dictionary.")

    logger.debug(
        "Loaded TS4NFDI frontend config with keys=%s",
        sorted(frontend_config.keys()),
    )
    return frontend_config
