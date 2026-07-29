"""Shared readers for normalized TS4NFDI Gateway result fields."""

RESULT_LIST_KEYS = ('items', 'results', 'artefacts', 'data', 'collection', 'collections')


def extract_results(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        response = payload.get('response')
        if isinstance(response, dict) and isinstance(response.get('docs'), list):
            return response['docs']
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

    path_separator = '->' if '->' in key else '.'
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
        for nested_key in ('label', 'value', 'text', 'en', 'de'):
            normalized = normalize_value(value.get(nested_key))
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
