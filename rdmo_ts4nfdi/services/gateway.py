import hashlib
import json
import logging
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


class GatewayError(RuntimeError):
    status_code = 502


class GatewayTimeout(GatewayError):
    status_code = 504


class GatewayRequestError(GatewayError):
    status_code = 400


def validate_gateway_path(path):
    normalized = str(path or '').lstrip('/')
    decoded_path = unquote(unquote(urlparse(f'/{normalized}').path))

    if not normalized or '..' in decoded_path.split('/'):
        raise GatewayRequestError('Invalid Gateway path.')

    if not any(normalized == prefix or normalized.startswith(f'{prefix}/') for prefix in ALLOWED_GATEWAY_PATH_PREFIXES):
        raise GatewayRequestError('Gateway path is not allowed.')

    return normalized


def filter_gateway_query(query_params):
    filtered = []
    for key in query_params:
        if key not in GATEWAY_PARAM_NAMES:
            continue
        for value in query_params.getlist(key):
            filtered.append((key, value))
    return filtered


def gateway_get(path, query=(), use_cache=True):
    gateway_config = load_gateway_config()
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
            return cached_response, True

    headers = {
        'Accept': 'application/json',
        'User-Agent': 'rdmo-ts4nfdi/annotation-proxy',
    }
    if gateway_config.get('api_token'):
        headers['Authorization'] = f'Bearer {gateway_config["api_token"]}'

    request = Request(request_url, headers=headers)
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
