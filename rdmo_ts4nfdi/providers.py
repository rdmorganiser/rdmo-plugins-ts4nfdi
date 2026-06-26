import json
import logging
from html import escape
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

from rdmo.options.providers import Provider

logger = logging.getLogger(__name__)

API_URL = 'https://terminology.services.base4nfdi.de/api-gateway'

class TS4NFDIProvider(Provider):

    search = True
    refresh = False

    DEFAULT_ID_FIELDS = ("iri", "uri", "id")
    DEFAULT_LABEL_FIELDS = ("prefLabel", "label", "name", "title")
    DEFAULT_HELP_FIELDS = ("definition", "description", "scopeNote", "summary")

    def get_options(self, project, search=None, user=None, site=None):
        if not search:
            return []

        provider_config = self.get_provider_config()
        api_url = provider_config("api_url", API_URL)
        timeout = provider_config.get("timeout", 10)
        params = self.build_query_params(provider_config, search)
        request_url = f"{api_url}?{urlencode(params, doseq=True)}"

        request = Request(
            request_url,
            headers={
                "Accept": "application/json",
                "User-Agent": "rdmo-ts4nfdi-provider/0.1",
            },
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except Exception:
            logger.exception("TS4NFDI provider request failed for provider '%s'.", self.key)
            return []

        results = self.extract_results(payload)
        options = []

        for result in results[: provider_config.get("limit", 20)]:
            option = self.map_result_to_option(result, provider_config)
            if option:
                options.append(option)

        return options

    def get_provider_config(self):
        config = getattr(settings, "TS4NFDI_OPTIONSET_PROVIDER_CONFIG", {})
        defaults = config.get("defaults", {})
        providers = config.get("providers", {})

        if self.key not in providers:
            raise RuntimeError(
                f"Missing TS4NFDI provider configuration for key '{self.key}'."
            )

        provider_config = {**defaults, **providers[self.key]}
        if "api_url" not in provider_config:
            raise RuntimeError(
                f"Missing 'api_url' in TS4NFDI provider configuration for key '{self.key}'."
            )

        return provider_config

    def build_query_params(self, provider_config, search):
        query_params = {
            provider_config.get("search_param", "query"): search,
        }

        if provider_config.get("limit") is not None:
            query_params[provider_config.get("limit_param", "limit")] = provider_config["limit"]

        terminologies = provider_config.get("terminologies", [])
        if terminologies:
            query_params[provider_config.get("terminologies_param", "terminologies")] = ",".join(terminologies)

        entity_types = provider_config.get("entity_types", [])
        if entity_types:
            query_params[provider_config.get("entity_types_param", "entity_types")] = ",".join(entity_types)

        extra_params = provider_config.get("extra_params", {})
        query_params.update(extra_params)

        return query_params

    def extract_results(self, payload):
        if isinstance(payload, list):
            return payload

        if isinstance(payload, dict):
            response = payload.get("response")
            if isinstance(response, dict) and isinstance(response.get("docs"), list):
                return response["docs"]

            for key in ("items", "results", "artefacts", "data"):
                value = payload.get(key)
                if isinstance(value, list):
                    return value

        return []

    def map_result_to_option(self, result, provider_config):
        if not isinstance(result, dict):
            return None

        identifier = self.get_first_value(result, provider_config.get("id_fields", self.DEFAULT_ID_FIELDS))
        label = self.get_first_value(result, provider_config.get("label_fields", self.DEFAULT_LABEL_FIELDS))

        if not identifier or not label:
            return None

        help_text = self.build_help_html(result, provider_config)

        option = {
            "id": identifier,
            "text": label,
        }

        if help_text:
            option["help"] = help_text

        return option

    def build_help_html(self, result, provider_config):
        ontology_name = self.get_first_value(
            result,
            provider_config.get("ontology_fields", ("ontology_name", "ontology")),
        )
        short_form = self.get_first_value(
            result,
            provider_config.get("short_form_fields", ("short_form", "obo_id")),
        )
        description = self.get_first_value(
            result,
            provider_config.get("help_fields", self.DEFAULT_HELP_FIELDS),
        )

        parts = []

        if ontology_name or short_form:
            breadcrumb = ['<span class="ts4nfdi-option-breadcrumb">']
            if ontology_name:
                breadcrumb.append(
                    f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--ontology">{escape(ontology_name)}</span>'
                )
            if short_form:
                breadcrumb.append('<span class="ts4nfdi-option-separator">›</span>')  # noqa: RUF001
                breadcrumb.append(
                    f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--term">{escape(short_form)}</span>'
                )
            breadcrumb.append('</span>')
            parts.append("".join(breadcrumb))

        if description:
            parts.append(
                f'<span class="ts4nfdi-option-description">{escape(description)}</span>'
            )

        return "".join(parts) or None

    def get_first_value(self, data, keys):
        for key in keys:
            value = data.get(key)
            normalized = self.normalize_value(value)
            if normalized:
                return normalized
        return None

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
