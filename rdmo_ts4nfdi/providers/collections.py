import logging
from html import escape

from .base import TS4NFDIBaseProvider

logger = logging.getLogger(__name__)


class TS4NFDICollectionsProvider(TS4NFDIBaseProvider):

    search = True
    refresh = False

    def get_options(self, project, search=None, user=None, site=None):
        if not search:
            return []

        provider_config = self.get_provider_config()
        payload = self.make_request(search, provider_config=provider_config)
        if payload is None:
            return self.get_request_error_options(provider_config)

        results = self.extract_results(payload)
        filtered_results = self.filter_results(results, search)
        options = []

        logger.debug(
            "TS4NFDI collections provider '%s' search=%r result_count=%s filtered_result_count=%s",
            self.key,
            search,
            len(results),
            len(filtered_results),
        )

        for result in filtered_results:
            option = self.map_result_to_option(result, provider_config)
            if option:
                options.append(option)

        options = self.deduplicate_options(options, provider_config)
        options = self.exclude_selected_options(project, options, provider_config)
        return options[: provider_config.get("limit", 20)]

    def build_query_params(self, provider_config, search):
        query_params = {}

        if provider_config.get("server_side_search"):
            query_params[provider_config.get("search_param", "query")] = search

        extra_params = provider_config.get("extra_params", {})
        query_params.update(extra_params)

        return query_params

    def filter_results(self, results, search):
        normalized_search = search.lower()

        return [
            result
            for result in results
            if self.collection_matches(result, normalized_search)
        ]

    def collection_matches(self, result, normalized_search):
        if not isinstance(result, dict):
            return False

        searchable_values = [
            result.get("id"),
            result.get("label"),
            result.get("description"),
            result.get("creator"),
        ]

        for terminology in result.get("terminologies", []):
            if isinstance(terminology, dict):
                searchable_values.extend(
                    [
                        terminology.get("label"),
                        terminology.get("uri"),
                        terminology.get("source"),
                        terminology.get("type"),
                    ]
                )

        return any(
            value and normalized_search in str(value).lower()
            for value in searchable_values
        )

    def map_result_to_option(self, result, provider_config):
        if not isinstance(result, dict):
            return None

        identifier = self.get_first_value(result, provider_config.get("id_fields", ("id",)))
        label = self.get_first_value(result, provider_config.get("label_fields", ("label",)))

        if not identifier or not label:
            return None

        option = {
            "id": identifier,
            "text": label,
        }

        help_text = self.build_help_html(result)
        if help_text:
            option["help"] = help_text

        return option

    def build_help_html(self, result):
        parts = []

        description = self.get_first_value(result, ("description",))
        creator = self.get_first_value(result, ("creator",))
        is_public = result.get("isPublic")

        badges = []
        if creator:
            badges.append(
                f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--ontology">{escape(creator)}</span>'
            )
        if is_public is not None:
            visibility = "public" if is_public else "restricted"
            badges.append(
                f'<span class="ts4nfdi-option-badge ts4nfdi-option-badge--term">{visibility}</span>'
            )

        if badges:
            parts.append(
                f'<span class="ts4nfdi-option-breadcrumb">{"".join(badges)}</span>'
            )

        if description:
            parts.append(
                f'<span class="ts4nfdi-option-description">{escape(description)}</span>'
            )

        return "".join(parts) or None
