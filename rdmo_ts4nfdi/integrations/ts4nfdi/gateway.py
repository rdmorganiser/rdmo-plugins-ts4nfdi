import hashlib
import json
import logging
from collections.abc import Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from django.core.cache import cache

from rdmo_ts4nfdi.config import GATEWAY_PARAM_NAMES, load_gateway_config

logger = logging.getLogger(__name__)

ALLOWED_GATEWAY_PATH_PREFIXES = (
    'collections',
    'ols4/api/individuals',
    'ols4/api/properties',
    'ols4/api/terms',
    'ols4/api/ontologies',
    'ols4/api/v2/classes',
    'ols4/api/v2/entities',
    'ols4/api/v2/individuals',
    'ols4/api/v2/ontologies',
    'ols4/api/v2/properties',
    'search',
)


def is_allowed_artefact_concept_path(path: str) -> bool:
    parts = path.split('/')
    return (
        len(parts) == 5
        and parts[0] == 'artefacts'
        and bool(parts[1])
        and parts[2] == 'resources'
        and parts[3] in {'classes', 'concepts'}
        and bool(parts[4])
    )


class GatewayError(RuntimeError):
    status_code = 502


class GatewayTimeout(GatewayError):
    status_code = 504
    # A Gateway timeout is an expected failure of an external dependency. The
    # browser proxy must not return a 5xx response for it: Django logs every
    # 5xx response through ``django.request`` and deployments commonly attach
    # ``AdminEmailHandler`` to that logger. Keep ``status_code`` as the actual
    # upstream classification and expose a separate, non-5xx proxy status.
    proxy_status_code = 424


class GatewayRequestError(GatewayError):
    status_code = 400


def validate_gateway_path(path: str) -> str:
    normalized = str(path or '').lstrip('/')
    parsed_path = urlparse(f'/{normalized}')
    decoded_path = unquote(unquote(parsed_path.path))

    if not normalized or parsed_path.query or parsed_path.fragment or '..' in decoded_path.split('/'):
        raise GatewayRequestError('Invalid Gateway path.')
    allowed_prefix = any(
        normalized == prefix or normalized.startswith(f'{prefix}/') for prefix in ALLOWED_GATEWAY_PATH_PREFIXES
    )
    if not allowed_prefix and not is_allowed_artefact_concept_path(normalized):
        raise GatewayRequestError('Gateway path is not allowed.')
    return normalized


def filter_gateway_query(query_params) -> list[tuple[str, str]]:
    return [(key, value) for key in query_params if key in GATEWAY_PARAM_NAMES for value in query_params.getlist(key)]


class GatewayClient:
    """Authenticated server-side adapter for the TS4NFDI API Gateway."""

    def __init__(self, config: dict | None = None):
        self._config = config

    @property
    def config(self) -> dict:
        return self._config or load_gateway_config()

    def get(
        self,
        path: str,
        query: Iterable[tuple[str, object]] = (),
        *,
        use_cache: bool = True,
    ) -> tuple[object, bool]:
        gateway_config = self.config
        path = validate_gateway_path(path)
        query = [(key, value) for key, value in query if key in GATEWAY_PARAM_NAMES and value not in (None, '')]
        base_url = gateway_config['base_url'].rstrip('/') + '/'
        request_url = urljoin(base_url, path)
        upstream = urlparse(request_url)
        configured = urlparse(base_url)

        if (
            upstream.scheme not in {'http', 'https'}
            or upstream.scheme != configured.scheme
            or upstream.netloc != configured.netloc
        ):
            raise GatewayRequestError('Gateway request escaped the configured host.')

        if query:
            request_url = f'{request_url}?{urlencode(query, doseq=True)}'

        cache_key = 'rdmo-ts4nfdi:gateway:' + hashlib.sha256(request_url.encode()).hexdigest()
        if use_cache:
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                logger.debug('TS4NFDI Gateway cache hit for %s', request_url)
                return cached_response, True

        logger.debug(
            'TS4NFDI Gateway requesting %s timeout=%s',
            request_url,
            gateway_config['timeout'],
        )

        request = Request(
            request_url,
            headers=self._headers(gateway_config),
        )
        try:
            with urlopen(request, timeout=gateway_config['timeout']) as response:
                final_url = urlparse(response.geturl())
                if final_url.scheme != configured.scheme or final_url.netloc != configured.netloc:
                    raise GatewayError('Gateway redirected to a different host.')
                payload = json.load(response)
        except TimeoutError as exc:
            raise GatewayTimeout('The terminology Gateway timed out.') from exc
        except HTTPError as exc:
            raise GatewayError(f'The terminology Gateway returned HTTP {exc.code}.') from exc
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise GatewayTimeout('The terminology Gateway timed out.') from exc
            raise GatewayError('The terminology Gateway is unavailable.') from exc
        except ValueError as exc:
            raise GatewayError('The terminology Gateway returned invalid JSON.') from exc

        if use_cache:
            cache.set(cache_key, payload, gateway_config['cache_timeout'])
        return payload, False

    @staticmethod
    def _headers(config: dict) -> dict[str, str]:
        headers = {
            'Accept': 'application/json',
            'User-Agent': 'rdmo-ts4nfdi/gateway-adapter',
        }
        if config.get('api_token'):
            headers['Authorization'] = f'Bearer {config["api_token"]}'
        return headers
