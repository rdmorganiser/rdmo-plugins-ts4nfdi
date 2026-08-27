import hashlib
import logging
from html import escape, unescape

from django.utils.translation import get_language

from rdmo.options.providers import Provider

from rdmo_ts4nfdi.config import load_provider_config
from rdmo_ts4nfdi.integrations.ts4nfdi.payload import extract_results
from rdmo_ts4nfdi.integrations.ts4nfdi.provider import GatewayProviderClient

from .utils import (
    normalize_list,
    option_description,
    redact_sensitive_params,
)

logger = logging.getLogger(__name__)


class TS4NFDIBaseProvider(Provider):
    search = True
    refresh = False

    DEFAULT_ID_FIELDS = ('iri', 'uri', 'id')
    DEFAULT_LABEL_FIELDS = ('prefLabel', 'label', 'name', 'title')
    DEFAULT_HELP_FIELDS = ('definition', 'description', 'scopeNote', 'summary')

    def make_request(self, search=None, provider_config=None):
        if provider_config is None:
            provider_config = self.get_provider_config()

        client = GatewayProviderClient()
        timeout = provider_config.get('timeout', 10)
        params = self.build_query_params(provider_config, search)
        request_url = client.prepare_request_url(
            provider_config,
            redact_sensitive_params(params),
        )
        self.last_request_error = None

        logger.debug(
            "TS4NFDI provider '%s' requesting %s timeout=%s",
            self.key,
            request_url,
            timeout,
        )

        try:
            payload = client.get(provider_config, params)
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

    def build_query_params(self, provider_config, search):
        return {}

    def get_provider_config(self):
        provider_config = load_provider_config(self.key)
        logger.debug(
            "Resolved TS4NFDI provider config for key='%s' with config keys=%s",
            self.key,
            sorted(provider_config.keys()),
        )
        return provider_config

    def get_request_error_options(self, provider_config):
        if provider_config.get('show_request_errors', True) is False:
            return []

        if not getattr(self, 'last_request_error', None):
            return []

        error_message = self.format_request_error(self.last_request_error)
        text = provider_config.get(
            'request_error_text',
            'TS4NFDI service is currently unavailable.',
        )
        help_text = provider_config.get(
            'request_error_help',
            f'Could not load options from the terminology service: {error_message}',
        )

        return [
            {
                'id': f'__ts4nfdi_request_error__:{self.key}',
                'text': text,
                'help': option_description([help_text]),
                'isDisabled': True,
                'disabled': True,
                'ts4nfdi_error': True,
            }
        ]

    def with_free_text_candidate(self, search, options, provider_config, *, all_options=None):
        """Add RDMO's native-create marker as an explicit, safe provider option.

        RDMO renders option text as HTML.  User input must therefore be escaped
        for display while ``value`` keeps the original text that RDMO persists
        through its existing ``__isNew__`` flow.
        """

        if provider_config.get('free_text_candidate') is not True:
            return options

        value = str(search or '').strip()
        if not value:
            return options

        comparison_options = all_options if all_options is not None else options
        if any(self.option_text_matches_search(option, value) for option in comparison_options):
            return options

        language = (get_language() or 'en').split('-', 1)[0].casefold()
        if language == 'de':
            message = 'Kein passender Begriff gefunden. Wählen Sie diesen Eintrag, um ihn als Freitext zu übernehmen.'
        else:
            message = 'No matching term found. Select this entry to use it as free text.'

        digest = hashlib.sha256(value.encode('utf-8')).hexdigest()
        return [
            *options,
            {
                'id': f'__ts4nfdi_free_text__:{self.key}:{digest}',
                'text': escape(value),
                'help': option_description([message]),
                'value': value,
                '__isNew__': True,
                'ts4nfdi_free_text': True,
            },
        ]

    @staticmethod
    def option_text_matches_search(option, search):
        if not isinstance(option, dict):
            return False

        option_text = option.get('text')
        if option_text is None:
            return False

        return unescape(str(option_text)).strip().casefold() == str(search).strip().casefold()

    def format_request_error(self, error):
        reason = getattr(error, 'reason', None)
        if reason:
            return str(reason)

        return str(error)

    def exclude_selected_options(self, project, options, provider_config):
        selected_attribute_uris = normalize_list(
            provider_config.get('exclude_selected_attribute_uris')
            or provider_config.get('selected_attribute_uris')
            or provider_config.get('attribute_uris')
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
            'attributes=%s selected_values=%s before=%s after=%s',
            self.key,
            selected_attribute_uris,
            len(selected_values),
            len(options),
            len(filtered_options),
        )
        return filtered_options

    def get_selected_option_values(self, project, attribute_uris):
        selected_values = set()
        values = project.values.filter(snapshot=None, attribute__uri__in=attribute_uris).select_related('option')

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
        selected_match_fields = provider_config.get('selected_match_fields', ('id',))

        return any(option.get(field) in selected_values for field in selected_match_fields)
