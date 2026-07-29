from html import escape

SENSITIVE_PARAM_KEYS = {'api_key', 'apikey', 'authorization', 'token'}


def normalize_list(value):
    if value is None:
        return []

    if isinstance(value, str):
        return [value]

    return list(value)


def redact_sensitive_params(params):
    return {key: '***' if key.lower() in SENSITIVE_PARAM_KEYS else value for key, value in params.items()}


def option_badge(text, modifier, title=None):
    title_attribute = f' title="{escape(str(title), quote=True)}"' if title else ''
    return (
        f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--{modifier}"{title_attribute}>'
        f'{escape(str(text))}'
        '</span>'
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
