import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from rdmo.options.providers import Provider

logger = logging.getLogger(__name__)

API_BASE_URL_DEFAULT = 'https://terminology.services.base4nfdi.de/api-gateway'


class TS4NFDIBaseProvider(Provider):

    search = True
    refresh = False

    DEFAULT_ID_FIELDS = ("iri", "uri", "id")
    DEFAULT_LABEL_FIELDS = ("prefLabel", "label", "name", "title")
    DEFAULT_HELP_FIELDS = ("definition", "description", "scopeNote", "summary")

    def make_request(self, search=None):

        provider_config = self.get_provider_config()
        api_url = self.get_request_url(provider_config)
        timeout = provider_config.get("timeout", 10)
        params = self.build_query_params(provider_config, search)
        request_url = self.add_query_params(api_url, params)

        request = Request(
            request_url,
            headers=self.get_request_headers(provider_config),
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except Exception:
            logger.exception("TS4NFDI provider request failed for provider '%s'.", self.key)
            return None
        else:
            return payload

    def get_request_url(self, provider_config):
        if provider_config.get("api_url"):
            return provider_config["api_url"]

        base_url = provider_config.get("base_url", API_BASE_URL_DEFAULT)
        endpoint = provider_config.get("endpoint", "")

        return self.join_url(base_url, endpoint)

    def join_url(self, base_url, endpoint):
        if not endpoint:
            return base_url

        return f"{base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def add_query_params(self, api_url, params):
        params = {key: value for key, value in params.items() if value not in (None, "", [])}

        if not params:
            return api_url

        separator = "&" if "?" in api_url else "?"
        return f"{api_url}{separator}{urlencode(params, doseq=True)}"

    def get_request_headers(self, provider_config):
        headers = {
                "Accept": "application/json",
                "User-Agent": "rdmo-ts4nfdi-provider/0.1",
        }

        token = provider_config.get("api_token")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        return headers

    def build_query_params(self, provider_config, search):
        return {}

    def get_provider_config(self):
        config = getattr(settings, "TS4NFDI_OPTIONSET_PROVIDER_CONFIG", {})
        defaults = config.get("defaults", {})
        providers = config.get("providers", {})

        if self.key not in providers:
            raise RuntimeError(
                f"Missing TS4NFDI provider configuration for key '{self.key}'."
            )

        return {**defaults, **providers[self.key]}

    def extract_results(self, payload):
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            response = payload.get("response")
            if isinstance(response, dict) and isinstance(response.get("docs"), list):
                return response["docs"]

            for key in ("items", "results", "artefacts", "data", "collection", "collections"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def get_first_value(self, data, keys):
        for key in keys:
            value = self.get_value(data, key)
            normalized = self.normalize_value(value)
            if normalized:
                return normalized
        return None

    def get_value(self, data, key):
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

    def normalize_value(self, value):
        if isinstance(value, str):
            return value.strip() or None

        if isinstance(value, dict):
            for nested_key in ("label", "value", "text", "en", "de"):
                nested_value = value.get(nested_key)
                normalized = self.normalize_value(nested_value)
                if normalized:
                    return normalized
            return None

        if isinstance(value, list):
            for item in value:
                normalized = self.normalize_value(item)
                if normalized:
                    return normalized
            return None

        if value is None:
            return None

        return str(value)

    def normalize_list(self, value):
        if value is None:
            return []

        if isinstance(value, str):
            return [value]

        return list(value)
