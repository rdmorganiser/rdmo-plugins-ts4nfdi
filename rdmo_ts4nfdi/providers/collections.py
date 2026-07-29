import logging

from rdmo_ts4nfdi.integrations.ts4nfdi.payload import extract_results, get_first_value

from .base import TS4NFDIBaseProvider
from .utils import option_badge, option_breadcrumb, option_description

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

        results = extract_results(payload)
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

        if provider_config.get('exclude_selected_collection_options') is True:
            options = self.exclude_selected_collection_options(
                project,
                options,
                provider_config,
                search,
            )
        return options[: provider_config.get('limit', 20)]

    def exclude_selected_collection_options(self, project, options, provider_config, search):
        if provider_config.get('preserve_exact_selected_search', True) is False:
            return self.exclude_selected_options(project, options, provider_config)

        preserved_options = [option for option in options if self.option_text_matches_search(option, search)]
        filtered_options = self.exclude_selected_options(project, options, provider_config)
        filtered_ids = {option.get('id') for option in filtered_options}

        for option in preserved_options:
            if option.get('id') not in filtered_ids:
                logger.debug(
                    "Preserving selected TS4NFDI collection option for provider '%s' "
                    'because it exactly matches the current search text: id=%s text=%r',
                    self.key,
                    option.get('id'),
                    option.get('text'),
                )
                filtered_options.append(option)
                filtered_ids.add(option.get('id'))

        return filtered_options

    def option_text_matches_search(self, option, search):
        if not search:
            return False

        option_text = option.get('text')
        if not option_text:
            return False

        return option_text.strip().casefold() == str(search).strip().casefold()

    def build_query_params(self, provider_config, search):
        query_params = {}

        if provider_config.get('server_side_search'):
            query_params[provider_config.get('search_param', 'query')] = search

        extra_params = provider_config.get('extra_params', {})
        query_params.update(extra_params)

        return query_params

    def filter_results(self, results, search):
        normalized_search = search.lower()

        return [result for result in results if self.collection_matches(result, normalized_search)]

    def collection_matches(self, result, normalized_search):
        if not isinstance(result, dict):
            return False

        searchable_values = [
            result.get('id'),
            result.get('label'),
            result.get('description'),
            result.get('creator'),
        ]

        for terminology in result.get('terminologies', []):
            if isinstance(terminology, dict):
                searchable_values.extend(
                    [
                        terminology.get('label'),
                        terminology.get('uri'),
                        terminology.get('source'),
                        terminology.get('type'),
                    ]
                )

        return any(value and normalized_search in str(value).lower() for value in searchable_values)

    def map_result_to_option(self, result, provider_config):
        if not isinstance(result, dict):
            return None

        uuid = get_first_value(
            result,
            provider_config.get('id_fields', ('id',)),
        )
        label = get_first_value(
            result,
            provider_config.get('label_fields', ('label',)),
        )
        identifier = self.get_collection_identifier(result, provider_config, uuid)

        if not uuid or not identifier or not label:
            return None

        option = {
            'id': identifier,
            'text': label,
            'uuid': uuid,
        }

        help_text = self.build_help_html(result, provider_config)
        if help_text:
            option['help'] = help_text

        return option

    def get_collection_identifier(self, result, provider_config, uuid):
        identifier = get_first_value(
            result,
            provider_config.get(
                'uri_fields',
                ('iri', 'uri', 'permalink', 'permaLink', 'permalinkUrl'),
            ),
        )

        if identifier:
            return identifier

        return self.build_permalink(uuid, provider_config)

    def build_help_html(self, result, provider_config):
        uuid = get_first_value(
            result,
            provider_config.get('id_fields', ('id',)),
        )
        description = get_first_value(result, ('description',))
        creator = get_first_value(result, ('creator',))
        is_public = result.get('isPublic')
        permalink = self.get_collection_identifier(result, provider_config, uuid)

        parts = []
        badges = []

        if creator:
            badges.append(option_badge(creator, 'ontology'))

        if is_public is not None:
            visibility = 'public' if is_public else 'restricted'
            badges.append(option_badge(visibility, 'term'))

        terminology_summary = self.build_terminology_summary(result, provider_config)
        if terminology_summary:
            badges.append(option_badge(terminology_summary, 'term'))

        breadcrumb = option_breadcrumb(badges)
        if breadcrumb:
            parts.append(breadcrumb)

        details = []
        if uuid:
            details.append(f'uuid: {uuid}')
        if permalink:
            details.append(f'permalink: {permalink}')

        description_parts = [description] if description else []
        description_parts.extend(details)

        description_html = option_description(description_parts)
        if description_html:
            parts.append(description_html)

        return ''.join(parts) or None

    def build_permalink(self, identifier, provider_config):
        if not identifier:
            return None

        permalink_base = provider_config.get(
            'permalink_base',
            'https://w3id.org/ts4nfdi/collection/',
        )
        return f'{permalink_base.rstrip("/")}/{identifier}'

    def build_terminology_summary(self, result, provider_config):
        terminologies = result.get('terminologies')
        if not isinstance(terminologies, list):
            return None

        terminology_labels = []
        badge_limit = provider_config.get('terminology_badge_limit', 5)

        for terminology in terminologies[:badge_limit]:
            if not isinstance(terminology, dict):
                continue

            label = get_first_value(terminology, ('label', 'uri'))
            source = get_first_value(terminology, ('source',))
            if not label:
                continue

            badge_text = label
            if source:
                badge_text = f'{badge_text} ({source})'

            terminology_labels.append(badge_text)

        if not terminology_labels:
            return None

        remaining_count = len(terminologies) - badge_limit
        if remaining_count > 0:
            terminology_labels.append(f'+{remaining_count} more')

        return 'Terminologies: ' + ', '.join(terminology_labels)
