import json
import logging
from urllib.request import Request, urlopen

from rdmo.options.providers import Provider

from rdmo_ts4nfdi.config import load_config

from .utils import (
    add_query_params,
    extract_results,
    join_url,
    normalize_list,
    option_description,
    redact_sensitive_params,
)

logger = logging.getLogger(__name__)

API_BASE_URL_DEFAULT = 'https://terminology.services.base4nfdi.de/api-gateway'


class TS4NFDIBaseProvider(Provider):

    search = True
    refresh = False

    DEFAULT_ID_FIELDS = ("iri", "uri", "id")
    DEFAULT_LABEL_FIELDS = ("prefLabel", "label", "name", "title")
    DEFAULT_HELP_FIELDS = ("definition", "description", "scopeNote", "summary")

    def make_request(self, search=None, provider_config=None):
        if provider_config is None:
            provider_config = self.get_provider_config()

        api_url = self.get_request_url(provider_config)
        timeout = provider_config.get("timeout", 10)
        params = self.build_query_params(provider_config, search)
        request_url = add_query_params(api_url, params)
        self.last_request_error = None

        logger.debug(
            "TS4NFDI provider '%s' requesting %s with params=%s timeout=%s",
            self.key,
            api_url,
            redact_sensitive_params(params),
            timeout,
        )

        request = Request(
            request_url,
            headers=self.get_request_headers(provider_config),
        )

        try:
            with urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
        except Exception as exc:
            self.last_request_error = exc
            logger.exception("TS4NFDI provider request failed for provider '%s'.", self.key)
            return None
        else:
            logger.debug(
                "TS4NFDI provider '%s' received payload type=%s result_count=%s",
                self.key,
                type(payload).__name__,
                len(extract_results(payload)),
            )
            return payload

    def get_request_url(self, provider_config):
        if provider_config.get("api_url"):
            return provider_config["api_url"]

        base_url = provider_config.get("base_url", API_BASE_URL_DEFAULT)
        endpoint = provider_config.get("endpoint", "")

        return join_url(base_url, endpoint)

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
        config = load_config()
        defaults = config.get("defaults", {})
        providers = config.get("providers", {})

        if self.key not in providers:
            raise RuntimeError(
                f"Missing TS4NFDI provider configuration for key '{self.key}'."
            )

        provider_config = {**defaults, **providers[self.key]}
        logger.debug(
            "Resolved TS4NFDI provider config for key='%s' with config keys=%s",
            self.key,
            sorted(provider_config.keys()),
        )
        return provider_config

    def deduplicate_options(self, options, provider_config):
        dedupe_fields = provider_config.get("dedupe_fields", ("id",))
        seen = set()
        deduplicated = []

        for option in options:
            dedupe_key = tuple(option.get(field) for field in dedupe_fields)
            if dedupe_key in seen:
                logger.debug(
                    "Skipping duplicate TS4NFDI option for provider '%s': dedupe_fields=%s dedupe_key=%s",
                    self.key,
                    dedupe_fields,
                    dedupe_key,
                )
                continue

            seen.add(dedupe_key)
            deduplicated.append(option)

        logger.debug(
            "Deduplicated TS4NFDI options for provider '%s': before=%s after=%s",
            self.key,
            len(options),
            len(deduplicated),
        )
        return deduplicated

    def get_request_error_options(self, provider_config):
        if provider_config.get("show_request_errors", True) is False:
            return []

        if not getattr(self, "last_request_error", None):
            return []

        error_message = self.format_request_error(self.last_request_error)
        text = provider_config.get(
            "request_error_text",
            "TS4NFDI service is currently unavailable.",
        )
        help_text = provider_config.get(
            "request_error_help",
            f"Could not load options from the terminology service: {error_message}",
        )

        return [
            {
                "id": f"__ts4nfdi_request_error__:{self.key}",
                "text": text,
                "help": option_description([help_text]),
                "isDisabled": True,
                "disabled": True,
                "ts4nfdi_error": True,
            }
        ]

    def format_request_error(self, error):
        reason = getattr(error, "reason", None)
        if reason:
            return str(reason)

        return str(error)

    def exclude_selected_options(self, project, options, provider_config):
        selected_attribute_uris = normalize_list(
            provider_config.get("exclude_selected_attribute_uris")
            or provider_config.get("selected_attribute_uris")
            or provider_config.get("attribute_uris")
        )

        if not project or not selected_attribute_uris:
            return options

        selected_values = self.get_selected_option_values(project, selected_attribute_uris)
        if not selected_values:
            return options

        filtered_options = [
            option
            for option in options
            if not self.option_matches_selected_value(option, selected_values, provider_config)
        ]

        logger.debug(
            "Excluded already selected TS4NFDI options for provider '%s': "
            "attributes=%s selected_values=%s before=%s after=%s",
            self.key,
            selected_attribute_uris,
            len(selected_values),
            len(options),
            len(filtered_options),
        )
        return filtered_options

    def get_selected_option_values(self, project, attribute_uris):
        selected_values = set()
        values = (
            project.values
            .filter(snapshot=None, attribute__uri__in=attribute_uris)
            .select_related("option")
        )

        for value in values:
            selected_values.update(
                candidate
                for candidate in (
                    value.external_id,
                    value.text,
                    value.option.uri if value.option else None,
                    value.option.text if value.option else None,
                )
                if candidate
            )

        return selected_values

    def option_matches_selected_value(self, option, selected_values, provider_config):
        selected_match_fields = provider_config.get("selected_match_fields", ("id",))

        return any(
            option.get(field) in selected_values
            for field in selected_match_fields
        )
