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

        identifier = self.get_first_value(
            result,
            provider_config.get("id_fields", ("id",)),
        )
        label = self.get_first_value(
            result,
            provider_config.get("label_fields", ("label",)),
        )

        if not identifier or not label:
            return None

        option = {
            "id": identifier,
            "text": label,
        }

        help_text = self.build_help_html(result, provider_config)
        if help_text:
            option["help"] = help_text

        return option

    def build_help_html(self, result, provider_config):
        identifier = self.get_first_value(
            result,
            provider_config.get("id_fields", ("id",)),
        )
        label = self.get_first_value(
            result,
            provider_config.get("label_fields", ("label",)),
        )
        description = self.get_first_value(result, ("description",))
        creator = self.get_first_value(result, ("creator",))
        is_public = result.get("isPublic")
        permalink = self.build_permalink(identifier, provider_config)

        parts = [
            '<span class="ts4nfdi-collection-card">',
            '<span class="ts4nfdi-collection-card__header">',
            '<span class="ts4nfdi-collection-card__title">'
            f'{escape(label or "")}'
            "</span>",
        ]

        if creator:
            parts.append(
                '<span class="ts4nfdi-collection-card__creator">'
                f'Created by: {escape(creator)}'
                "</span>"
            )

        if is_public is not None:
            visibility = "public" if is_public else "restricted"
            visibility_class = "public" if is_public else "restricted"
            parts.append(
                '<span class="'
                "ts4nfdi-collection-card__status "
                f"ts4nfdi-collection-card__status--{visibility_class}"
                f'">{visibility}</span>'
            )

        parts.append("</span>")

        metadata = [
            ("uuid:", identifier),
            ("PermaLink:", permalink),
        ]

        metadata_html = [
            self.render_metadata_row(label, value)
            for label, value in metadata
            if value
        ]
        if metadata_html:
            parts.append(
                '<span class="ts4nfdi-collection-card__metadata">'
                f'{"".join(metadata_html)}'
                "</span>"
            )

        if description:
            parts.append(
                '<span class="ts4nfdi-collection-card__description">'
                f'{escape(description)}'
                "</span>"
            )

        terminology_badges = self.render_terminology_badges(result, provider_config)
        if terminology_badges:
            parts.append(
                '<span class="ts4nfdi-collection-card__terminologies">'
                '<span class="ts4nfdi-collection-card__terminologies-label">'
                "Terminologies:"
                "</span>"
                f'{terminology_badges}'
                "</span>"
            )

        parts.append("</span>")

        return "".join(parts)

    def build_permalink(self, identifier, provider_config):
        if not identifier:
            return None

        permalink_base = provider_config.get(
            "permalink_base",
            "https://w3id.org/ts4nfdi/collection/",
        )
        return f"{permalink_base.rstrip('/')}/{identifier}"

    def render_metadata_row(self, label, value):
        return (
            '<span class="ts4nfdi-collection-card__metadata-row">'
            '<span class="ts4nfdi-collection-card__metadata-label">'
            f'{escape(label)}'
            "</span>"
            '<span class="ts4nfdi-collection-card__metadata-value">'
            f'{escape(value)}'
            "</span>"
            "</span>"
        )

    def render_terminology_badges(self, result, provider_config):
        terminologies = result.get("terminologies")
        if not isinstance(terminologies, list):
            return ""

        badge_limit = provider_config.get("terminology_badge_limit", 12)
        badges = []

        for terminology in terminologies[:badge_limit]:
            if not isinstance(terminology, dict):
                continue

            label = self.get_first_value(terminology, ("label", "uri"))
            source = self.get_first_value(terminology, ("source",))
            if not label:
                continue

            badge_text = label
            if source:
                badge_text = f"{badge_text} ({source})"

            badges.append(
                '<span class="ts4nfdi-collection-card__terminology-badge">'
                f'{escape(badge_text)}'
                "</span>"
            )

        remaining_count = len(terminologies) - badge_limit
        if remaining_count > 0:
            badges.append(
                '<span class="ts4nfdi-collection-card__terminology-badge '
                'ts4nfdi-collection-card__terminology-badge--more">'
                f'+{remaining_count} more'
                "</span>"
            )

        return "".join(badges)
