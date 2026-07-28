from urllib.parse import urlparse


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
