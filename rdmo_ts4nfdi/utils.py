from urllib.parse import urlencode, urlparse


def join_url(base_url, endpoint):
    if not endpoint:
        return base_url
    return f'{base_url.rstrip("/")}/{endpoint.lstrip("/")}'


def add_query_params(api_url, params):
    params = {key: value for key, value in params.items() if value not in (None, '', [])}
    if not params:
        return api_url
    separator = '&' if '?' in api_url else '?'
    return f'{api_url}{separator}{urlencode(params, doseq=True)}'


def normalize_optional_string(value):
    if value is None:
        return None

    value = str(value).strip()
    return value or None


def require_string(mapping, key):
    value = normalize_optional_string(mapping.get(key))
    if not value:
        raise RuntimeError(f'{key} is required')
    return value


def is_http_iri(value):
    if not value:
        return False

    parsed = urlparse(value)
    return parsed.scheme in {'http', 'https'} and bool(parsed.netloc)
