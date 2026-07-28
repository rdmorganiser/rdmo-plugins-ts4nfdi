from html import escape
from urllib.parse import urlencode

RESULT_LIST_KEYS = ("items", "results", "artefacts", "data", "collection", "collections")
SENSITIVE_PARAM_KEYS = {"api_key", "apikey", "authorization", "token"}


def join_url(base_url, endpoint):
    if not endpoint:
        return base_url

    return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"


def add_query_params(api_url, params):
    params = {key: value for key, value in params.items() if value not in (None, "", [])}

    if not params:
        return api_url

    separator = "&" if "?" in api_url else "?"
    return f"{api_url}{separator}{urlencode(params, doseq=True)}"


def extract_results(payload):
    if isinstance(payload, list):
        return payload

    if isinstance(payload, dict):
        response = payload.get("response")
        if isinstance(response, dict) and isinstance(response.get("docs"), list):
            return response["docs"]

        for key in RESULT_LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value

    return []


def get_first_value(data, keys):
    for key in keys:
        value = get_value(data, key)
        normalized = normalize_value(value)
        if normalized:
            return normalized
    return None


def get_values(data, keys):
    for key in keys:
        value = get_value(data, key)
        raw_values = value if isinstance(value, list) else [value]
        values = []
        for raw_value in raw_values:
            normalized = normalize_value(raw_value)
            if normalized and normalized not in values:
                values.append(normalized)
        if values:
            return values
    return []


def get_value(data, key):
    if not isinstance(data, dict):
        return None

    if key in data:
        return data[key]

    path_separator = "->" if "->" in key else "."
    if path_separator not in key:
        return None

    value = data
    for part in key.split(path_separator):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]

    return value


def normalize_value(value):
    if isinstance(value, str):
        return value.strip() or None

    if isinstance(value, dict):
        for nested_key in ("label", "value", "text", "en", "de"):
            nested_value = value.get(nested_key)
            normalized = normalize_value(nested_value)
            if normalized:
                return normalized
        return None

    if isinstance(value, list):
        for item in value:
            normalized = normalize_value(item)
            if normalized:
                return normalized
        return None

    if value is None:
        return None

    return str(value)


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    return list(value)


def redact_sensitive_params(params):
    return {
        key: "***" if key.lower() in SENSITIVE_PARAM_KEYS else value
        for key, value in params.items()
    }


def option_badge(text, modifier, title=None):
    title_attribute = f' title="{escape(str(title), quote=True)}"' if title else ""
    return (
        f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--{modifier}"{title_attribute}>'
        f'{escape(str(text))}'
        "</span>"
    )


def option_separator():
    return '<span class="ts4nfdi-option-separator">›</span>'  # noqa: RUF001


def option_breadcrumb(badges):
    if not badges:
        return None

    return f'<span class="ts4nfdi-option-breadcrumb">{"".join(badges)}</span>'


def option_description(parts):
    parts = [part for part in parts if part]
    if not parts:
        return None

    return f'<span class="ts4nfdi-option-description">{escape(" | ".join(parts))}</span>'
